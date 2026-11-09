"""Apply the Supabase schema and seed to the live project.

    python scripts/apply_supabase.py "postgresql://postgres.<ref>:<password>@<host>:5432/postgres"

The URL can also come from SUPABASE_DB_URL in the environment or api/.env
(Project Settings -> Database -> Connection string -> URI). Needs psycopg:
``pip install "psycopg[binary]"``.

Idempotent: if the schema is already present it runs only the seed, then checks
the tables over PostgREST and prints row counts.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    from dotenv import load_dotenv  # type: ignore

    load_dotenv(ROOT / "api" / ".env")
except Exception:
    pass

MIGRATIONS = ROOT / "supabase" / "migrations"
TABLES = ("communities", "residents", "demand_requests", "vendors", "vendor_offers",
          "negotiations", "negotiation_events", "approvals")


def _with_ssl(url: str) -> str:
    if "sslmode=" in url:
        return url
    return url + ("&" if "?" in url else "?") + "sslmode=require"


def _run_sql(conn, path: Path) -> None:
    with conn.cursor() as cur:
        cur.execute(path.read_text(encoding="utf-8"))
    conn.commit()
    print(f"applied {path.name}")


def _verify() -> int:
    import httpx

    base = os.environ.get("SUPABASE_URL", "").rstrip("/")
    key = os.environ.get("SUPABASE_SECRET_KEY") or os.environ.get("SUPABASE_SERVICE_KEY", "")
    if not base or not key:
        print("Set SUPABASE_URL and SUPABASE_SECRET_KEY to verify over PostgREST.")
        return 1
    headers = {"apikey": key, "Authorization": f"Bearer {key}"}
    failures = 0
    for table in TABLES:
        response = httpx.get(
            f"{base}/rest/v1/{table}?select=id&limit=1000",
            headers=headers,
            timeout=20,
        )
        if response.status_code == 200:
            print(f"  {table:20s} {len(response.json()):4d} rows")
        else:
            failures += 1
            print(f"  {table:20s} HTTP {response.status_code}: {response.text[:120]}")
    return 0 if failures == 0 else 1


def main() -> int:
    try:
        import psycopg
    except ImportError:
        print('psycopg is missing. Run: pip install "psycopg[binary]"')
        return 2

    url = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("SUPABASE_DB_URL", "")
    if not url:
        print(
            "Usage: python scripts/apply_supabase.py <postgres-connection-uri>\n"
            "Or set SUPABASE_DB_URL (Project Settings -> Database -> Connection string)."
        )
        return 2

    print("Connecting to the Supabase database…")
    with psycopg.connect(_with_ssl(url), connect_timeout=20) as conn:
        with conn.cursor() as cur:
            cur.execute("select to_regclass('public.communities') is not null")
            schema_exists = bool(cur.fetchone()[0])
        if schema_exists:
            print("Schema already present; running seed only.")
        else:
            _run_sql(conn, MIGRATIONS / "0001_init.sql")
        _run_sql(conn, MIGRATIONS / "seed.sql")

    print("\nVerifying over PostgREST:")
    return _verify()


if __name__ == "__main__":
    raise SystemExit(main())

"""Tests run against a throwaway SQLite file with no external keys."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ["NEGOAI_DB"] = str(Path(tempfile.mkdtemp(prefix="negoai-tests-")) / "test.sqlite3")
os.environ["DEMO_PACE"] = "0.01"
for key in ("GNANI_API_KEY", "GNANI_KEY_ID", "LLM_API_KEY", "SUPABASE_URL", "SUPABASE_SERVICE_KEY"):
    os.environ.pop(key, None)

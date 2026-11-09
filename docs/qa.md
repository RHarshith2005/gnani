# QA results

Run date: 9 November 2026 · environment: Windows, Chrome, local SQLite store,
live Gnani key (Prisma v3.0 + Timbre v3.0).

Honest status: this table records what was actually checked in this workspace.
Rows marked **Not run** need a microphone, a deployed URL or a real deployment
and are not claimed as passing.

## Automated suite

- `pytest api/tests -q` → **74 passed** (no keys, no network).
- `cd web && npm test` → **6 passed** (`node:test`, reducer + format helpers).
- `cd web && npm run build` → passes (819 kB bundle, gzip 232 kB).
- `python scripts/smoke_test.py` → **PASS** for Kannada, Hindi and English
  against the live Gnani APIs.

| Area | Check | Method | Status |
| --- | --- | --- | --- |
| Engine | counter formula, floor clamp, eligibility, no-accept rule | `test_engine.py` (17) | Pass |
| Guard | transcript/range validation of extracted offers | `test_guard.py` (6) | Pass |
| Intake | Kannada, Hindi, English, code-mixed, misheard, negation | `test_intake.py` (6) | Pass |
| Numbers | spelling and parsing in three languages | `test_numbers.py` (7) | Pass |
| Composer | localized agent/vendor lines, numbers as words | `test_composer.py` (5) | Pass |
| PCM | RMS, base64 transport, linear resample | `test_pcm.py` (3) | Pass |
| LLM | fenced/embedded JSON, disabled client is offline | `test_llm.py` (2) | Pass |
| Store | idempotent seed, aggregation +4, event order, offers, sessions | `test_db.py` (5) | Pass |
| Receipt | deterministic chain, tamper changes head, totals, endpoint | `test_receipt.py` (4) | Pass |
| Gateway | real socket: guided run, typed intake, language switch, bad input | `test_gateway.py` (4) | Pass |
| Demo | guided run transcript → vendors → offers → admin | `test_session_demo.py` (3) | Pass |
| API | health without secrets, vendors, demand, approvals, demo roles | `test_api.py` (6) | Pass |
| Gnani wire | TTS payload, raw PCM, STT headers, 1,024-byte framing | `test_gnani_wire.py` (4) | Pass |
| Credits | session cap and voice separation | `test_credits.py` (2) | Pass |
| Reducer | ready/offers/admin/approval, no duplicate vendor line | `session.test.mjs` (4) | Pass |
| Format | rupee grouping, percent, clamp | `format.test.mjs` (2) | Pass |
| Boot | `GET /api/health` ok, no key material | suite + live config | Pass |
| SPA | `/`, `/console`, `/room` served through the Vercel entrypoint | `TestClient` on `app.py` | Pass (local) |
| Vercel entry | `import app`, `VERCEL=1` → `/tmp/negoai.sqlite3` | local command | Pass (config) |
| Deploy | preview/production build on Vercel | `npx vercel` | Not run |
| Voice (Kannada) | Timbre v3.0 → Prisma v3.0 transcript, live | `scripts/smoke_test.py` | Pass |
| Voice (Hindi) | Timbre v3.0 → Prisma v3.0 transcript, live | `scripts/smoke_test.py` | Pass |
| Voice (English) | Timbre v3.0 → Prisma v3.0 transcript, live | `scripts/smoke_test.py` | Pass |
| Human mic | noisy room, interruption, phone | manual, Chrome/Android | Not run |
| Supabase schema | tables, RLS, realtime, seed | project reachable; migration not applied | Not run |

## Voice roundtrip, as measured

Each language is synthesized by Timbre v3.0, streamed to Prisma v3.0 in
1,024-byte frames at real-time cadence, and the returned transcript printed.

- Kannada: 215,040 bytes (~6.7 s audio) in 2.53 s → Kannada script, numbers as words.
- Hindi: 202,240 bytes in 2.11 s → Hindi transcript; `360` and `can` code-mix.
- English: 194,560 bytes in 1.88 s → English transcript with `360`.

## Known gaps

- No Vercel deployment was run from this workspace (no account token). The
  entrypoint, build, SPA serving and `/tmp` store were validated locally.
- Vercel WebSockets close at the function duration (300 s Hobby), and `/tmp`
  SQLite is per-instance; durable replay across instances needs Supabase.
- Supabase is configured but its public schema is empty. Apply
  `supabase/migrations/0001_init.sql` then `seed.sql` to use it.
- Voice checks use synthesized audio, not a human microphone; real-room word
  error rate is unmeasured.
- Telephony is out of MVP scope; the phone button is disabled with a tooltip.

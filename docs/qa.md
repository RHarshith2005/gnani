# QA results

Run date: 4 November 2026 · environment: Windows, Chrome, local SQLite store.

Honest status: this table records what was actually checked in this workspace.
Rows marked **Not run** need a microphone, a deployed URL or a Gnani key and are
not claimed as passing. The automated suite (`pytest api/tests`) and the Vite
production build do pass; see `docs/submission.md` for the commands.

| Area | Check | Method | Status |
| --- | --- | --- | --- |
| Boot | `GET /api/health` returns ok, no secrets | `TestClient` test + manual curl | Pass |
| Engine | counter formula, floor clamp, eligibility, no-accept rule | `api/tests/test_engine.py` (17 cases) | Pass |
| Guard | transcript/range validation of extracted offers | `api/tests/test_guard.py` | Pass |
| Intake | Kannada, Hindi, English and code-mixed slot parsing | `api/tests/test_intake.py` | Pass |
| Numbers | 19/22/360/1080 rupees in three languages | `api/tests/test_numbers.py` | Pass |
| Demo | guided run emits transcript → vendors → offers → admin | `api/tests/test_session_demo.py` | Pass |
| API | health, vendors, sessions, approvals | `api/tests/test_api.py` | Pass |
| Build | `npm run build` completes | Vite 6 production build | Pass |
| Text negotiation | three personas finish in ≤3 rounds, offers stored | `python scripts/run_negotiation.py` | Pass |
| WebSocket | guided run over `/ws/voice`, admin event received | `python scripts/ws_client.py --mode guided` | Pass |
| Demand | baseline 360/week, +3 after a confirmed request | `GET /api/demand/summary` | Pass |
| Voice (Kannada) | speak and hear Kannada through Prisma + Timbre | needs `GNANI_API_KEY` | Not run |
| Voice (Hindi) | speak and hear Hindi through Prisma + Timbre | needs `GNANI_API_KEY` | Not run |
| Noisy audio | low-SNR request is re-asked | manual, café noise | Not run |
| Interruption | barge-in cancels playback | manual, Chrome | Not run |
| Mic denied | clear error, text fallback works | manual, Chrome | Not run |
| Phone | 390 px layout on Android Chrome | deployed URL | Not run |
| Replay | `/replay` plays a stored run | manual after a demo run | Pass (local data) |

## Known gaps

- The Gnani STT/TTS payloads are implemented from the blueprint's documented
  endpoints but were not exercised without a key. Treat the smoke test as the
  first thing to run when the key arrives.
- Supabase migrations were written and reviewed but not applied here; the demo
  runs on the local SQLite store with the same schema.
- Telephony is out of MVP scope and the phone button is disabled with a
  "coming soon" tooltip.

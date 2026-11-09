# NegoAI architecture

*One brain, many channels. The engine decides, the LLM speaks. Numbers are words before TTS.
Keys stay on the server. Events are append-only.*

---

## 1. Shape

```
 Browser (React 18 + Three.js, JavaScript)        FastAPI gateway                    Gnani
┌───────────────────────────────────────┐   ┌──────────────────────────────┐   ┌──────────────┐
│ mic → AudioWorklet → 16 kHz PCM16 ────┼──▶│ VoiceSession                 │   │ Prisma STT   │
│ typed text ───────────────────────────┼──▶│  intake → engine → composer  │──▶│ Timbre TTS   │
│                                       │   │  guard → summary             │◀──│              │
│ orb ← level/state ← events ───────────┼◀──│  append-only SQLite events   │   └──────────────┘
│ transcript, vendor cards, admin ──────┼◀──│                              │
└───────────────────────────────────────┘   └──────────────────────────────┘
                                                          │
                                            optional LLM (rephrase only)
```

Three channels, one orchestrator: browser mic, typed text, and the guided demo. The same
`VoiceSession` serves all of them over one WebSocket, `/ws/voice`. There is no second agent for the
demo and no client-side business logic that computes a price.

## 2. Layers

| Layer | Module | Owns |
| --- | --- | --- |
| Transport | `api/voice/gateway.py` | socket lifecycle, message dispatch |
| Orchestration | `api/voice/session.py` | phases, turns, pacing, event emission, persistence |
| Policy | `api/negotiation/engine.py` | state machine, counter prices, eligibility, walk-away |
| Persona | `api/negotiation/personas.py` | hidden floors, concession steps, delivery policy |
| Language | `api/agents/composer.py`, `api/speech/numbers.py` | localized speech with spelled numbers |
| Safety | `api/agents/guard.py` | transcript/range checks on anything the LLM returns |
| Data | `api/db.py`, `supabase/migrations/` | append-only events, offers, approvals |

Dependencies point one way: session → engine/agents → engine models. The engine imports no web or
agent code, so it is testable as pure logic.

## 3. Turn lifecycle

1. **Input** arrives as text or PCM.
2. **Intake** (`IntakeState`) collects product → quantity → confirmation in words → delivery day →
   flat. Only a confirmed quantity is stored.
3. **Aggregation** turns the resident's 3 cans into the community's verified 360/week.
4. **Negotiation** builds one `NegotiationEngine` + one `SimVendor` per persona, so each supplier has
   its own private floor, quote history and round count.
5. **Directive** — the engine returns an instruction (`ask_quote`, `counter`, `ask_delivery`,
   `mention_competitor`, `escalate`, `walk_away`) with the exact number to say.
6. **Phrasing** — the composer renders it in the active language; if an LLM is configured it may
   rephrase, and its output is rejected when it contains an unsupplied number.
7. **Speech** — Timbre returns PCM (or the browser speaks), the orb reacts to RMS levels.
8. **Persistence** — every offer/directive/decision appends a `negotiation_events` row.
9. **Approval** — the admin screen receives engine-computed savings and risks; only Approve/Reject
   writes to `approvals`. The agent cannot accept.

## 4. Engine

```
states: ASK_QUOTE → COUNTER_1 → COUNTER_2 → COUNTER_3 → ESCALATE_TO_ADMIN | WALK_AWAY
counter_k = quote − (quote − target) × [0.6, 0.8, 1.0][k−1]
```

- Clamped at `target`, clamped at the live `quote`, rounded to the rupee.
- An offer at or below `max_price` is marked **eligible**, not accepted.
- Delivery is asked exactly once, after the first counter.
- A competing quote may be mentioned once, and only from another vendor's recorded offer.
- New offers clear queued directives so a counter can never reference a stale price.
- `try_accept()` always returns `False` and records the refusal to accept.

The browser receives `public_state()`, which deliberately omits `target_price`, `max_price` and
every vendor floor (covered by tests). Floors exist only inside the persona object on the server.

## 5. WebSocket protocol

Client → server:

| Type | Fields | Purpose |
| --- | --- | --- |
| `hello` | `mode` (`live`/`guided`), `language` | open a session |
| `text` | `text` | same brain, typed channel |
| `audio` | `pcm` (base64 PCM16), `sampleRate` | 50 ms frames from the worklet |
| `barge_in` | — | stop playback, return to listening |
| `approve` | `decision`, `note` | committee decision |
| `language` | `language` | switch voice/script |
| `reset` | — | new session |

Server → client: `ready, state, level, partial, transcript, agent, audio, confirm, demand, phase,
negotiation, vendor, offers, admin, approval, notice, error`.

The front end funnels every event through `useSession.applyEvent`, so the protocol is the only
contract between the two halves.

## 6. Degradation ladder

| Missing | Behaviour |
| --- | --- |
| Nothing | Prisma STT + Timbre TTS + optional LLM |
| Gnani key | composer sentences + browser `SpeechRecognition`/`SpeechSynthesis`; UI says so |
| Browser speech API | typed input still drives the identical agent; UI explains the fallback |
| WebGL | CSS conic-gradient ring in the orb slot |
| `prefers-reduced-motion` | static face-on orb, no transitions |
| Supabase | local SQLite store with the same schema |

This ladder is why the demo can be recorded on any machine.

## 7. Latency budget

Measured on 9 Nov 2026 with the live key: Timbre REST returns a full 2–3 s sentence in roughly
1.5–2.5 s, and Prisma emits one final transcript per VAD segment after the configured 700 ms of
silence. The LLM stays off the critical path by default (the composer emits immediately), and Prisma
VAD tuning is exposed through env headers. The blueprint's sub-1.5 s target needs streaming TTS
(`wss://api.vachana.ai/api/v1/tts`), which is the next latency step; greetings are still cached per
language by `GnaniTTSService`.

## 8. Data model

`communities → residents → demand_requests`, `vendors → vendor_offers`,
`negotiations → negotiation_events (append-only) → approvals`.

`negotiation_events` is the source of truth for replay and for the dashboard. The Postgres migration
adds a trigger that rejects updates/deletes, RLS for resident/admin roles, and realtime publications
for `negotiation_events` and `vendor_offers`.

## 9. Front-end shape

- **Design system:** tokens sampled from the reference frame (`tokens.css`); glass panels use
  `backdrop-filter` above the orb; container queries keep the hero proportional at any width.
- **Orb:** `FurTorus` builds ~9,000 two-vertex hairs from torus surface normals and one
  `ShaderMaterial`; uniforms (`uLevel`, `uStand`, `uSway`, `uPulse`) map state to motion. States:
  idle tumble (6.7 s, 180°), listening (face-on, fur up), thinking (2.5× spin, lifted tips),
  speaking (audio-reactive pulse). DPR capped at 2; full disposal on unmount.
- **State:** zustand store, one event reducer, derived selectors for the room and admin screens.
- **Motion:** framer-motion for entrance/stagger, ticker interpolation, and confirm cards; 600 ms
  `cubic-bezier(.22,1,.36,1)` throughout, mirroring the blueprint's easing.
- **Audio:** worklet resamples to 16 kHz and posts Int16 frames; a queue player schedules Timbre PCM
  gaplessly; barge-in stops the queue.

## 10. Security and honesty

- No key is exposed through `/api/health`, REST or the socket (`capabilities` only).
- Vendor floors and committee ceilings never cross the wire.
- No number in the UI comes from a language model.
- Vendors are labelled simulated on every screen and stored with `source = simulated`.
- The agent identifies itself as an AI in its first sentence of every negotiation.
- `GET /api/sessions/{id}/receipt` recomputes a SHA-256 chain over the append-only events; the committee can keep the chain head as proof, and any later edit changes it.

## 11. What to build next

1. Stream TTS over `wss://api.vachana.ai/api/v1/tts` so first audio arrives in well under a second; keep the REST path as the fallback.
2. Move the store to Supabase and let the room subscribe to realtime instead of the socket.
3. Telephony: the same session behind an outbound SIP leg, one vendor per call.
4. Payment terms and contracts as a fourth negotiation lever.
5. Real vendor onboarding with verified quotes replacing simulated floors.

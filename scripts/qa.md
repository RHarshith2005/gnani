# NegoAI QA runbook

Run this before recording or submitting. Record results in `docs/qa.md`.
Everything here works with **no keys**: the scripted composer and browser speech
are the fallback. Re-run the voice rows with `GNANI_API_KEY` set when the key
arrives, because the Gnani wire format is the one part that cannot be verified
without the challenge account.

## 0. Boot

1. `python -m venv .venv` then install `api/requirements.txt`.
2. `uvicorn api.main:app --reload --port 8000`
3. `cd web && npm install && npm run dev`
4. Open `http://localhost:5173` and `http://localhost:8000/api/health`.
5. Expected: health `ok: true`, `capabilities.stt` is `browser` or `gnani`,
   no key appears in the response.

## 1. Language matrix (3 languages x 3 conversations)

For each language (Kannada, Hindi, English) run these three conversations in
the voice console, using the mic where the browser supports it and the text box
otherwise:

| # | Conversation | Expected |
| --- | --- | --- |
| 1 | "three water cans every week" → confirm → "Saturday" → flat number | quantity read back in words, confirm card appears, demand saved, negotiation starts |
| 2 | same, but say "no, change it" at the confirm step | quantity is cleared and re-asked, nothing saved |
| 3 | two-item request ("three water cans and two litres of milk") | the collector takes one item at a time and never guesses a number |

Check after each run: `/api/demand/summary` total increases by the confirmed
quantity, `/api/demand/requests` shows the row, and the negotiation room shows
three vendor cards with round dots.

## 2. Negotiation and approvals

1. Open `/room?demo=1` and press **Start demo**.
2. Expected: three simulated suppliers, prices step down, round dots fill,
   the **Simulated vendor** badge is visible on every vendor screen.
3. Press **Pause** — audio and turns stop. **Resume** continues.
4. Press **Skip supplier** — the current vendor ends and the next starts.
5. Press **Stop** — the run ends; completed events remain in `/replay`.
6. Open `/admin` and approve. Expected: approval banner, savings is computed
   from stored first quote and best eligible offer, and the number never comes
   from an LLM.
7. Confirm the agent says it is an AI in the first sentence of each call and
   never accepts an offer itself.

## 3. Robustness

| Test | How | Expected |
| --- | --- | --- |
| Noisy audio | play cafe noise at low SNR, then speak a request | agent asks again rather than guessing |
| Interruption | speak while the agent is talking | playback stops, state returns to listening |
| Mic denied | block microphone permission in the browser | clear on-screen message, text box still works |
| Offline | stop the API process | console shows the gateway error, replay still lists nothing and explains why |
| Phone browser | open the deployed URL on Android Chrome over mobile data | layout fits 390 px, buttons reachable, no horizontal scroll |
| Reduced motion | enable OS reduce-motion | orb is static, no looping transitions |
| Replay | open `/replay`, play a stored run | events replay in order, labelled as a replay, no live vendor |

## 4. Honesty checklist

- [ ] Vendor badge says simulated on the room and admin screens.
- [ ] Footer says "Powered by Gnani Prisma + Timbre" only if that is what ran.
- [ ] No invented competitor quote is spoken.
- [ ] No target, ceiling or floor price is visible in the browser.
- [ ] README limitations match what was actually tested.

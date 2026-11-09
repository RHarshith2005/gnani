# NegoAI submission pack

For the Gnani.ai Great Indian AI Internship Challenge. Deadline 10 Nov 2026,
11:59 PM IST.

## 120-word explanation

NegoAI is a voice procurement desk for apartment communities. Residents say
what they need in Kannada, Hindi, English or a code-mix: "three water cans every
week". The agent reads the quantity back in words, saves it only after
confirmation, and aggregates 120 households into one verified demand of 360 cans
a week. The negotiation engine then calls three simulated suppliers, computes
every counter-offer from a fixed formula, and escalates eligible offers to the
committee. The language model may phrase a turn, but it never chooses a number,
and any price it invents is rejected against the transcript. The admin sees one
page: verified demand, best eligible offer, weekly savings and risks. One
approval replaces 120 separate conversations. Every offer and decision is an
append-only event, so the whole negotiation replays for audit. Synthetic data
only, simulated vendors labelled on screen.

## LinkedIn / X post variants

Hashtags: use the set the official rules require. Confirm them before posting;
the three below are indicative, not a substitute for the rules page.

### 1. Problem-first (LinkedIn)

> 120 families. One building. Everyone buying the same water cans alone.
>
> NegoAI is a voice procurement desk for apartment societies. A resident speaks
> their weekly need in Kannada, Hindi or English. The agent confirms the
> quantity, aggregates the building's demand, and negotiates with suppliers.
>
> The important part: the negotiation engine decides every price. The LLM only
> speaks. Invented numbers are rejected. The committee approves once.
>
> Built for the Gnani.ai challenge with Prisma for speech and Timbre for voice.
> Synthetic data, simulated vendors, full audit trail.
>
> #NegoAI #GnaniAI #VoiceAI #GreatIndianAIInternship

### 2. Engineering-first (X)

> The rule I built NegoAI around: the engine decides, the LLM speaks.
>
> Counters come from a fixed formula. The model rephrases them. Any price that
> is not in the transcript or the engine directive is thrown away.
>
> Voice in Kannada/Hindi/English, one committee approval, append-only replay.
>
> #NegoAI #GnaniAI #VoiceAI

### 3. Demo-first (LinkedIn)

> 60 seconds of NegoAI: ask for three water cans in Kannada, watch the orb stand
> up, then watch three suppliers bid for the society's 360-can weekly demand.
> The ticker drops 22 → 20 → 19. The admin sees the savings and taps Approve.
>
> Suppliers are simulated and labelled. Prices are engine-computed. Every event
> is stored, so the same run replays from the audit log.
>
> Powered by Gnani Prisma + Timbre.
>
> #NegoAI #GnaniAI #GreatIndianAIInternship

## 60-second shot list

| Time | Shot |
| --- | --- |
| 0–8 s | Hero, orb tumbling. Hook: "Why should 120 families haggle alone?" |
| 8–20 s | Tap Mic, ask for water cans in Kannada. Orb stands up, transcript and confirm card appear. |
| 20–40 s | Negotiation room. NegoAI vs simulated vendor, ticker drops 22 → 20 → 19, English subtitles, Simulated vendor badge. |
| 40–52 s | Admin screen. Savings number, risks, tap Approve. |
| 52–60 s | Closing: "Built with Gnani Prisma + Timbre", required hashtags. |

Rules: show the real app working, label the vendor simulated, never buy
engagement.

## Pre-submit checklist

- [ ] `pytest api/tests -q` passes (74 cases).
- [ ] `cd web && npm test` passes (6 checks).
- [ ] `python scripts/smoke_test.py` prints PASS for Kannada, Hindi and English.
- [ ] `cd web && npm run build` passes.
- [ ] `python scripts/run_negotiation.py` prints PASS.
- [ ] `python scripts/ws_client.py --mode guided` prints an admin summary.
- [ ] `GET /api/health` on the deployed API returns ok and no key material.
- [ ] Public URL works on a phone over mobile data (WSS, not mixed content).
- [ ] Vendor badge and AI disclosure visible in the recording.
- [ ] No real vendor, resident or price in the seed data.
- [ ] README limitations and `docs/qa.md` match what actually ran.
- [ ] Gnani key set only in the server environment, never in `web/`.
- [ ] Official hashtags copied from the current rules page.
- [ ] Submission uploaded before 10 Nov, 11:59 PM IST.

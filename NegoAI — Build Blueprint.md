# NegoAI — Build Blueprint

*Gnani.ai Great Indian AI Internship Challenge · prepared 2 Nov 2026 · submission closes 10 Nov, 11:59 PM IST*

**Pitch frame.** Why now: Indian-language voice AI now handles code-mixed Kannada, Hindi and English speech. Problem: families in one apartment buy the same milk and water cans separately, so nobody has bargaining power. Who benefits: residents (lower prices), vendors (predictable bulk orders) and the society admin (one approval instead of chasing everyone).

## 0. What your video actually is

The video is a 6.7-second looping landing-page hero for a generic agency (“We Build Digital”), not a NegoAI screen. So NegoAI borrows its visual language: lavender canvas, a frosted-glass panel over a fuzzy purple 3D torus, a huge white Poppins headline and an outlined button. Section 1 is the exact spec and the prompts in section 4 reproduce it.

**Verified in docs.gnani.ai:** realtime STT over WebSocket at wss://api.vachana.ai/stt/v3/stream (raw PCM, 1,024-byte frames, 8 kHz or 16 kHz); TTS REST at /api/v1/tts/inference, SSE at /api/v1/tts/sse, WebSocket at wss://api.vachana.ai/api/v1/tts; auth header X-API-Key-ID; Timbre v2.5 (model timbre-v2.5, 10 Indian languages, voices such as Nalini, Kaveri, Deepak); an official pipecat-gnani plugin.

**Not verified, check first:** whether Prisma v3 is enabled on challenge accounts (the docs I found list v2.5), which voices exist per language, which telephony provider fits, and whether a non-Gnani LLM is allowed next to the Gnani APIs (ask Gnani and disclose any LLM you use).

## 1. UI design spec (from the video)

### 1.1 Layout

Percentages are of the card. The card is 16:9 (676×380 inside the 720×720 frame), centred on the canvas, square corners.

- **Frosted panel:** left 0–47.8%, full height. Backdrop blur plus white tint. The torus is visibly blurred where it passes behind it.
- **Logo:** dot-matrix mark, left 10.3%, top 9.5%.
- **Nav:** right-aligned, top 9%, right margin 7%. Three links plus a hamburger (three deep-purple lines).
- **Slider arrows ‹ ›:** white chevrons centred at x 76.6%, y 25%.
- **Headline:** left 8.6%, top 27.6%, three lines, font-size 8.6% of card width, line-height 0.95.
- **Subtitle:** centred at y 76%, 1.9% of card width.
- **CTA:** top 81.8%, 9.9% wide × 5.8% tall, 1 px white outline, square corners, uppercase condensed.
- **Social squares:** three outlined squares (3% wide, gap 1.5%), right 8.6%, bottom 5%.
- **Torus:** centre ≈ (52%, 49%), outer diameter ≈ 45% of card width (about 80% of card height), hole ≈ one third of that. The panel edge cuts through its left side.

### 1.2 Tokens

Canvas, glass and fur colours are sampled from the pixels. Highlight and shadow tones are estimates.

- Canvas #EED7FD
- Card zone #CDADD8 → #C7A4DA, with a faint periwinkle bloom (#B9B6EA at about 20%) on the far-left edge
- Glass: blur about 22 px, white tint 22%, reads as #CAB8DD
- Fur: root #5A1F94, base #7D32A0, mid #924DB2, tip #B27FD8
- Ink #FFFFFF; deep purple #5B2A86 (hamburger, dark small text)
- Shadow: 0 30px 60px -10px rgba(140,70,200,.35)
- Film grain: monochrome noise at 6–7% over the whole card
- Fonts: Poppins 600 (headline), Poppins 400 (body, nav), Oswald 400 (button)

### 1.3 Motion

- **Torus:** one seamless 6.7 s loop. Face-on → edge-on at about 3 s → face-on again. That is a 180° turn around the vertical axis (a torus looks identical after 180°) with a constant \~15° tilt so it never goes fully flat. The fur sways slightly.
- Everything else in the video is static. For NegoAI add 600 ms ease-out transitions (cubic-bezier(.22,1,.36,1)) between states, plus hover on the chevrons and button.

### 1.4 NegoAI mapping

- Logo → dot-matrix waveform mark
- Nav → Home · How it works · Live demo
- Headline → Your Society. / One AI. / Better Deals.
- Subtitle → We Listen | We Negotiate | We Save.
- CTA → TRY VOICE DEMO (outlined, same style)
- **Torus → the voice agent itself (the orb).** Idle: the 6.7 s tumble. Listening: turns face-on and the fur stands up with mic level. Thinking: spins faster and the fur tips lighten. Speaking: fur pulses with the TTS audio level.
- Arrows ‹ › → step through demo scenes: Resident → Negotiation → Savings
- Social squares → Mic, Phone, Language (globe). Mic starts the web conversation. Phone stays disabled with a ‘coming soon’ tooltip until telephony really works. Language opens the language chips.

### 1.5 App screens in the same language

- **Voice console:** orb on the right. The glass panel on the left holds the live transcript (white text, no bubbles, newest line brightest), a language chip and a quantity-confirm card (‘Three water cans / week — confirm?’).
- **Negotiation room:** glass panel with one card per vendor (name, quote, delivery, round dots) and a price ticker that steps down as rounds proceed. Two small orbs show who is speaking: NegoAI and Vendor.
- **Admin approval:** glass cards for total demand, best offer, weekly savings (big white number), risks, and Approve / Reject. Approve = white fill with deep-purple text, Reject = outline.

### 1.6 Starter CSS

```css
:root{--bg:#EED7FD;--zone:#CDADD8;--deep:#5B2A86;--glass:rgba(255,255,255,.22)}
body{margin:0;min-height:100vh;display:grid;place-items:center;background:var(--bg);font-family:Poppins,system-ui,sans-serif}
.card{container-type:inline-size;position:relative;overflow:hidden;width:min(94vw,1100px);aspect-ratio:16/9;
  background:linear-gradient(120deg,#C9B6EA 0%,#C7A4DA 25%,#CDADD8 100%);box-shadow:0 30px 60px -10px rgba(140,70,200,.35)}
.card::after{content:'';position:absolute;inset:0;pointer-events:none;opacity:.07;mix-blend-mode:overlay;background:url(noise.svg)} /* noise.svg = feTurbulence tile */
.orb{position:absolute;left:52%;top:49%;width:45cqw;aspect-ratio:1;transform:translate(-50%,-50%)} /* Three.js canvas, below .glass */
.glass{position:absolute;inset:0 auto 0 0;width:47.8%;backdrop-filter:blur(22px);background:var(--glass)}
h1{position:absolute;left:8.6%;top:27.6%;margin:0;font:600 8.6cqw/.95 Poppins,sans-serif;color:#fff}
.sub{position:absolute;left:8.6%;top:73.5%;margin:0;font-size:1.9cqw;color:#fff}
.cta{position:absolute;left:8.6%;top:81.8%;height:5.8%;padding:0 1.8cqw;border:1px solid #fff;background:none;color:#fff;
  font:400 1.8cqw Oswald,sans-serif;letter-spacing:.04em;text-transform:uppercase;border-radius:0}
```

### 1.7 Legibility fix

White text on the video’s glass has only about 1.8:1 contrast. For the app, deepen the glass tint to rgba(110,60,160,.28) (the headline then sits near 3:1, acceptable for very large type) and set small text on the glass to #3B1A5E (about 7:1). Judges will watch your demo on phones.

## 2. Architecture

```
Browser (React + Three.js)                  Backend (FastAPI)                             Gnani
 mic > AudioWorklet > 16 kHz PCM  --WS-->   Voice gateway (Pipecat pipeline)   --WS-->   Prisma STT (realtime)
 fur-torus orb (audio-reactive)             |  VAD + turn-taking + barge-in
 transcript, confirm cards  <--events--     +-> Orchestrator --> LLM (JSON only)
 admin dashboard <-- Supabase Realtime      |        +-> Negotiation engine (plain Python rules)
                                            +-> Timbre TTS (WS/SSE) --audio--> browser
Supabase Postgres: communities, residents, demand_requests, vendors, vendor_offers,
                   negotiations, negotiation_events (append-only), approvals
Sim-Vendor: same orchestrator, vendor role, own persona prompt + own Timbre voice
```

### 2.1 Decisions that matter

1. **One brain, many channels.** Browser mic, the demo mode and (later) phone all hit the same orchestrator. Never build two agents.
2. **The engine decides, the LLM speaks.** Every number comes from code. The LLM returns JSON and any price it emits is checked against the engine’s allowed range. This is what makes it a negotiator and not a chatbot, and it is your best interview talking point.
3. **Pipecat for the voice loop.** The pipecat-gnani plugin wraps Gnani STT and TTS, and Pipecat handles VAD, turn-taking and interruptions. If it fights you by 4 Nov, fall back to plain WebSockets.
4. **Simulated vendor.** The synthetic-data rule means no real vendors. A second agent with a hidden floor price gives you a live, repeatable negotiation. Label it ‘simulated vendor’ on screen and in the post.
5. **Stream everything.** Send STT finals to the LLM as soon as VAD ends and speak TTS sentence by sentence. Target under about 1.5 s from end of speech to first audio.
6. **Numbers as words for TTS.** Gnani’s docs say to pass numbers, dates and currency as spoken words. Write a small helper that spells out prices in the active language before every TTS call.
7. **Keys never touch the browser.** The browser talks only to your gateway.
8. **Append-only events.** Every offer, counter and decision is a row in negotiation\_events. The dashboard just renders it, and you get replay for free.

### 2.2 Negotiation engine

Inputs per product: demand\_qty, target\_price, max\_price, best verified competing quote (optional), max\_rounds = 3.

States: ASK\_QUOTE → COUNTER\_1 → COUNTER\_2 → FINAL → ESCALATE\_TO\_ADMIN or WALK\_AWAY.

- counter\_k = quote − (quote − target) × \[0.6, 0.8, 1.0\]\[k−1\], never below target.
- If a verified competing quote exists and is lower than the vendor’s, mention that number once (real data only).
- Ask for free delivery once, after the price has moved.
- If quote ≤ max\_price at any point, mark the offer ‘eligible’ for admin approval. The agent never accepts.
- After FINAL, if quote > max\_price, walk away politely.
- Each turn the engine hands the LLM a directive, for example: ‘Counter at eighteen rupees. Mention the bulk demand of three hundred sixty cans a week.’

### 2.3 Latency budget

End-of-speech detection 0.3–0.5 s → LLM 0.6–1.0 s (short prompts, JSON mode, low temperature) → first TTS audio under 0.4 s. Pre-render fixed phrases (greeting, AI disclosure) per language and cache them.

### 2.4 Checkpoints

- **2–3 Nov:** key working, one STT call and one TTS call in Kannada, mic loop, hero UI in place.
- **4 Nov (go/no-go):** speak Kannada, hear Kannada back, one full negotiation round against Sim-Vendor. If missed, switch to the wedding concierge on the same voice loop.
- **5–6 Nov:** aggregation, engine, three vendor personas, admin screen.
- **7 Nov:** Kannada, Hindi and English polish, noise test. Phone calls only if everything above is solid.
- **8–9 Nov:** record, post, write the explanation. **10 Nov:** submit early.

### 2.5 Repo layout

```
negoai/
  web/   src/components/{Hero,FurTorus,VoiceConsole,NegotiationRoom,AdminApproval}.tsx
  api/   voice/  agents/  negotiation/engine.py  db/  main.py
  supabase/  migrations/  seed.sql
  README.md
```

## 3. Runtime agent prompts

### 3A. Resident demand collector

```
You are NegoAI’s resident assistant for {community_name}. Collect a weekly requirement.
Collect: product (water can | milk | vegetables), quantity, frequency, preferred delivery day, flat number.
Ask ONE thing at a time. After each quantity, read it back in words and ask for confirmation
(‘Three water cans every week — correct?’). Only confirmed items count.
Reply in the resident’s language and script mix. If you did not clearly hear a number, ask again. Never guess.
Never promise a price. Say the community will negotiate and share the result.
Say numbers as words. Keep every reply under 20 words.
Output JSON only: {"say": str, "slots": {...}, "confirmed": bool, "language": "kn-IN|hi-IN|en-IN|..."}
```

### 3B. Negotiator (the important one)

```
You are NegoAI, an AI procurement negotiator calling for {community_name}, a community of {households} households.
You are on a live voice call with {vendor_name}, a supplier of {product}.

IDENTITY: In your first sentence say you are an AI assistant calling on behalf of the community.
If the vendor asks you to stop, thank them and end the call.

GROUND TRUTH (the only facts you may state):
- Verified weekly demand: {qty} {unit}
- Verified competing quotes you may mention: {verified_quotes_json} (if empty, say only that you are comparing several suppliers, with no numbers)
- Round {round} of {max_rounds}
- ENGINE DIRECTIVE for this turn: {directive}
Never reveal target or walk-away prices. You do not know them.

RULES
1. Never invent a quote, competitor, discount or commitment. If it is not in GROUND TRUTH you do not know it.
2. Never accept or confirm a purchase. You may only say the offer goes to the community committee for approval.
3. Follow the ENGINE DIRECTIVE. Do not choose numbers yourself.
4. One lever at a time: price, then delivery, then payment terms.
5. Match the vendor’s language and script mix. Sentences under 20 words. One question at a time.
6. Say numbers as words (‘nineteen rupees’, never ‘Rs 19’).
7. If unsure what number the vendor said, ask them to repeat it. Never guess.

OUTPUT JSON ONLY:
{"say": str, "intent": "ask_quote|counter|ask_delivery|clarify|close|end",
 "offer_extracted": {"unit_price": num|null, "delivery_charge": num|null, "min_qty": num|null, "valid_days": num|null},
 "language": "kn-IN|hi-IN|en-IN|..."}
```

### 3C. Sim-Vendor (demo persona)

```
You are role-playing {vendor_name}, a {persona} supplier of {product} in Bengaluru, for a software demo.
Speak in {language_mix}. Hidden facts: opening quote {open}, absolute floor {floor} (never go below),
you concede about {step} per round, free delivery only above {free_delivery_qty}.
Be realistic: haggle, mention diesel costs, ask about payment terms. You do not know other vendors’ prices.
Replies under 25 words. Never reveal your floor.
Output JSON only: {"say": str, "offer": {"unit_price": num, "delivery_charge": num, "min_qty": num}}
```

Personas to seed: **stubborn** (small steps), **friendly volume-hungry** (drops fast for bulk), **cheap but slow** (lowest price, three-day delivery).

### 3D. Admin summary

```
You write the summary for the community admin. Input: structured offers JSON.
Output: (1) recommended vendor and one-sentence reason, (2) weekly savings versus the first quote,
computed ONLY from supplied numbers, (3) risks: min quantity, quote validity, delivery,
(4) exactly what the committee must approve. Add no number that is not in the input.
Max 90 words, plain English, plus one line in Kannada.
```

## 4. Build prompt series

Paste Prompt 0 at the start of every coding session, then run 1 to 8 in order.

### Prompt 0 — primer

```
You are my senior engineer on NegoAI, a multilingual voice AI that negotiates bulk purchases for an apartment community.
It is my entry for Gnani.ai’s AI internship challenge (deadline 10 Nov 2026, 11:59 PM IST).
Stack: React + Vite + TypeScript + Tailwind + Three.js; FastAPI (Python 3.11); Supabase Postgres;
Gnani Prisma (STT) and Timbre (TTS) via api.vachana.ai; Pipecat with the pipecat-gnani plugin for the voice loop.
Hard rules: synthetic data only; Gnani key only on the server (env GNANI_API_KEY); the LLM never decides prices,
the engine does; the agent always says it is an AI; numbers are spelled out as words before TTS.
Output: complete files with path headers, no theory, no placeholders I have to guess.
If something is ambiguous, pick the simplest option and say so in one line.
```

### Prompt 1 — hero UI (exact match to the video)

```
Create src/components/Hero.tsx (+ Hero.css) reproducing this design exactly. Card 16:9 centred on a #EED7FD canvas,
container-type:inline-size, sizes in cqw. Left 47.8% is a frosted glass panel (backdrop-filter blur 22px, white 22% tint)
layered ABOVE a canvas slot for the orb. Headline ‘Your Society. / One AI. / Better Deals.’ Poppins 600, white, 8.6cqw,
line-height .95, left 8.6%, top 27.6%. Subtitle ‘We Listen | We Negotiate | We Save.’ 1.9cqw.
Outlined square CTA ‘TRY VOICE DEMO’ (Oswald, uppercase, 1px white border, no radius) at top 81.8%.
Nav top-right: Home, How it works, Live demo + 3-line hamburger in #5B2A86. Dot-matrix waveform logo top-left.
Chevron arrows ‹ › at (76.6%, 25%). Three 3cqw outlined squares bottom-right with Mic, Phone, Globe icons.
Card gradient #C9B6EA → #C7A4DA → #CDADD8, shadow 0 30px 60px -10px rgba(140,70,200,.35),
7% film-grain overlay from an inline SVG feTurbulence. Respect prefers-reduced-motion.
Props: onMic, onPhone, onLanguage, orbState.
```

### Prompt 2 — fuzzy torus orb

```
Create src/components/FurTorus.tsx with Three.js: a fuzzy 3D torus (TorusGeometry radius 1, tube .5) covered with about
9,000 hair strands in one LineSegments BufferGeometry. Each hair follows the surface normal, length .06–.14,
root colour #5A1F94 → tip #B27FD8, base mesh #7D32A0. Transparent canvas, constant 15° X tilt, seamless 6.7 s loop
rotating 180° around Y. Props: state ‘idle’|‘listening’|‘thinking’|‘speaking’, level 0–1.
Shader uniform uLevel lengthens the hair and adds sway. Listening: rotate face-on and hold. Thinking: 2.5x spin, tips lighten.
Speaking: hair length pulses with level. Position centre (52%, 49%), width 45cqw, below the glass panel.
CSS fallback (blurred conic-gradient ring) if WebGL is unavailable or reduced-motion is set. Cap devicePixelRatio at 2.
```

### Prompt 3 — voice loop with Gnani

```
Build api/voice/ with FastAPI + Pipecat. The browser sends 16 kHz mono PCM16 over WebSocket /ws/voice.
Pipeline: VAD → GnaniSTTService → orchestrator.handle(transcript, session) → GnaniTTSService (Timbre v2.5, voice per language)
→ audio back to the browser sentence by sentence. Support barge-in (user speaks → cancel TTS).
Emit JSON events to the client: partial_transcript, final_transcript, agent_text, state (listening|thinking|speaking),
level (RMS 0–1 every 50 ms). Add scripts/smoke_test.py doing one Kannada STT and one Kannada TTS call, saving out.wav.
Read GNANI_API_KEY from env, never send it to the client. If pipecat-gnani blocks you, fall back to plain websockets against
wss://api.vachana.ai/stt/v3/stream and wss://api.vachana.ai/api/v1/tts with header X-API-Key-ID.
```

### Prompt 4 — database

```
Write Supabase SQL migrations for: communities, residents, demand_requests (resident_id, product, qty, frequency, delivery_day,
language, status), vendors, vendor_offers (vendor_id, product, unit_price, delivery_charge, min_qty, valid_until, source, created_at),
negotiations (id, vendor_id, product, state, round, max_rounds), negotiation_events (append-only: negotiation_id, ts, actor, type,
payload jsonb), approvals (offer_id, admin_id, decision, note). Add RLS for resident and admin roles, Realtime on
negotiation_events and vendor_offers, and seed.sql with ONE synthetic community ‘Green Residency’ (120 households),
water-can demand totalling 360 per week, and three vendors (stubborn, friendly volume-hungry, cheap-but-slow).
All names and numbers fictional.
```

### Prompt 5 — demand collector

```
Implement the Resident Demand Collector using prompt 3A from the blueprint. Parse its JSON, keep session slots, and save a
demand_request only after the resident confirms the spelled-out quantity. Add aggregate_demand(community_id, product) returning
total weekly quantity and household count. Write tests with Kannada, Hindi, English and code-mixed transcripts.
Handle mis-heard numbers by re-asking.
```

### Prompt 6 — negotiation engine and Sim-Vendor

```
Implement api/negotiation/engine.py as a pure-Python state machine (ASK_QUOTE, COUNTER_1, COUNTER_2, FINAL, ESCALATE, WALK_AWAY).
counter_k = quote − (quote − target)·[0.6, 0.8, 1.0][k−1], never below target. It never accepts; it only marks an offer
eligible for admin approval when quote ≤ max_price. Each turn it returns a directive string for the LLM.
Wire the Negotiator prompt (3B) and Sim-Vendor prompt (3C) through the same orchestrator, one Timbre voice each,
so two agents can talk in text (fast tests) and in audio (demo). Validate every LLM-extracted offer against the engine and
reject numbers that do not appear in the transcript. Write 10 pytest cases, including a vendor who refuses, one who lies
about a competitor, and a quote above max_price.
```

### Prompt 7 — negotiation room and admin screens

```
Build the Negotiation Room and Admin Approval screens in the Hero’s glass-panel style (Poppins, white ink, lavender canvas,
orb on the right). Subscribe to Supabase Realtime on negotiation_events and vendor_offers. Negotiation Room: one glass card per
vendor with quote, delivery, round dots and an animated price ticker; two small orbs (NegoAI, Vendor) showing who is speaking.
Admin: total demand, best eligible offer, weekly savings versus the first quote (computed from stored numbers only),
risks (min qty, validity, delivery), and Approve (white fill) / Reject (outline) writing to approvals.
Small text on glass must be #3B1A5E.
```

### Prompt 8 — demo mode and submission pack

```
Add a ?demo=1 mode: preloaded synthetic community, a one-click ‘Start negotiation’ that runs NegoAI against the Sim-Vendor in Kannada
with English subtitles, a visible ‘Simulated vendor’ badge, and a ‘Powered by Gnani Prisma + Timbre’ footer. Add a /replay route
playing a stored negotiation from negotiation_events. Generate README.md with the architecture, which Gnani models are used and
where, the languages actually tested, a team contribution section, a Limitations section and an LLM-usage disclosure line.
```

## 5. 60-second demo shot list

- **0–8 s:** hero with the orb tumbling, hook line: ‘Why should 120 families haggle alone?’
- **8–20 s:** tap Mic, ask for water cans in Kannada, the orb stands up, transcript and confirm card appear.
- **20–40 s:** Negotiation room, NegoAI against the simulated vendor, ticker drops 22 → 20 → 19, English subtitles.
- **40–52 s:** admin screen, savings number, tap Approve.
- **52–60 s:** closing line, ‘Built with Gnani Prisma + Timbre’ and the hashtags the official rules require.

Rules: show the real app working, label the vendor as simulated, and never buy engagement.

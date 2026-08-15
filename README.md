# Omni Hotels AI Voice Agent — Aria

A LiveKit-based voice AI agent for **Omni Hotels & Resorts**, handling inbound guest support, reservations, loyalty questions, and career inquiries.

Built for the Regal AI Product Specialist take-home. Pivoted from ElevenLabs Agents to LiveKit for platform reliability.

## Architecture (at a glance)

```
Caller ──► LiveKit Room ──► Aria (single agent)
                              │
                              ├── STT: Deepgram (nova-3)
                              ├── LLM: OpenAI-compatible (GLM 4.5 via Baseten by default)
                              ├── TTS: ElevenLabs (Rachel voice by default)
                              ├── VAD: Silero
                              └── Tools:
                                   ├── get_weather   (Open-Meteo, no key)
                                   └── get_local_events (Ticketmaster Discovery)
```

**Single agent, no multi-agent workflow** — one comprehensive system prompt handles intent detection, capture flows, escalation, and personalization. The multi-node ElevenLabs workflow architecture proved unreliable in that platform; LiveKit's single-agent pattern is more robust for a demo build.

## Project structure

```
Omni-Hotels-AI-Agent/
├── agent.py             # LiveKit worker entrypoint
├── prompt.py            # Aria's consolidated system prompt (loads kb.txt)
├── tools.py             # get_weather + get_local_events function tools
├── kb.txt               # Omni knowledge base (~4,400 words, inlined into prompt)
├── pyproject.toml       # Python dependencies (managed with uv)
├── .env.example         # Copy to .env.local and fill in keys
└── docs/
    ├── kb_source.md         # Where the KB was scraped from
    └── test_scenarios.md    # 12-scenario test matrix for slide 3 metrics
```

## Setup — quick start

**Full step-by-step guide: [`docs/SETUP.md`](docs/SETUP.md)** (venv + pip flow, ~10 min end-to-end).

Short version:

### 1. Install dependencies

Using pip + venv (recommended):

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Or with uv:

```bash
uv sync
```

Requires **Python 3.10+**.

### 2. Configure environment

```bash
cp .env.example .env.local
```

Fill in:
- **`LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`** — from your LiveKit Cloud project
- **`DEEPGRAM_API_KEY`** — from [Deepgram console](https://console.deepgram.com/)
- **`LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`** — from Baseten (or swap for OpenAI proper)
- **`ELEVENLABS_API_KEY`** and optional **`ELEVENLABS_VOICE_ID`** — from ElevenLabs
- **`TICKETMASTER_API_KEY`** — free key from [developer.ticketmaster.com](https://developer.ticketmaster.com/)

### 3. Run locally in dev mode

Install the LiveKit CLI, authenticate, and run:

```bash
brew install livekit-cli   # macOS
lk cloud auth
lk agent dev
```

Hot-reload is on by default. (`python agent.py dev` still works but is deprecated.)

The agent connects to your LiveKit Cloud project and waits for room-join events. Use the LiveKit Cloud dashboard's **Agent Console** to talk to it, or spin up the Next.js frontend (below) for a shareable URL.

## Sharing with evaluators — deploy the Next.js frontend to Vercel

LiveKit's Sandbox playground is deprecated. To share the agent externally, deploy the [agent-starter-react](https://github.com/livekit-examples/agent-starter-react) frontend to Vercel with your LiveKit credentials.

Quick path:

```bash
git clone https://github.com/livekit-examples/agent-starter-react
cd agent-starter-react
```

Set these env vars on Vercel:
- `LIVEKIT_URL` (same as agent)
- `LIVEKIT_API_KEY` / `LIVEKIT_API_SECRET`

Deploy. Share the resulting Vercel URL with evaluators.

## Deploy the agent to LiveKit Cloud

```bash
lk cloud auth
lk agent create
```

This generates a `livekit.toml` and Dockerfile (if not present) and deploys to LiveKit Cloud. Free Build tier: 1,000 agent session minutes/month (plenty for the demo).

Monitor:
```bash
lk agent status
lk agent logs
```

## Testing

Run the 12-scenario matrix from [`docs/test_scenarios.md`](docs/test_scenarios.md). Log outcomes and roll up into slide 3 metrics (intent classification accuracy, containment rate, escalation precision).

## Design notes

- **Off-topic redirect** is intentionally non-enumerated: *"I'm not able to help with that one — but if there's anything about Omni I can help with, I'm here."* Enumerating categories ("your stay or careers") makes the redirect feel scripted.
- **Cancellation policy math** anchors on today's date first — the model speaks "today is X, arrival is Y, deadline is Z" so calendar reasoning is visible and self-checking.
- **VIP / anniversary mentions** during booking are captured as `special_requests`, NOT escalated. Aria never fabricates VIP packages (no champagne/chocolates/spa) since she has no data on real Omni offerings.
- **Frustration hair-trigger**: any explicit human request or frustration signal transfers immediately, no further capture, no negotiation.
- **Containment framing for slide 3**: capture-and-handoff is the intentional pattern given no PMS/payment integration in this demo. Production would add PMS integration and lift containment rate.

## Credentials the caller never provides

Aria will NOT ask for or accept: credit card numbers, passwords, SSNs, government ID. If offered: *"For your security, I don't take payment info over the phone — our specialist will handle that when they follow up."*

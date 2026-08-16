# Omni Hotels AI Voice Agent — Aria

A LiveKit-based voice AI agent for **Omni Hotels & Resorts**, handling inbound guest support, reservations, loyalty questions, and career inquiries.

Built for the Regal AI Product Specialist take-home. Pivoted from ElevenLabs Agents to LiveKit for platform reliability.

## 🎙 Try Aria live

**[https://omni-aria-frontend.vercel.app/](https://omni-aria-frontend.vercel.app/)**

Open the link, allow microphone access, click **Start**, and talk to Aria. Test scenarios to try are listed in [`docs/test_scenarios.md`](docs/test_scenarios.md).

> **⚠️ Cold-start note:** The agent runs on LiveKit Cloud's free Build tier, which spins down after periods of inactivity. **The very first call after a quiet stretch may take 15–30 seconds to connect** while the container boots. Subsequent calls in the same session are instant. If Aria doesn't greet you within ~30 seconds on a first-of-the-day connection, hang up and start a fresh session — the worker will be warm by then.

## Architecture (at a glance)

```
Caller ──► LiveKit Room ──► Aria (single agent)
                              │
                              ├── STT: Deepgram (nova-3)
                              ├── LLM: OpenAI-compatible (GLM 5.2 Fast via Baseten by default)
                              ├── TTS: ElevenLabs (Rachel voice by default)
                              ├── VAD: Silero + livekit turn-detector-v1
                              └── Tools:
                                   ├── EndCallTool         (LiveKit official — graceful hangup + room close)
                                   ├── verify_date         (Python calendar — deterministic weekday check)
                                   ├── log_caller_intent   (intent classification per call)
                                   ├── log_booking_capture / cancel / reschedule / escalation
                                   │                       (structured handoff data per action)
                                   ├── get_weather         (Open-Meteo, no key)
                                   └── get_local_events    (Ticketmaster Discovery)
```

**Single agent, no multi-agent workflow** — one comprehensive system prompt handles intent detection, capture flows, escalation, and personalization. The multi-node ElevenLabs workflow architecture proved unreliable in that platform; LiveKit's single-agent pattern is more robust for a demo build.

## Project structure

```
Omni-Hotels-AI-Agent/
├── agent.py                # LiveKit worker entrypoint
├── prompt.py               # Aria's consolidated system prompt (loads kb.txt)
├── tools.py                # end_call, verify_date, log_caller_intent,
│                           # log_*_capture, get_weather, get_local_events
├── kb.txt                  # Omni knowledge base (~4,400 words, inlined into prompt)
├── requirements.txt        # pip-installable dependencies
├── pyproject.toml          # uv-friendly dependency spec
├── Dockerfile              # Container image for LiveKit Cloud deployment
├── .env.example            # Copy to .env.local and fill in keys
├── docs/
│   ├── SETUP.md                # End-to-end setup + deploy walkthrough
│   ├── frontend_deploy.md      # Next.js frontend deploy to Vercel
│   ├── kb_source.md            # Where the KB was scraped from
│   ├── test_scenarios.md       # 14-scenario test matrix
│   └── test_metrics.md         # Running observations + slide 3/4/5 talking points
├── sessions/               # Per-scenario session bundles from LiveKit
│   ├── README.md               # Bundle format + rollup instructions
│   └── NN_slug/                # One folder per scenario, holds:
│       ├── p_..._audio.oga         # Full call audio
│       ├── p_..._chat_history.json # Turn-by-turn transcript
│       ├── p_..._logs.json         # OTel logs (intent + capture lines)
│       ├── p_..._metrics.json      # OTel metrics (latency histograms)
│       └── p_..._traces.json       # Tool call traces
└── scripts/
    └── rollup_metrics.py   # Reads all session bundles, prints aggregated stats
```

## Test data & results

All test evidence lives in the repo:

- **[`docs/test_scenarios.md`](docs/test_scenarios.md)** — the 14-scenario test matrix (caller script + expected behavior per scenario)
- **[`docs/test_metrics.md`](docs/test_metrics.md)** — running observations, per-scenario pass/fail, latency flags, and the pre-drafted slide 3 / 4 / 5 talking points
- **[`sessions/NN_*/`](sessions/)** — full session bundle per scenario, downloaded from LiveKit Cloud:
  - `audio.oga` (full call recording)
  - `chat_history.json` (turn-by-turn transcript)
  - `logs.json` (OpenTelemetry logs including `CALLER_INTENT=` and `CAPTURE=` lines)
  - `metrics.json` (OTel metrics including e2e latency, TTFT, TTFB, token usage)
  - `traces.json` (detailed tool-call and speech-event traces)

To regenerate aggregated stats across all session bundles:

```bash
python scripts/rollup_metrics.py
```

Output includes per-scenario latency (min/avg/max), median LLM TTFT, median TTS TTFB, intent distribution, and structured-capture counts by type.

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

Run the 14-scenario matrix from [`docs/test_scenarios.md`](docs/test_scenarios.md). For each scenario, download the session bundle from the LiveKit Cloud dashboard (Sessions → the session → Download), unzip into `sessions/NN_slug/`, then run:

```bash
python scripts/rollup_metrics.py
```

The script produces a table of per-scenario latency + intent + capture counts, plus aggregated medians for slide 3. See [`sessions/README.md`](sessions/README.md) for details on the bundle format.

## Design notes

- **Off-topic redirect** is intentionally non-enumerated: *"I'm not able to help with that one — but if there's anything about Omni I can help with, I'm here."* Enumerating categories ("your stay or careers") makes the redirect feel scripted.
- **Cancellation policy math** anchors on today's date first — the model speaks "today is X, arrival is Y, deadline is Z" so calendar reasoning is visible and self-checking.
- **VIP / anniversary mentions** during booking are captured as `special_requests`, NOT escalated. Aria never fabricates VIP packages (no champagne/chocolates/spa) since she has no data on real Omni offerings.
- **Frustration hair-trigger**: any explicit human request or frustration signal transfers immediately, no further capture, no negotiation.
- **Containment framing for slide 3**: capture-and-handoff is the intentional pattern given no PMS/payment integration in this demo. Production would add PMS integration and lift containment rate.

## Credentials the caller never provides

Aria will NOT ask for or accept: credit card numbers, passwords, SSNs, government ID. If offered: *"For your security, I don't take payment info over the phone — our specialist will handle that when they follow up."*

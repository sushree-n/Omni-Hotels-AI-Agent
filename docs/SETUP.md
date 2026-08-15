# End-to-End Setup — Aria Voice Agent

From zero to a running agent, using pip + venv (no uv needed).

## Prerequisites

- **Python 3.10+** (check with `python3 --version`)
- **LiveKit Cloud project** created — you have this
- Accounts + API keys for:
  - LiveKit Cloud (`LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`)
  - Deepgram (`DEEPGRAM_API_KEY`) — [console.deepgram.com](https://console.deepgram.com/)
  - Baseten (`LLM_API_KEY` + your model deployment URL)
  - ElevenLabs (`ELEVENLABS_API_KEY`) — Scale tier
  - Ticketmaster Discovery API (`TICKETMASTER_API_KEY`) — [developer.ticketmaster.com](https://developer.ticketmaster.com/)

---

## Step 1 — Clone/enter the project

```bash
cd ~/Desktop/Sushree/regal-takehome/Regal/Omni-Hotels-AI-Agent
```

## Step 2 — Create and activate a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

You should see `(.venv)` prepended to your prompt.

To deactivate later: `deactivate`.

## Step 3 — Install dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

This installs LiveKit Agents 1.x with the openai, deepgram, elevenlabs, and silero plugins, plus `python-dotenv` and `aiohttp` for env loading and HTTP calls.

## Step 4 — Configure environment variables

```bash
cp .env.example .env.local
```

Open `.env.local` in your editor and fill in every value. Key notes:

### LiveKit Cloud

In your LiveKit Cloud dashboard:
- `LIVEKIT_URL`: found on the project overview page — looks like `wss://your-project.livekit.cloud`
- `LIVEKIT_API_KEY` and `LIVEKIT_API_SECRET`: **Settings → Keys** — create a new key if you don't have one

### Baseten (LLM)

In your Baseten dashboard, open the specific model deployment you want to use (GLM 4.5 Fast, Kimi K2, or DeepSeek V3.1):
- `LLM_BASE_URL`: on your model deployment page, look for the OpenAI-compatible endpoint. It's typically `https://inference.baseten.co/v1` OR a per-deployment URL like `https://model-xxxxxx.api.baseten.co/environments/production/sync/v1`. **Copy the exact value.**
- `LLM_API_KEY`: your Baseten API key from account settings
- `LLM_MODEL`: the exact model identifier from Baseten (e.g., `zai-org/GLM-4.5-Air`). Case-sensitive. **Check the Baseten model page for the exact string.**

If unsure which URL format to use, test it with a quick curl:

```bash
curl -X POST "$LLM_BASE_URL/chat/completions" \
  -H "Authorization: Bearer $LLM_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model": "'$LLM_MODEL'", "messages": [{"role":"user","content":"hi"}]}'
```

A `200` with a completion in the response means your URL + model + key are correct.

### Deepgram / ElevenLabs / Ticketmaster

- `DEEPGRAM_API_KEY`: create a key at [console.deepgram.com](https://console.deepgram.com/) → API Keys
- `ELEVENLABS_API_KEY`: from ElevenLabs → Profile → API Keys
- `ELEVENLABS_VOICE_ID`: the default `21m00Tcm4TlvDq8ikWAM` is Rachel. To pick a different voice, browse [ElevenLabs Voice Library](https://elevenlabs.io/app/voice-library) and copy any voice's ID.
- `TICKETMASTER_API_KEY`: create a Ticketmaster developer account → create an app → copy the Consumer Key

## Step 5 — Verify env is loaded correctly

Quick sanity check:

```bash
python3 -c "from dotenv import load_dotenv; import os; load_dotenv('.env.local'); print('LiveKit:', bool(os.environ.get('LIVEKIT_URL'))); print('LLM:', bool(os.environ.get('LLM_API_KEY'))); print('Deepgram:', bool(os.environ.get('DEEPGRAM_API_KEY'))); print('ElevenLabs:', bool(os.environ.get('ELEVENLABS_API_KEY'))); print('Ticketmaster:', bool(os.environ.get('TICKETMASTER_API_KEY')))"
```

All five should print `True`. If any is `False`, that env var isn't set in `.env.local`.

## Step 6 — Run the agent locally

First, install the LiveKit CLI (you'll need it here AND for deployment):

```bash
brew install livekit-cli    # macOS
# or download from https://github.com/livekit/livekit-cli/releases
```

Authenticate once:

```bash
lk cloud auth
```

Then run the agent in dev mode with hot-reload:

```bash
lk agent dev
```

You should see log output like:

```
INFO livekit.agents - starting worker { ... }
INFO omni-aria - Aria session starting ...
```

The agent is now connected to your LiveKit Cloud project and waiting for a caller. Any code changes hot-reload automatically.

**Note:** `python agent.py dev` still works but is deprecated. Use `lk agent dev` going forward.

## Step 7 — Talk to the agent

You have two options for testing locally:

### Option A: LiveKit Cloud Agent Console (fastest — no frontend needed)

1. Open [cloud.livekit.io](https://cloud.livekit.io/) → your project → **Agents** tab → **Agent Console**
2. Click **Start** or **Connect** to open a mic-enabled test session
3. Talk to Aria — she should respond with the greeting

### Option B: LiveKit Sandbox / Local Frontend

If the Agent Console doesn't give you the interaction quality you want, spin up the Next.js starter locally:

```bash
git clone https://github.com/livekit-examples/agent-starter-react
cd agent-starter-react
cp .env.example .env.local  # fill in your LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET
npm install
npm run dev
```

Open http://localhost:3000 and talk to Aria.

## Step 8 — Run the test scenarios

Open [`docs/test_scenarios.md`](test_scenarios.md), read the 12 scenarios, and run each one. Log outcomes for slide 3.

## Step 9 — Deploy to LiveKit Cloud

Once local testing looks good, deploy the agent to LiveKit Cloud so it's always running and reachable by evaluators (not tied to your laptop). You already installed the CLI and authenticated in Step 6.

### 9a. Deploy the agent

The project already includes a **Dockerfile** and **.dockerignore** — LiveKit will use them to build a container image. The first deploy generates a `livekit.toml` file with your agent config.

```bash
lk agent create --secrets-file .env.local
```

The `--secrets-file .env.local` flag copies every `KEY=value` in `.env.local` into LiveKit Cloud's encrypted secrets store, so the deployed agent has all its API keys (LLM, Deepgram, ElevenLabs, Ticketmaster, etc.).

First deployment takes ~2-5 min (Docker build + upload).

### 9b. Verify

```bash
lk agent status   # shows deployment status, replica count
lk agent logs     # live tail of agent logs — leave running while you test
```

### 9c. Test the deployed agent

Open [cloud.livekit.io](https://cloud.livekit.io/) → your project → **Agents** tab → **Agent Console**. Connect — the deployed agent picks up the session instead of your local process.

### 9d. Updating after code changes

```bash
lk agent deploy                                     # rebuild + redeploy code
lk agent update-secrets --secrets-file .env.local   # update env vars only (no rebuild)
```

Free **Build tier** limits: 1,000 agent session minutes per month. Plenty for demo + evaluator testing.

## Step 10 — Share with evaluators

For a public URL evaluators can visit:

```bash
git clone https://github.com/livekit-examples/agent-starter-react
cd agent-starter-react
```

Push to your GitHub, connect to Vercel, add the LiveKit env vars in Vercel's dashboard, deploy. The Vercel URL (e.g., `omni-aria.vercel.app`) is what you send to evaluators.

---

## Troubleshooting

**Agent starts but nothing happens when I connect:**
Check the agent process logs — you should see a "job assigned" message when someone connects. If not, verify `LIVEKIT_URL` matches your project.

**LLM turns are slow or return errors:**
Verify the Baseten endpoint with the curl in Step 4. Also check `LLM_MODEL` matches exactly what Baseten expects (case-sensitive slug).

**TTS sounds wrong / robotic:**
Try a different `ELEVENLABS_VOICE_ID`. Rachel (`21m00Tcm4TlvDq8ikWAM`) is a good default but voice preference is subjective.

**Tools aren't invoked:**
Check the agent logs for tool-call traces. If Aria never invokes `get_weather` or `get_local_events`, the LLM may not be picking up the tool descriptions — try switching to a stronger LLM temporarily (e.g., OpenAI GPT-4o) to verify the code path works, then swap back.

**"Module not found" errors:**
Make sure your venv is activated (`source .venv/bin/activate`) — the `(.venv)` prefix should be visible in your prompt.

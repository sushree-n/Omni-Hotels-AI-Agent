# Test Session Recordings & Metrics

One subfolder per test scenario (`01_info_nashville_checkin/`, `02_info_wifi_not_in_kb/`, etc). Each subfolder holds the full session bundle downloaded from LiveKit Cloud.

## Bundle contents (as downloaded, leave named as-is)

LiveKit prefixes every file with `p_<project_id>_RM_<room_id>_`:

- `p_<...>_audio.oga` — full call audio
- `p_<...>_chat_history.json` — turn-by-turn transcript
- `p_<...>_logs.json` — OpenTelemetry log records
  - Includes our custom `CALLER_INTENT=...` and `CAPTURE={...}` lines
  - Plus LiveKit's per-turn STT / LLM / TTS / EOU metric log lines
- `p_<...>_metrics.json` — OpenTelemetry metrics (e2e latency histograms, TTFB/TTFT, usage sums)
- `p_<...>_traces.json` — detailed tool call traces + speech events
- `notes.md` (optional, add manually) — observations, pass/fail, any issues

## How to download from LiveKit

1. LiveKit Cloud → your project → **Sessions**
2. Click into the session you just ran
3. Look for a **Download** button
4. Unzip into the matching `sessions/NN_slug/` folder

The `scripts/rollup_metrics.py` helper finds files by their `_logs.json` / `_metrics.json` suffix — you don't need to rename anything.

## Rolling up metrics for slide 3

```bash
python scripts/rollup_metrics.py
```

Output includes per-scenario table (turns, intents, captures, e2e latency min/avg/max) plus aggregated totals (median LLM TTFT, median TTS TTFB, total tokens, intent distribution).

Screenshot the output → slide 3 evidence.

## Folder naming convention

`NN_short_slug/` where NN is the scenario number from [`docs/test_scenarios.md`](../docs/test_scenarios.md).

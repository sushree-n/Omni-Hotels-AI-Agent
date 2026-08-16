#!/usr/bin/env python3
"""Roll up test session metrics for slide 3.

Reads the LiveKit-downloaded session bundles from `sessions/NN_slug/` and
prints an aggregated summary suitable for slide 3.

Handles the actual bundle filename pattern from LiveKit Cloud:
    p_<project_id>_RM_<room_id>_logs.json      (OpenTelemetry log records)
    p_<project_id>_RM_<room_id>_metrics.json   (OpenTelemetry metrics)
    p_<project_id>_RM_<room_id>_chat_history.json
    p_<project_id>_RM_<room_id>_traces.json
    p_<project_id>_RM_<room_id>_audio.oga

Usage:
    python scripts/rollup_metrics.py
"""

from __future__ import annotations

import json
import re
import statistics
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
SESSIONS_DIR = REPO_ROOT / "sessions"

INTENT_RE = re.compile(r"CALLER_INTENT=([a-z_]+)\s*\|\s*reason=(.*)")
CAPTURE_RE = re.compile(r"CAPTURE=(\{.*\})")


def _find_bundle_file(session_dir: Path, suffix: str) -> Path | None:
    """Return the first file in `session_dir` whose name ends with `_<suffix>.json`.

    Handles LiveKit's `p_<project>_RM_<room>_<suffix>.json` naming.
    """
    matches = sorted(session_dir.glob(f"*_{suffix}.json"))
    return matches[0] if matches else None


def _get_attr(record: dict, key: str) -> Any:
    """Pull an attribute value out of an OpenTelemetry attributes array."""
    for a in record.get("attributes", []) or []:
        if a.get("key") == key:
            v = a.get("value", {})
            return v.get("stringValue") or v.get("intValue") or v.get("doubleValue")
    return None


def parse_logs(logs_path: Path) -> dict:
    """Walk the OTel resourceLogs structure and pull custom intents/captures
    plus LLM/STT/TTS/EOU metric log lines.
    """
    out: dict[str, Any] = {
        "intents": [],
        "intent_reasons": [],
        "captures": [],
        "llm_ttft_seconds": [],
        "llm_prompt_tokens": [],
        "llm_completion_tokens": [],
        "tts_ttfb_seconds": [],
        "tts_audio_seconds": [],
        "stt_audio_seconds": [],
        "eou_delay_seconds": [],
    }
    if not logs_path or not logs_path.exists():
        return out

    data = json.loads(logs_path.read_text())
    for resource in data.get("resourceLogs", []) or []:
        for scope in resource.get("scopeLogs", []) or []:
            for record in scope.get("logRecords", []) or []:
                body = record.get("body", {}).get("stringValue", "") or ""

                # Custom intent + capture logs
                m = INTENT_RE.search(body)
                if m:
                    out["intents"].append(m.group(1))
                    out["intent_reasons"].append(m.group(2).strip())
                    continue
                m = CAPTURE_RE.search(body)
                if m:
                    try:
                        out["captures"].append(eval(m.group(1)))
                    except Exception:
                        pass
                    continue

                # LiveKit per-turn metric lines carry data in attributes
                if body == "LLM metrics":
                    ttft = _get_attr(record, "ttft")
                    if ttft is not None:
                        out["llm_ttft_seconds"].append(float(ttft))
                    p_tok = _get_attr(record, "prompt_tokens")
                    if p_tok is not None:
                        out["llm_prompt_tokens"].append(int(p_tok))
                    c_tok = _get_attr(record, "completion_tokens")
                    if c_tok is not None:
                        out["llm_completion_tokens"].append(int(c_tok))
                elif body == "TTS metrics":
                    ttfb = _get_attr(record, "ttfb")
                    if ttfb is not None:
                        out["tts_ttfb_seconds"].append(float(ttfb))
                    dur = _get_attr(record, "audio_duration")
                    if dur is not None:
                        out["tts_audio_seconds"].append(float(dur))
                elif body == "STT metrics":
                    dur = _get_attr(record, "audio_duration")
                    if dur is not None:
                        out["stt_audio_seconds"].append(float(dur))
                elif body == "EOU metrics":
                    delay = _get_attr(record, "end_of_utterance_delay")
                    if delay is not None:
                        out["eou_delay_seconds"].append(float(delay))
    return out


def parse_metrics(metrics_path: Path) -> dict:
    """Extract e2e turn latency + usage sums from the metrics.json histogram data."""
    out: dict[str, Any] = {
        "e2e_latency_min": None,
        "e2e_latency_max": None,
        "e2e_latency_avg": None,
        "e2e_latency_count": 0,
        "e2e_latency_sum": 0.0,
    }
    if not metrics_path or not metrics_path.exists():
        return out

    data = json.loads(metrics_path.read_text())
    e2e_sums: list[float] = []
    e2e_counts: list[int] = []
    mins: list[float] = []
    maxs: list[float] = []
    for resource in data.get("resourceMetrics", []) or []:
        for scope in resource.get("scopeMetrics", []) or []:
            for metric in scope.get("metrics", []) or []:
                if metric.get("name") != "lk.agents.turn.e2e_latency":
                    continue
                for dp in metric.get("histogram", {}).get("dataPoints", []) or []:
                    e2e_sums.append(float(dp.get("sum", 0) or 0))
                    e2e_counts.append(int(dp.get("count", 0) or 0))
                    if dp.get("min") is not None:
                        mins.append(float(dp["min"]))
                    if dp.get("max") is not None:
                        maxs.append(float(dp["max"]))

    total_sum = sum(e2e_sums)
    total_count = sum(e2e_counts)
    out["e2e_latency_sum"] = round(total_sum, 3)
    out["e2e_latency_count"] = total_count
    if total_count:
        out["e2e_latency_avg"] = round(total_sum / total_count, 3)
    if mins:
        out["e2e_latency_min"] = round(min(mins), 3)
    if maxs:
        out["e2e_latency_max"] = round(max(maxs), 3)
    return out


def summarise_session(session_dir: Path) -> dict:
    logs = parse_logs(_find_bundle_file(session_dir, "logs"))
    metrics = parse_metrics(_find_bundle_file(session_dir, "metrics"))
    return {
        "scenario": session_dir.name,
        **logs,
        **metrics,
    }


def _fmt(v: Any) -> str:
    if v is None:
        return "-"
    if isinstance(v, float):
        return f"{v:.2f}"
    return str(v)


def main() -> None:
    if not SESSIONS_DIR.exists():
        print(f"No sessions directory at {SESSIONS_DIR}")
        return

    session_dirs = sorted(
        d for d in SESSIONS_DIR.iterdir()
        if d.is_dir() and not d.name.startswith(".") and d.name != "__pycache__"
    )

    per_session = []
    for d in session_dirs:
        has_data = (
            _find_bundle_file(d, "logs") is not None
            or _find_bundle_file(d, "metrics") is not None
        )
        if not has_data:
            print(f"[skip] {d.name}: no bundle files yet")
            continue
        per_session.append(summarise_session(d))

    if not per_session:
        print(
            "\nNo populated sessions found. "
            "Download session bundles from LiveKit and drop them into sessions/NN_slug/."
        )
        return

    print(f"\nFound {len(per_session)} populated session(s).\n")

    # Per-session table
    print(
        f"{'Scenario':<40} "
        f"{'Turns':>5} "
        f"{'Intents':<25} "
        f"{'Captures':<20} "
        f"{'E2E min':>7} "
        f"{'E2E avg':>7} "
        f"{'E2E max':>7}"
    )
    print("-" * 116)
    for s in per_session:
        intents_str = ",".join(s["intents"]) if s["intents"] else "-"
        capture_types = [c.get("capture_type", "?") for c in s["captures"]]
        captures_str = ",".join(capture_types) if capture_types else "-"
        print(
            f"{s['scenario']:<40} "
            f"{s['e2e_latency_count']:>5} "
            f"{intents_str[:25]:<25} "
            f"{captures_str[:20]:<20} "
            f"{_fmt(s['e2e_latency_min']):>7} "
            f"{_fmt(s['e2e_latency_avg']):>7} "
            f"{_fmt(s['e2e_latency_max']):>7}"
        )

    # Aggregate
    all_ttft = [v for s in per_session for v in s["llm_ttft_seconds"]]
    all_tts_ttfb = [v for s in per_session for v in s["tts_ttfb_seconds"]]
    all_eou = [v for s in per_session for v in s["eou_delay_seconds"]]
    total_prompt_tok = sum(sum(s["llm_prompt_tokens"]) for s in per_session)
    total_completion_tok = sum(sum(s["llm_completion_tokens"]) for s in per_session)
    total_stt_seconds = sum(sum(s["stt_audio_seconds"]) for s in per_session)
    total_tts_seconds = sum(sum(s["tts_audio_seconds"]) for s in per_session)
    total_turns = sum(s["e2e_latency_count"] for s in per_session)
    total_intents_logged = sum(len(s["intents"]) for s in per_session)
    total_captures_logged = sum(len(s["captures"]) for s in per_session)

    print("\n=== Aggregated across all sessions ===")
    print(f"Total sessions:             {len(per_session)}")
    print(f"Total turns:                {total_turns}")
    print(f"Median LLM TTFT (s):        {statistics.median(all_ttft):.2f}" if all_ttft else "Median LLM TTFT (s):        -")
    print(f"Median TTS TTFB (s):        {statistics.median(all_tts_ttfb):.2f}" if all_tts_ttfb else "Median TTS TTFB (s):        -")
    print(f"Median EOU delay (s):       {statistics.median(all_eou):.2f}" if all_eou else "Median EOU delay (s):       -")
    print(f"Total LLM prompt tokens:    {total_prompt_tok:,}")
    print(f"Total LLM output tokens:    {total_completion_tok:,}")
    print(f"Total STT audio (s):        {total_stt_seconds:.1f}")
    print(f"Total TTS audio (s):        {total_tts_seconds:.1f}")
    print(f"Total intent logs:          {total_intents_logged}")
    print(f"Total capture logs:         {total_captures_logged}")

    # Intent distribution
    all_intents = [i for s in per_session for i in s["intents"]]
    intent_counts: dict[str, int] = {}
    for i in all_intents:
        intent_counts[i] = intent_counts.get(i, 0) + 1
    if intent_counts:
        print("\n=== Intent distribution ===")
        for intent, count in sorted(intent_counts.items(), key=lambda x: -x[1]):
            print(f"  {intent:<20} {count}")

    # Capture types
    all_capture_types = [
        c.get("capture_type", "?") for s in per_session for c in s["captures"]
    ]
    capture_counts: dict[str, int] = {}
    for t in all_capture_types:
        capture_counts[t] = capture_counts.get(t, 0) + 1
    if capture_counts:
        print("\n=== Structured captures by type ===")
        for t, count in sorted(capture_counts.items(), key=lambda x: -x[1]):
            print(f"  {t:<25} {count}")


if __name__ == "__main__":
    main()

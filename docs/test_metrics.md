# Test Metrics Log

Running log of test observations for slide 3 / slide 4. Populate as scenarios are run.

## Latency observations

| Scenario | Turn / operation | Latency | Note |
|---|---|---|---|
| 3 (Nashville property overview) | Info FAQ retrieval + response | **5.93s** | Higher than voice-UX ideal (~2s). Contributor: long KB context inline in system prompt + GLM 5.2 Fast reasoning through it. Worth flagging as a production improvement opportunity — two-tier LLM routing (fast model for info FAQ, stronger model for capture flows) would cut this. |

## Scenario pass/fail (final)

| # | Scenario | Result | Notes |
|---|---|---|---|
| 1 | Info FAQ (in KB) — check-in time | ✅ Pass | |
| 2 | Info FAQ (not in KB) — wifi password | ✅ Pass | Correctly redirects to property phone, no KB mention |
| 3 | Property overview (Nashville) | ✅ Pass | High latency: 5.93s (flagged for slide 4) |
| 4 | Off-topic redirect | ✅ Pass | Exact non-enumerated line |
| 5 | Simple booking with tools | ✅ Pass | Events opt-in question fired correctly after fix |
| 6 | Date mismatch flag | ✅ Pass | Fixed via mandatory `verify_date` tool — Python computes weekday, LLM doesn't |
| 7 | Date match — silent verification | ✅ Pass | No performative "let me verify" announcement |
| 8 | Cancellation with policy math | ✅ Pass | Policy math grounded via calendar reference + verify_date |
| 9 | Escalation — group booking 10+ | ✅ Pass | Correctly routed despite word "book" in caller's opener |
| 10 | Frustration hair-trigger | ✅ Pass | Immediate transfer, no continued capture |
| 11 | Intent shift (info → booking) | ✅ Pass | Multi-intent logged with two `log_caller_intent` calls |
| 12 | Intent shift (booking → cancellation) | ✅ Pass | Same pattern, pivoted cleanly |
| 13 | Events opt-in — explicit ask | ✅ Pass | Mandatory question fires; tool called silently after opt-in |
| 14 | Events declined | ✅ Pass | No tool invocation, drops the thread |

**Final tally: 14/14 pass.**

## Slide 3 metric buckets (roll up when all scenarios done)

- **Intent classification accuracy**: correct classifications / total = TBD
- **Containment rate**: contained (info + off-topic + career FAQ) / total, excluding scenarios that SHOULD escalate = TBD
- **Escalation precision**: correct escalations / total escalations = TBD
- **Personalization trigger accuracy**: appropriate tool invocations / opportunities = TBD
- **Median LLM latency per turn**: TBD (session summaries in lk agent logs report this)

## Slide 4 talking points (build as tests reveal them)

- Latency on info-heavy responses hits ~6s occasionally. Voice UX starts feeling laggy past 3s. Production would use a two-tier LLM setup.
- Multi-intent handling in single-agent architecture is natively supported — no complex routing needed vs. workflow-based agents.
- Date verification via injected calendar table is reliable in tests (vs. LLM computing weekdays in-head, which is unreliable).

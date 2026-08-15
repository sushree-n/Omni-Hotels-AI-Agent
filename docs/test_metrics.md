# Test Metrics Log

Running log of test observations for slide 3 / slide 4. Populate as scenarios are run.

## Latency observations

| Scenario | Turn / operation | Latency | Note |
|---|---|---|---|
| 3 (Nashville property overview) | Info FAQ retrieval + response | **5.93s** | Higher than voice-UX ideal (~2s). Contributor: long KB context inline in system prompt + GLM 5.2 Fast reasoning through it. Worth flagging as a production improvement opportunity — two-tier LLM routing (fast model for info FAQ, stronger model for capture flows) would cut this. |

## Scenario pass/fail (running)

| # | Scenario | Result | Notes |
|---|---|---|---|
| 1 | Info FAQ (in KB) — check-in time | ✅ Pass | |
| 2 | Info FAQ (not in KB) — wifi password | ✅ Pass | Correctly redirects to property phone, no KB mention |
| 3 | Property overview (Nashville) | ✅ Pass | High latency: 5.93s |
| 4 | Off-topic redirect | ✅ Pass | Exact non-enumerated line |
| 5 | Simple booking with tools | ✅ Pass | Intent logging missed — fixed with mandatory rule |

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

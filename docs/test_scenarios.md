# Test Scenarios — Aria

12-scenario matrix for evaluating the agent. Log outcomes in the results column and roll up into slide 3 metrics.

## Metrics tracked

- **Intent classification accuracy**: did Aria correctly identify what the caller wanted? (target 90%+)
- **Containment rate**: % of calls resolved without transfer, excluding scenarios that SHOULD transfer (target 65-75%)
- **Escalation precision**: when an escalation happened, was it correct? (target 100%)
- **Personalization trigger accuracy**: did Aria proactively invoke a tool when appropriate?

## Scenarios

| # | Caller script | Intent | Expected behavior | Result |
|---|---|---|---|---|
| 1 | *"Hi, can you tell me about check-in times and parking at your Nashville property?"* | info_faq | KB retrieval, 2-3 sentence answer, no filler tail, clean close on goodbye | |
| 2 | *"I'm staying at Berkshire in room 205 — what's the wifi password?"* | info_faq (not-in-KB) | Aria says "I don't have that specific info — call the property directly at (212) 753-5800". No fabricated welcome-packet guidance. | |
| 3 | *"What are the check-in times at Nashville? Actually, just get me a real person."* | info → escalation | Answer, then hair-trigger escalation. Capture name + phone + reason. End cleanly. | |
| 4 | *"I'd like to book a room at your New York property from August 20-22 for two guests."* | new_booking | One-field-at-a-time capture. Weather + events tool invocation. Intent-framed read-back. Handoff line + end_call. | |
| 5 | *"I want to book Berkshire for August 22-24 for two — it's our tenth anniversary. Any VIP packages?"* | new_booking with anniversary | Warmly acknowledge anniversary, log as special_requests, continue booking. Do NOT fabricate VIP packages. | |
| 6 | *"Cancel my Scottsdale reservation, confirmation ABC12345, arriving this Friday."* | cancellation | Show math: today's date → arrival day → policy rule → deadline → outcome. Fields captured. Handoff + end. | |
| 7 | *"Cancel my Scottsdale reservation, confirmation XYZ98765, arriving August 25."* | cancellation | Math shows deadline still ahead, reassures caller no charge. Handoff. | |
| 8 | *"I need to change my Nashville stay. Confirmation LMN45678, moving from August 20 to August 27."* | reschedule | Capture flow, intent-framed read-back, handoff. | |
| 9 | *"We want to host a corporate offsite at Nashville — 30 rooms."* | escalation (group 10+) | Routes to escalation despite word "book". Captures minimal fields. Handoff. | |
| 10 | *"I want to speak to a manager about a charge on my Boston stay — never got a refund."* | escalation (billing dispute) | Empathy first. Captures name + phone + reason + property + dates. Handoff. | |
| 11 | *"Can you book me a flight from New York to Nashville?"* | out_of_scope | Exact line: *"I'm not able to help with that one — but if there's anything about Omni I can help with, I'm here."* No route. | |
| 12 | Booking flow, then mid-capture say *"Ugh, this is taking forever. Just get me a real person."* | frustration hair-trigger | Immediately stops capture, warm empathetic transfer with partial data. | |

## Stretch tests

| # | Caller script | Expected |
|---|---|---|
| 13 | *"Book Berkshire for Sunday August 24, staying two nights."* (Aug 24 is a Monday) | Aria catches the day-of-week mismatch and asks the caller to clarify. |
| 14 | *"Book Nashville August 22-24 for two."* | Verify `get_weather` and `get_local_events` are actually invoked; check they're woven into the response naturally. |
| 15 | *"Do you have internships?"* → *"Actually I applied last week, can you check my status?"* | First question answered from KB. Second gets directed to careers@omnihotels.com. |

## How to run

1. Start the agent locally: `uv run python agent.py dev`
2. Open the LiveKit Agent Playground (or your Next.js frontend if deployed) and connect
3. Speak each scenario, log outcome
4. Roll up metrics for slide 3

"""Function tools for Aria.

- end_call: gracefully hang up after farewell/transfer line
- get_weather: Open-Meteo forecast (no API key required)
- get_local_events: Ticketmaster Discovery events (needs TICKETMASTER_API_KEY)
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import date, datetime, timezone
from typing import Any

import aiohttp
from livekit.agents import RunContext, function_tool, get_job_context

logger = logging.getLogger("omni-aria.tools")

# Property city → (latitude, longitude) for weather lookups
PROPERTY_COORDINATES: dict[str, tuple[float, float]] = {
    "nashville": (36.1627, -86.7816),
    "scottsdale": (33.5722, -111.9483),
    "washington dc": (38.9280, -77.0576),
    "dc": (38.9280, -77.0576),
    "washington": (38.9280, -77.0576),
    "new york": (40.7580, -73.9772),  # Omni Berkshire Place, Midtown
    "berkshire": (40.7580, -73.9772),
}

# Property city aliases → normalized Ticketmaster city query
CITY_ALIASES: dict[str, str] = {
    "scottsdale": "Scottsdale",
    "nashville": "Nashville",
    "washington dc": "Washington",
    "dc": "Washington",
    "washington": "Washington",
    "new york": "New York",
    "berkshire": "New York",
}


def _normalize_city(city: str) -> str:
    return city.strip().lower()


ALLOWED_INTENTS = {
    "info_faq",
    "new_booking",
    "cancellation",
    "reschedule",
    "escalation",
    "out_of_scope",
}


@function_tool
async def verify_date(
    context: RunContext,
    iso_date: str,
    claimed_weekday: str = "",
) -> dict[str, Any]:
    """Return the actual day of week for a given date, and flag mismatches.

    You MUST call this SILENTLY for every date the caller mentions (arrival,
    checkout, cancellation arrival, reschedule dates). The tool returns the
    ground truth from Python's calendar — do NOT compute weekdays in your head.

    Args:
        iso_date: The date in ISO format, YYYY-MM-DD (e.g., "2026-08-22").
        claimed_weekday: If the caller stated a specific day of week
                         ("Friday August 22"), pass that here (e.g., "Friday").
                         Leave empty if they only said the date.

    Returns:
        - actual_weekday: the real weekday (e.g., "Saturday")
        - matches_claim: True if claimed_weekday matches, False if mismatch,
                         None if no claim
        - is_past: True if the date is in the past
        - days_from_today: integer, negative if past, positive if future

    Use the result:
    - If matches_claim=True → say NOTHING about verification, proceed silently
    - If matches_claim=False → warmly flag: "Just to double check — August
      twenty-second is actually a Saturday, not a Friday. Did you mean..."
    - If is_past=True → flag: "Just to check — that date is in the past..."
    """
    try:
        target = date.fromisoformat(iso_date)
    except ValueError:
        return {"error": f"Invalid date format: {iso_date}. Expected YYYY-MM-DD."}

    today = datetime.now(timezone.utc).astimezone().date()
    actual_weekday = target.strftime("%A")
    days_from_today = (target - today).days

    matches_claim: bool | None
    if claimed_weekday.strip():
        matches_claim = actual_weekday.lower() == claimed_weekday.strip().lower()
    else:
        matches_claim = None

    result = {
        "iso_date": iso_date,
        "actual_weekday": actual_weekday,
        "claimed_weekday": claimed_weekday or None,
        "matches_claim": matches_claim,
        "is_past": days_from_today < 0,
        "is_far_future": days_from_today > 365,
        "days_from_today": days_from_today,
    }
    logger.info("verify_date: %s", result)
    return result


@function_tool
async def log_caller_intent(
    context: RunContext,
    intent: str,
    brief_reason: str,
) -> str:
    """Log the caller's currently-detected intent for post-call analysis.

    Call this ONCE when you first classify the caller's intent, and AGAIN
    every time the caller SHIFTS to a different intent (e.g., info question
    → booking → cancel). A single call can have multiple intent logs.

    Do NOT call this repeatedly for the same intent — only log when a new
    or changed intent is detected.

    Args:
        intent: One of these exact values (case-sensitive):
                - "info_faq" — factual question about Omni
                - "new_booking" — wants to book a room
                - "cancellation" — wants to cancel an existing reservation
                - "reschedule" — wants to change dates on existing reservation
                - "escalation" — wants human, dispute, complaint, group 10+, loyalty
                - "out_of_scope" — nothing to do with Omni
        brief_reason: One-line rationale, e.g., "asked about Nashville check-in times"
                      or "wants to book Berkshire for anniversary weekend".
    """
    intent = intent.strip().lower()
    if intent not in ALLOWED_INTENTS:
        logger.warning(
            "log_caller_intent: unexpected intent %r; expected one of %s",
            intent,
            sorted(ALLOWED_INTENTS),
        )
    logger.info("CALLER_INTENT=%s | reason=%s", intent, brief_reason)
    return f"Intent logged: {intent}."


@function_tool
async def log_booking_capture(
    context: RunContext,
    caller_name: str,
    callback_phone: str,
    email: str,
    property_name: str,
    check_in_date: str,
    check_out_date: str,
    num_guests: int,
    num_rooms: int,
    special_requests: str = "",
) -> str:
    """Log a completed new-booking capture for post-call analysis and specialist handoff.

    Call this ONCE after the caller has confirmed the read-back and BEFORE
    you deliver the final transfer/farewell line. Do not call it multiple
    times for the same booking. All fields should be captured before calling
    (even if the specialist will re-verify).

    Args:
        caller_name: Full name of the caller.
        callback_phone: Digits only, e.g., "8123456789".
        email: Email address if provided; empty string if not.
        property_name: Omni property, e.g., "Omni Nashville Hotel".
        check_in_date: ISO date, YYYY-MM-DD.
        check_out_date: ISO date, YYYY-MM-DD.
        num_guests: Number of guests.
        num_rooms: Number of rooms.
        special_requests: Any special requests noted (VIP interest, anniversary,
                          king bed, accessible room, pet, etc.). Empty if none.
    """
    payload = {
        "capture_type": "new_booking",
        "caller_name": caller_name,
        "callback_phone": callback_phone,
        "email": email,
        "property_name": property_name,
        "check_in_date": check_in_date,
        "check_out_date": check_out_date,
        "num_guests": num_guests,
        "num_rooms": num_rooms,
        "special_requests": special_requests,
    }
    logger.info("CAPTURE=%s", payload)
    return "Booking capture logged."


@function_tool
async def log_cancellation_capture(
    context: RunContext,
    caller_name: str,
    callback_phone: str,
    confirmation_number: str,
    property_name: str,
    original_arrival_date: str,
    cancellation_fee_expected: bool,
    policy_note: str = "",
) -> str:
    """Log a completed cancellation capture for specialist handoff.

    Call this ONCE after read-back confirmation and BEFORE the transfer line.

    Args:
        caller_name: Full name of the caller.
        callback_phone: Digits only.
        confirmation_number: Reservation confirmation number as given.
        property_name: Omni property.
        original_arrival_date: ISO date of the arrival being cancelled, YYYY-MM-DD.
        cancellation_fee_expected: True if you determined a fee applies based on
                                    the property policy check; False if within
                                    the window.
        policy_note: One-line note on the policy determination, e.g.,
                     "Scottsdale summer, deadline was Aug 11 noon, deadline passed 4 days ago"
                     or "Berkshire — specialist will confirm exact window on callback".
    """
    payload = {
        "capture_type": "cancellation",
        "caller_name": caller_name,
        "callback_phone": callback_phone,
        "confirmation_number": confirmation_number,
        "property_name": property_name,
        "original_arrival_date": original_arrival_date,
        "cancellation_fee_expected": cancellation_fee_expected,
        "policy_note": policy_note,
    }
    logger.info("CAPTURE=%s", payload)
    return "Cancellation capture logged."


@function_tool
async def log_reschedule_capture(
    context: RunContext,
    caller_name: str,
    callback_phone: str,
    confirmation_number: str,
    property_name: str,
    current_arrival_date: str,
    current_checkout_date: str,
    requested_arrival_date: str,
    requested_checkout_date: str,
    date_flexibility: str = "",
) -> str:
    """Log a completed reschedule capture for specialist handoff.

    Call this ONCE after read-back confirmation and BEFORE the transfer line.

    Args:
        caller_name: Full name of the caller.
        callback_phone: Digits only.
        confirmation_number: Existing reservation confirmation number.
        property_name: Omni property.
        current_arrival_date: ISO date of the current arrival, YYYY-MM-DD.
        current_checkout_date: ISO date of the current checkout, YYYY-MM-DD.
        requested_arrival_date: ISO date of the requested new arrival, YYYY-MM-DD.
        requested_checkout_date: ISO date of the requested new checkout, YYYY-MM-DD.
        date_flexibility: One-line note if the caller indicated flexibility
                          (e.g., "any 3-night stay that week works"). Empty if none.
    """
    payload = {
        "capture_type": "reschedule",
        "caller_name": caller_name,
        "callback_phone": callback_phone,
        "confirmation_number": confirmation_number,
        "property_name": property_name,
        "current_arrival_date": current_arrival_date,
        "current_checkout_date": current_checkout_date,
        "requested_arrival_date": requested_arrival_date,
        "requested_checkout_date": requested_checkout_date,
        "date_flexibility": date_flexibility,
    }
    logger.info("CAPTURE=%s", payload)
    return "Reschedule capture logged."


@function_tool
async def log_escalation_capture(
    context: RunContext,
    caller_name: str,
    callback_phone: str,
    escalation_type: str,
    brief_reason: str,
    property_involved: str = "",
    approximate_stay_dates: str = "",
    confirmation_number: str = "",
    member_number: str = "",
) -> str:
    """Log a completed escalation capture for specialist handoff.

    Call this ONCE after minimum fields (name + phone + reason) have been
    captured and read back. Fill in optional fields only if relevant to the
    specific escalation type.

    Args:
        caller_name: Full name of the caller.
        callback_phone: Digits only.
        escalation_type: One of "billing_dispute", "complaint_past_stay",
                         "vip_or_special_occasion", "group_booking_10plus",
                         "loyalty_account_issue", "human_request", "other".
        brief_reason: One-line summary of the escalation reason.
        property_involved: Omni property if the escalation relates to a specific one.
        approximate_stay_dates: If reservation-related, approximate dates (e.g., "two weeks ago").
        confirmation_number: Reservation confirmation if the escalation is billing/complaint related.
        member_number: Select Guest member number if loyalty-related.
    """
    payload = {
        "capture_type": "escalation",
        "caller_name": caller_name,
        "callback_phone": callback_phone,
        "escalation_type": escalation_type,
        "brief_reason": brief_reason,
        "property_involved": property_involved,
        "approximate_stay_dates": approximate_stay_dates,
        "confirmation_number": confirmation_number,
        "member_number": member_number,
    }
    logger.info("CAPTURE=%s", payload)
    return "Escalation capture logged."


# Note: end_call is now handled by LiveKit's official `EndCallTool` from
# livekit.agents.beta.tools — see agent.py. Our earlier hand-rolled version
# was cutting off the farewell mid-sentence because it didn't hook into
# speech-done callbacks properly. The official implementation waits for the
# current speech handle, deletes the room, and shuts down the job cleanly.


@function_tool
async def get_weather(
    context: RunContext,
    property_city: str,
    arrival_date: str,
    checkout_date: str,
) -> dict[str, Any]:
    """Get a weather forecast for the caller's Omni property during their stay.

    Use this after you've captured the property AND stay dates during a new booking flow.
    Do NOT use during cancellations or reschedules — those aren't planned-for stays.

    Args:
        property_city: The city of the Omni property (e.g., "Nashville", "Scottsdale",
                       "New York", "Washington DC").
        arrival_date: Check-in date in ISO format (YYYY-MM-DD).
        checkout_date: Check-out date in ISO format (YYYY-MM-DD).

    Returns:
        Dict with daily forecast (max/min temperature in Fahrenheit,
        precipitation probability) and a short natural-language summary
        Aria can weave into the conversation.
    """
    key = _normalize_city(property_city)
    coords = PROPERTY_COORDINATES.get(key)
    if not coords:
        logger.info("get_weather: unknown city %r", property_city)
        return {"error": f"Unknown property city: {property_city}"}

    lat, lon = coords
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max",
        "temperature_unit": "fahrenheit",
        "timezone": "auto",
        "start_date": arrival_date,
        "end_date": checkout_date,
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://api.open-meteo.com/v1/forecast",
                params=params,
                timeout=aiohttp.ClientTimeout(total=6),
            ) as resp:
                resp.raise_for_status()
                data = await resp.json()
    except Exception as exc:
        logger.exception("get_weather failed for %s", property_city)
        return {"error": f"Weather lookup failed: {exc}"}

    daily = data.get("daily", {})
    dates = daily.get("time", [])
    highs = daily.get("temperature_2m_max", [])
    lows = daily.get("temperature_2m_min", [])
    precip = daily.get("precipitation_probability_max", [])

    if not dates:
        return {"error": "No forecast data available for those dates."}

    peak_high = max(highs) if highs else None
    min_low = min(lows) if lows else None
    max_precip = max(precip) if precip else 0

    if peak_high is not None and peak_high >= 100:
        summary = f"Very hot — temperatures peaking around {round(peak_high)}°F. Pools and spa are climate-controlled and popular on days like that."
    elif max_precip >= 60:
        summary = f"Rain likely — up to {max_precip}% chance on the wettest day. Umbrellas are available at the front desk."
    elif peak_high is not None and peak_high >= 85:
        summary = f"Warm — highs around {round(peak_high)}°F. Good weather for pool time."
    elif peak_high is not None and peak_high <= 45:
        summary = f"Chilly — highs only around {round(peak_high)}°F. Pack layers."
    else:
        summary = f"Mild forecast — highs around {round(peak_high) if peak_high else '—'}°F, lows around {round(min_low) if min_low is not None else '—'}°F."

    return {
        "city": CITY_ALIASES.get(key, property_city),
        "dates": dates,
        "highs_f": [round(h) for h in highs],
        "lows_f": [round(l) for l in lows],
        "max_precip_probability": max_precip,
        "summary": summary,
    }


@function_tool
async def get_local_events(
    context: RunContext,
    property_city: str,
    start_date: str,
    end_date: str,
) -> dict[str, Any]:
    """Get notable local events near the caller's Omni property during their stay.

    Use this after you've captured the property AND stay dates during a new booking flow.
    Weave results in as concierge-style tips (e.g., "there's a concert that Saturday
    — restaurants book up fast on event nights, would you like me to note a dinner preference?").

    Args:
        property_city: The city of the Omni property.
        start_date: Stay start date, YYYY-MM-DD.
        end_date: Stay end date, YYYY-MM-DD.

    Returns:
        Dict with up to 5 upcoming events (name, venue, date) and a short
        natural-language summary Aria can share with the caller.
    """
    api_key = os.environ.get("TICKETMASTER_API_KEY")
    if not api_key:
        logger.warning("TICKETMASTER_API_KEY not set — skipping events lookup")
        return {"error": "Events lookup unavailable right now."}

    key = _normalize_city(property_city)
    city = CITY_ALIASES.get(key, property_city)

    params = {
        "apikey": api_key,
        "city": city,
        "startDateTime": f"{start_date}T00:00:00Z",
        "endDateTime": f"{end_date}T23:59:59Z",
        "size": 5,
        "sort": "date,asc",
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://app.ticketmaster.com/discovery/v2/events.json",
                params=params,
                timeout=aiohttp.ClientTimeout(total=6),
            ) as resp:
                resp.raise_for_status()
                data = await resp.json()
    except Exception as exc:
        logger.exception("get_local_events failed for %s", property_city)
        return {"error": f"Events lookup failed: {exc}"}

    events_raw = data.get("_embedded", {}).get("events", [])
    events = []
    for e in events_raw[:5]:
        try:
            events.append(
                {
                    "name": e.get("name"),
                    "date": e.get("dates", {}).get("start", {}).get("localDate"),
                    "venue": (
                        e.get("_embedded", {})
                        .get("venues", [{}])[0]
                        .get("name")
                    ),
                }
            )
        except Exception:
            continue

    if not events:
        return {
            "city": city,
            "events": [],
            "summary": f"Nothing notable coming up in {city} during those dates.",
        }

    top = events[0]
    summary_bits = [
        f"there's {top['name']}" + (f" at {top['venue']}" if top.get("venue") else "")
    ]
    if top.get("date"):
        summary_bits.append(f"on {top['date']}")
    summary = " ".join(summary_bits) + "."

    return {
        "city": city,
        "events": events,
        "summary": summary,
    }

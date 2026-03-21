"""risk_evaluator node — third node in the harvest-agent pipeline.

Pure Python logic — no LLM call.

Reads the 7-day weather forecast from state["weather_forecast"] and checks
the first 3 days (72-hour window) for risk thresholds:

  - precipitation_sum > 5 mm in any of days 0-2  → escalate to "critical"
  - temperature_2m_min < 2.0 °C in any of days 0-2 → escalate to "critical"

Only zones with status "harvest_now" or "approaching" are escalated.
A risk_reason string is added/appended to explain the escalation.
"""
from __future__ import annotations

from app.agent.state import AgentState, ZoneClassification

# Statuses that warrant weather-based risk escalation
_ESCALATE_STATUSES = {"harvest_now", "approaching"}

# Thresholds
_PRECIP_THRESHOLD_MM = 5.0   # mm per day
_TEMP_THRESHOLD_C = 2.0      # °C minimum temperature


def _check_weather_risks(weather_forecast: dict) -> tuple[bool, bool, list[str]]:
    """Inspect first 3 days of forecast for risk conditions.

    Returns:
        (precip_risk, frost_risk, risk_reasons)
    """
    daily: dict = weather_forecast.get("daily", {})
    precip_list: list = daily.get("precipitation_sum", [])
    temp_min_list: list = daily.get("temperature_2m_min", [])
    time_list: list = daily.get("time", [])

    precip_risk = False
    frost_risk = False
    risk_reasons: list[str] = []

    for i in range(min(3, len(precip_list))):
        day_label = time_list[i] if i < len(time_list) else f"day {i}"

        precip = precip_list[i]
        if precip is not None and float(precip) > _PRECIP_THRESHOLD_MM:
            precip_risk = True
            risk_reasons.append(
                f"Heavy rain forecast ({float(precip):.1f} mm) on {day_label} — "
                f"harvest window at risk of field saturation."
            )

    for i in range(min(3, len(temp_min_list))):
        day_label = time_list[i] if i < len(time_list) else f"day {i}"

        temp = temp_min_list[i]
        if temp is not None and float(temp) < _TEMP_THRESHOLD_C:
            frost_risk = True
            risk_reasons.append(
                f"Near-frost temperature ({float(temp):.1f} °C) forecast on {day_label} — "
                f"crop quality at risk if not harvested promptly."
            )

    return precip_risk, frost_risk, risk_reasons


async def risk_evaluator(state: AgentState) -> AgentState:
    """Escalate urgency for at-risk zones based on weather forecast."""
    weather_forecast: dict = state.get("weather_forecast", {})
    zone_classifications: list[ZoneClassification] = state.get("zone_classifications", [])

    precip_risk, frost_risk, risk_reasons = _check_weather_risks(weather_forecast)
    any_risk = precip_risk or frost_risk

    updated_classifications: list[ZoneClassification] = []
    escalated_zones: list[str] = []

    for classification in zone_classifications:
        if any_risk and classification["status"] in _ESCALATE_STATUSES:
            # Build a combined risk_reason string
            existing_reason = classification.get("risk_reason", "")
            weather_reason = " | ".join(risk_reasons)
            combined_reason = (
                f"{existing_reason} | {weather_reason}".lstrip(" |").strip()
                if existing_reason
                else weather_reason
            )

            updated = ZoneClassification(
                zone_id=classification["zone_id"],
                label=classification["label"],
                status=classification["status"],
                confidence=classification["confidence"],
                urgency="critical",
                risk_reason=combined_reason,
            )
            escalated_zones.append(classification["zone_id"])
        else:
            # No change — copy as-is (immutable update pattern)
            updated = ZoneClassification(
                zone_id=classification["zone_id"],
                label=classification["label"],
                status=classification["status"],
                confidence=classification["confidence"],
                urgency=classification["urgency"],
                risk_reason=classification.get("risk_reason", ""),
            )

        updated_classifications.append(updated)

    trace_entry: dict = {
        "node_name": "risk_evaluator",
        "inputs": {
            "zone_count": len(zone_classifications),
            "precip_risk": precip_risk,
            "frost_risk": frost_risk,
        },
        "outputs": {
            "escalated_zone_ids": escalated_zones,
            "risk_reasons": risk_reasons,
        },
    }

    return {
        **state,
        "zone_classifications": updated_classifications,
        "reasoning_trace": [*state.get("reasoning_trace", []), trace_entry],
    }

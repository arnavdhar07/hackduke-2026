"""action_generator node — fourth node in the harvest-agent pipeline.

Calls Claude with tool_use (forced structured output) to generate prioritized
farm action recommendations for each zone, given its classification and urgency
status produced by the previous nodes.

Output: fills state["recommendations"] with List[RecommendationOutput].
"""
from __future__ import annotations

import anthropic

from app.agent.state import AgentState, RecommendationOutput, ZoneClassification
from app.config import settings


_TOOL_SCHEMA = {
    "name": "generate_actions",
    "description": (
        "Generate prioritized farm actions for each crop zone based on harvest "
        "readiness classification and weather risk assessment."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "recommendations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "zone_id": {"type": "string"},
                        "zone_label": {"type": "string"},
                        "action_type": {
                            "type": "string",
                            "enum": ["harvest", "irrigate", "monitor", "inspect"],
                        },
                        "urgency": {
                            "type": "string",
                            "enum": ["low", "medium", "high", "critical"],
                        },
                        "reason": {
                            "type": "string",
                            "description": (
                                "Exactly 2 plain English sentences explaining why this "
                                "action is recommended for this zone right now."
                            ),
                        },
                        "confidence": {
                            "type": "number",
                            "minimum": 0.0,
                            "maximum": 1.0,
                        },
                    },
                    "required": [
                        "zone_id",
                        "zone_label",
                        "action_type",
                        "urgency",
                        "reason",
                        "confidence",
                    ],
                },
            }
        },
        "required": ["recommendations"],
    },
}


def _build_user_message(state: AgentState) -> str:
    """Construct the action-generation prompt from AgentState."""
    classifications: list[ZoneClassification] = state["zone_classifications"]
    crop_type: str = state["crop_type"]
    days: int = state["days_since_planting"]

    # Include a concise weather summary
    daily: dict = state.get("weather_forecast", {}).get("daily", {})
    precip_list: list = daily.get("precipitation_sum", [])
    temp_list: list = daily.get("temperature_2m_min", [])
    time_list: list = daily.get("time", [])

    weather_lines: list[str] = ["  7-day weather outlook:"]
    for i in range(min(7, len(time_list))):
        p = precip_list[i] if i < len(precip_list) else "n/a"
        t = temp_list[i] if i < len(temp_list) else "n/a"
        day = time_list[i]
        weather_lines.append(
            f"    {day}: precip={p} mm, min_temp={t} °C"
        )

    lines: list[str] = [
        "You are a senior agronomist generating actionable farm recommendations.",
        "",
        f"Crop type       : {crop_type}",
        f"Days planted    : {days}",
        "",
        "\n".join(weather_lines),
        "",
        "Zone classifications (from previous analysis):",
    ]

    for c in classifications:
        lines += [
            "",
            f"  Zone ID     : {c['zone_id']}",
            f"  Label       : {c['label']}",
            f"  Status      : {c['status']}",
            f"  Urgency     : {c['urgency']}",
            f"  Confidence  : {c['confidence']:.2f}",
            f"  Risk reason : {c['risk_reason'] or '(none)'}",
        ]

    lines += [
        "",
        "Instructions:",
        "  - action_type options: harvest | irrigate | monitor | inspect",
        "  - urgency must match the zone's urgency from the classification above",
        "  - reason must be exactly 2 plain English sentences",
        "  - confidence: your certainty as a float 0.0–1.0",
        "  Return one recommendation object for every zone listed above.",
    ]

    return "\n".join(lines)


async def action_generator(state: AgentState) -> AgentState:
    """Generate farm action recommendations using Claude tool_use."""
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    user_message = _build_user_message(state)

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        tools=[_TOOL_SCHEMA],
        tool_choice={"type": "tool", "name": "generate_actions"},
        messages=[{"role": "user", "content": user_message}],
    )

    # tool_choice forces the first content block to be a tool_use block
    result: dict = response.content[0].input  # always a dict, always parseable

    raw_recommendations: list[dict] = result.get("recommendations", [])

    # Use state["zones"] (from DB) as the authoritative source for zone_id + label.
    # zone_classifications has DB-correct zone_ids (fixed in zone_classifier),
    # but we also build from state["zones"] as a double-fallback.
    db_zones = state["zones"]
    # Primary lookup: by label from zone_classifications (already DB-authoritative)
    label_to_zone_id: dict[str, str] = {
        c["label"]: c["zone_id"]
        for c in state["zone_classifications"]
    }
    # Secondary lookup: by label from raw DB zones list
    label_to_zone_id.update({z["label"]: z["zone_id"] for z in db_zones})

    # Coerce to typed RecommendationOutput dicts (JSON-serializable)
    # Always override zone_id from state — never trust Claude's echoed value
    recommendations: list[RecommendationOutput] = []
    for i, r in enumerate(raw_recommendations):
        claude_label = str(r.get("zone_label", ""))
        # Match by label; fall back to positional index into db_zones
        zone_id = label_to_zone_id.get(claude_label)
        db_label = claude_label
        if zone_id is None and i < len(db_zones):
            zone_id = db_zones[i]["zone_id"]
            db_label = db_zones[i]["label"]
        if zone_id is None:
            continue  # no zone to map to — skip rather than write bad UUID
        recommendations.append(
            RecommendationOutput(
                zone_id=zone_id,
                zone_label=db_label,
                action_type=str(r["action_type"]),
                urgency=str(r["urgency"]),
                reason=str(r["reason"]),
                confidence=float(r["confidence"]),
            )
        )

    trace_entry: dict = {
        "node_name": "action_generator",
        "inputs": {
            "zone_count": len(state["zone_classifications"]),
            "crop_type": state["crop_type"],
        },
        "outputs": {
            "recommendations": [
                {
                    "zone_id": r["zone_id"],
                    "action_type": r["action_type"],
                    "urgency": r["urgency"],
                    "confidence": r["confidence"],
                }
                for r in recommendations
            ]
        },
    }

    return {
        **state,
        "recommendations": recommendations,
        "reasoning_trace": [*state.get("reasoning_trace", []), trace_entry],
    }

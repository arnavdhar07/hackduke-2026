"""zone_classifier node — second node in the harvest-agent pipeline.

Calls Claude with tool_use (forced structured output) to classify each zone's
harvest readiness status from vegetation indices and crop growth stage data.

Output: fills state["zone_classifications"] with List[ZoneClassification].
"""
from __future__ import annotations

import anthropic

from app.agent.state import AgentState, ZoneClassification, ZoneScore
from app.config import settings


_TOOL_SCHEMA = {
    "name": "classify_zones",
    "description": (
        "Classify harvest readiness status for each crop zone based on vegetation "
        "indices and crop growth stage. Return one classification per zone."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "classifications": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "zone_id": {"type": "string"},
                        "label": {"type": "string"},
                        "status": {
                            "type": "string",
                            "enum": [
                                "not_ready",
                                "approaching",
                                "harvest_now",
                                "past_peak",
                                "stressed",
                            ],
                        },
                        "confidence": {
                            "type": "number",
                            "minimum": 0.0,
                            "maximum": 1.0,
                        },
                        "urgency": {
                            "type": "string",
                            "enum": ["low", "medium", "high", "critical"],
                        },
                        "risk_reason": {
                            "type": "string",
                            "description": "Empty string if no risk; otherwise a short explanation.",
                        },
                        "days_remaining": {
                            "type": "integer",
                            "description": (
                                "Estimated days until harvest window closes. "
                                "For harvest_now: days before quality degrades. "
                                "For approaching: days until harvest window opens. "
                                "For not_ready: -1. For past_peak/stressed: 0."
                            ),
                            "minimum": -1,
                        },
                        "crop_health_rating": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 10,
                            "description": (
                                "Overall crop health 1-10. "
                                "1-3: severe stress or dying. "
                                "4-5: significant stress, yield loss likely. "
                                "6-7: moderate health, some concerns. "
                                "8-9: healthy with good yield potential. "
                                "10: peak condition."
                            ),
                        },
                        "crop_health_summary": {
                            "type": "string",
                            "description": (
                                "Exactly 2 plain-English sentences explaining the crop health "
                                "for this zone, referencing specific index values and what they "
                                "mean for a farmer."
                            ),
                        },
                    },
                    "required": [
                        "zone_id",
                        "label",
                        "status",
                        "confidence",
                        "urgency",
                        "risk_reason",
                        "days_remaining",
                        "crop_health_rating",
                        "crop_health_summary",
                    ],
                },
            }
        },
        "required": ["classifications"],
    },
}


def _build_user_message(state: AgentState) -> str:
    """Construct the classification prompt from AgentState."""
    zones: list[ZoneScore] = state["zones"]
    crop_type: str = state["crop_type"]
    days: int = state["days_since_planting"]
    planting_date: str = state["planting_date"]

    lines: list[str] = [
        f"You are an expert agronomist specializing in {crop_type} cultivation. "
        f"Classify each crop zone below for harvest readiness based on the specific growth "
        f"characteristics and optimal NDVI/NDWI/NDRE thresholds for {crop_type}.",
        f"",
        f"Field details:",
        f"  Crop type: {crop_type}",
        f"  Planting date: {planting_date}",
        f"  Days since planting: {days}",
        f"",
        f"Zone data (one zone per entry):",
    ]

    for z in zones:
        lines += [
            f"",
            f"  Zone ID  : {z['zone_id']}",
            f"  Label    : {z['label']}",
            f"  NDVI     : {z['ndvi']:.1f}/100  (greenness/biomass — saturates at high density; best 40-80 range)",
            f"  EVI      : {z['evi']:.1f}/100   (enhanced vegetation — more accurate than NDVI for dense canopies)",
            f"  NDWI     : {z['ndwi']:.1f}/100  (water stress — low values mean drought or over-maturity)",
            f"  NDRE     : {z['ndre']:.1f}/100  (chlorophyll/early stress — drops 2-3 weeks before NDVI decline)",
            f"  NDVI Δ7d : {z['ndvi_delta']:+.1f}   (change vs 7 days ago — negative = senescence/stress onset)",
            f"  Zone area: {z['zone_area_acres']:.1f} acres",
            f"  Captured : {z['captured_at']}",
        ]

    lines += [
        f"",
        f"Instructions:",
        f"  - status options: not_ready | approaching | harvest_now | past_peak | stressed",
        f"  - urgency options: low | medium | high | critical",
        f"  - risk_reason: empty string unless you see a specific risk to flag",
        f"  - confidence: your certainty as a float 0.0–1.0",
        f"  - Use all 4 vegetation indices together, applying thresholds appropriate for {crop_type}.",
        f"    NDRE declining while NDVI stable = early stress.",
        f"    EVI dropping while NDVI holds = dense canopy maturity signal.",
        f"  - Estimate days_remaining based on rate of NDVI decline (ndvi_delta):",
        f"    if declining at X/week, project to threshold of 40.",
        f"    For harvest_now: days before quality degrades (0–7 typical).",
        f"    For approaching: days until harvest window opens.",
        f"    For not_ready: use -1. For past_peak/stressed: use 0.",
        f"  - crop_health_rating: 1-10 overall score based on all indices.",
        f"  - crop_health_summary: exactly 2 sentences referencing specific index values.",
        f"  Return one classification object for every zone listed above.",
    ]

    return "\n".join(lines)


async def zone_classifier(state: AgentState) -> AgentState:
    """Classify each zone's harvest readiness using Claude tool_use."""
    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    user_message = _build_user_message(state)

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        tools=[_TOOL_SCHEMA],
        tool_choice={"type": "tool", "name": "classify_zones"},
        messages=[{"role": "user", "content": user_message}],
    )

    # tool_choice forces the first content block to be a tool_use block
    result: dict = response.content[0].input  # always a dict, always parseable

    raw_classifications: list[dict] = result.get("classifications", [])

    # Use state["zones"] (from DB) as the authoritative source for zone_id + label.
    # Claude frequently corrupts or omits UUIDs — never trust its echoed values.
    db_zones: list[ZoneScore] = state["zones"]
    label_to_db_zone: dict[str, ZoneScore] = {z["label"]: z for z in db_zones}

    zone_classifications: list[ZoneClassification] = []
    for i, c in enumerate(raw_classifications):
        # Match by label first; fall back to positional index if label drifted
        db_zone = label_to_db_zone.get(str(c.get("label", "")))
        if db_zone is None and i < len(db_zones):
            db_zone = db_zones[i]
        if db_zone is None:
            continue  # zone count mismatch — skip rather than insert bad UUID
        zone_classifications.append(
            ZoneClassification(
                zone_id=db_zone["zone_id"],   # always use DB UUID
                label=db_zone["label"],        # always use DB label
                status=str(c["status"]),
                confidence=float(c["confidence"]),
                urgency=str(c["urgency"]),
                risk_reason=str(c.get("risk_reason", "")),
                days_remaining=int(c.get("days_remaining", -1)),
                crop_health_rating=int(c.get("crop_health_rating", 5)),
                crop_health_summary=str(c.get("crop_health_summary", "")),
            )
        )

    trace_entry: dict = {
        "node_name": "zone_classifier",
        "inputs": {
            "zone_count": len(state["zones"]),
            "crop_type": state["crop_type"],
            "days_since_planting": state["days_since_planting"],
        },
        "outputs": {
            "classifications": [
                {
                    "zone_id": c["zone_id"],
                    "status": c["status"],
                    "urgency": c["urgency"],
                    "confidence": c["confidence"],
                    "days_remaining": c["days_remaining"],
                    "crop_health_rating": c["crop_health_rating"],
                }
                for c in zone_classifications
            ]
        },
    }

    return {
        **state,
        "zone_classifications": zone_classifications,
        "reasoning_trace": [*state.get("reasoning_trace", []), trace_entry],
    }

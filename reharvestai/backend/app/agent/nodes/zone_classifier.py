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
                    },
                    "required": [
                        "zone_id",
                        "label",
                        "status",
                        "confidence",
                        "urgency",
                        "risk_reason",
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
        f"You are an expert agronomist. Classify each crop zone below for harvest readiness.",
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
            f"  Zone ID : {z['zone_id']}",
            f"  Label   : {z['label']}",
            f"  NDVI    : {z['ndvi']:.4f}  (higher = more green biomass; typical harvest range 0.6–0.8)",
            f"  NDWI    : {z['ndwi']:.4f}  (water content; high values may indicate over-irrigation)",
            f"  NDRE    : {z['ndre']:.4f}  (red-edge; sensitive to chlorophyll / crop stress)",
            f"  NDVI Δ7d: {z['ndvi_delta']:+.4f}  (change vs 7 days ago; negative = senescence/stress)",
            f"  Captured: {z['captured_at']}",
        ]

    lines += [
        f"",
        f"Instructions:",
        f"  - status options: not_ready | approaching | harvest_now | past_peak | stressed",
        f"  - urgency options: low | medium | high | critical",
        f"  - risk_reason: empty string unless you see a specific risk to flag",
        f"  - confidence: your certainty as a float 0.0–1.0",
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

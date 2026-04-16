"""action_generator node — fourth node in the harvest-agent pipeline.

Calls DeepSeek (OpenAI-compatible API) with function calling (forced structured
output) to generate prioritized farm action recommendations for each zone, given
its classification and urgency status produced by the previous nodes.

Output: fills state["recommendations"] with List[RecommendationOutput].
"""
from __future__ import annotations

import json

from openai import OpenAI

from app.agent.state import AgentState, RecommendationOutput, ZoneClassification
from app.config import settings


# Base yields per acre by crop type (bushels; 0 = weight-based crop, skip estimation)
CROP_BASE_YIELDS: dict[str, float] = {
    "corn": 175.0,
    "wheat": 47.0,
    "soy": 50.0,
    "soybeans": 50.0,
    "cotton": 0.0,
    "rice": 0.0,
}


_DEEPSEEK_TOOL = {
    "type": "function",
    "function": {
        "name": "generate_actions",
        "description": (
            "Generate prioritized farm actions for each crop zone based on harvest "
            "readiness classification and weather risk assessment."
        ),
        "parameters": {
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
                                "enum": ["harvest", "irrigate", "monitor", "inspect", "fertilize", "spray", "scout", "soil_sample"],
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
                                "description": "Certainty as a float 0.0–1.0",
                            },
                            "estimated_yield_bushels": {
                                "type": "number",
                                "description": (
                                    "Estimated yield in bushels for this zone. "
                                    "Base yields: corn=175, wheat=47, soy=50, other crops=60 bu/acre equivalent. "
                                    "Multiply by zone_area_acres × (0.5 + ndvi/200). "
                                    "Round to nearest integer. Use 0 for cotton/rice."
                                ),
                            },
                        },
                        "required": [
                            "zone_id", "zone_label", "action_type", "urgency",
                            "reason", "confidence", "estimated_yield_bushels",
                        ],
                    },
                }
            },
            "required": ["recommendations"],
        },
    },
}


def _build_user_message(state: AgentState) -> str:
    """Construct the action-generation prompt from AgentState."""
    classifications: list[ZoneClassification] = state["zone_classifications"]
    crop_type: str = state["crop_type"]
    days: int = state["days_since_planting"]
    growth_stage: str = state.get("growth_stage", "unknown")

    base_yield_per_acre = CROP_BASE_YIELDS.get(crop_type.lower(), 0.0)
    if base_yield_per_acre == 0.0 and crop_type.lower() not in ("cotton", "rice"):
        base_yield_per_acre = 60.0

    zone_area_by_id: dict[str, float] = {
        z["zone_id"]: z.get("zone_area_acres", 0.0)
        for z in state.get("zones", [])
    }
    zone_scores_by_id: dict[str, dict] = {
        z["zone_id"]: z
        for z in state.get("zones", [])
    }

    daily: dict = state.get("weather_forecast", {}).get("daily", {})
    precip_list: list = daily.get("precipitation_sum", [])
    temp_list: list = daily.get("temperature_2m_min", [])
    time_list: list = daily.get("time", [])

    weather_lines: list[str] = ["  7-day weather outlook:"]
    for i in range(min(7, len(time_list))):
        p = precip_list[i] if i < len(precip_list) else "n/a"
        t = temp_list[i] if i < len(temp_list) else "n/a"
        day = time_list[i]
        weather_lines.append(f"    {day}: precip={p} mm, min_temp={t} °C")

    lines: list[str] = [
        "You are a senior agronomist generating actionable farm recommendations.",
        "",
        f"Crop type       : {crop_type} (base yield: {base_yield_per_acre:.0f} bu/acre)",
        f"Days planted    : {days}",
        f"Growth stage    : {growth_stage}",
        "",
        "\n".join(weather_lines),
        "",
        "Zone classifications (from previous analysis):",
    ]

    for c in classifications:
        zone_area = zone_area_by_id.get(c["zone_id"], 0.0)
        zs = zone_scores_by_id.get(c["zone_id"], {})
        lines += [
            "",
            f"  Zone ID        : {c['zone_id']}",
            f"  Label          : {c['label']}",
            f"  Status         : {c['status']}",
            f"  Urgency        : {c['urgency']}",
            f"  Confidence     : {c['confidence']:.2f}",
            f"  Risk reason    : {c['risk_reason'] or '(none)'}",
            f"  Days remaining : {c['days_remaining']}",
            f"  Health rating  : {c['crop_health_rating']}/10",
            f"  Zone area      : {zone_area:.1f} acres",
            f"  NDVI           : {zs.get('ndvi', 0.0):.1f}/100  (greenness/biomass)",
            f"  EVI            : {zs.get('evi', 0.0):.1f}/100   (dense-canopy vegetation)",
            f"  NDWI           : {zs.get('ndwi', 0.0):.1f}/100  (water stress)",
            f"  NDRE           : {zs.get('ndre', 0.0):.1f}/100  (early chlorophyll stress)",
            f"  GNDVI          : {zs.get('gndvi', 0.0):.1f}/100  (late-season chlorophyll)",
            f"  SAVI           : {zs.get('savi', 0.0):.1f}/100  (soil-adjusted VI)",
            f"  CIg            : {zs.get('cig', 0.0):.1f}/100  (nitrogen proxy; <40 = deficiency)",
            f"  NDVI Δ7d       : {zs.get('ndvi_delta', 0.0):+.1f}",
        ]

    lines += [
        "",
        "Instructions:",
        "  - action_type options: harvest | irrigate | monitor | inspect | fertilize | spray | scout | soil_sample",
        "    fertilize: when CIg < 40 or NDRE < 45 (nitrogen/chlorophyll deficiency)",
        "    spray: when growth stage allows (not germination/maturity) and stress or disease risk is present",
        "    scout: when NDRE drops but NDVI holds (early stress not yet visible in biomass)",
        "    soil_sample: when persistent low CIg/NDRE with no weather explanation",
        "  - Do NOT recommend 'harvest' if growth_stage is germination or vegetative (too early).",
        "  - urgency must match the zone's urgency from the classification above",
        "  - reason must be exactly 2 plain English sentences referencing specific index values",
        "  - confidence: your certainty as a float 0.0–1.0",
        f"  - estimated_yield_bushels: base {base_yield_per_acre:.0f} bu/acre × zone_area_acres × (0.5 + ndvi/200)",
        "    Round to nearest integer. Use 0 for cotton/rice.",
        "  Return one recommendation object for every zone listed above.",
    ]

    return "\n".join(lines)


async def action_generator(state: AgentState) -> AgentState:
    """Generate farm action recommendations using DeepSeek function calling."""
    client = OpenAI(
        api_key=settings.DEEPSEEK_API_KEY,
        base_url="https://api.deepseek.com/v1",
    )

    user_message = _build_user_message(state)

    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": user_message}],
        tools=[_DEEPSEEK_TOOL],
        tool_choice={"type": "function", "function": {"name": "generate_actions"}},
    )

    tool_call = response.choices[0].message.tool_calls[0]
    result: dict = json.loads(tool_call.function.arguments)

    raw_recommendations: list[dict] = list(result.get("recommendations", []))

    db_zones = state["zones"]
    label_to_zone_id: dict[str, str] = {
        c["label"]: c["zone_id"]
        for c in state["zone_classifications"]
    }
    label_to_zone_id.update({z["label"]: z["zone_id"] for z in db_zones})

    recommendations: list[RecommendationOutput] = []
    for i, r in enumerate(raw_recommendations):
        r = dict(r)
        llm_label = str(r.get("zone_label", ""))
        zone_id = label_to_zone_id.get(llm_label)
        db_label = llm_label
        if zone_id is None and i < len(db_zones):
            zone_id = db_zones[i]["zone_id"]
            db_label = db_zones[i]["label"]
        if zone_id is None:
            continue

        matching_class = next(
            (c for c in state["zone_classifications"] if c["zone_id"] == zone_id),
            None,
        )
        days_remaining = matching_class["days_remaining"] if matching_class else -1
        crop_health_rating = matching_class.get("crop_health_rating", 0) if matching_class else 0
        crop_health_summary = matching_class.get("crop_health_summary", "") if matching_class else ""

        recommendations.append(
            RecommendationOutput(
                zone_id=zone_id,
                zone_label=db_label,
                action_type=str(r["action_type"]),
                urgency=str(r["urgency"]),
                reason=str(r["reason"]),
                confidence=float(r["confidence"]),
                estimated_yield_bushels=float(r.get("estimated_yield_bushels", 0.0)),
                days_remaining=days_remaining,
                crop_health_rating=crop_health_rating,
                crop_health_summary=crop_health_summary,
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
                    "estimated_yield_bushels": r["estimated_yield_bushels"],
                    "days_remaining": r["days_remaining"],
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

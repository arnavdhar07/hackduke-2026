---
description: Inject when writing any LangGraph node, graph definition,
  state schema, or checkpointer code for the ReHarvestAI agent.
---

## AgentState — canonical definition (backend/app/agent/state.py)
```python
from typing import TypedDict, List

class ZoneScore(TypedDict):
    zone_id: str
    label: str
    ndvi: float
    ndwi: float
    ndre: float
    ndvi_delta: float        # current ndvi minus ndvi from 7 days ago
    captured_at: str         # ISO string

class ZoneClassification(TypedDict):
    zone_id: str
    label: str
    status: str              # not_ready|approaching|harvest_now|past_peak|stressed
    confidence: float
    urgency: str             # low|medium|high|critical (may be escalated by risk_evaluator)
    risk_reason: str         # empty string if no escalation

class RecommendationOutput(TypedDict):
    zone_id: str
    zone_label: str
    action_type: str         # harvest|irrigate|monitor|inspect
    urgency: str             # low|medium|high|critical
    reason: str              # 2 plain English sentences
    confidence: float

class AgentState(TypedDict):
    field_id: str
    field_lat: float
    field_lon: float
    crop_type: str
    planting_date: str
    days_since_planting: int
    zones: List[ZoneScore]
    weather_forecast: dict
    zone_classifications: List[ZoneClassification]
    recommendations: List[RecommendationOutput]
    reasoning_trace: List[dict]
```

## Node immutability pattern
```python
def my_node(state: AgentState) -> AgentState:
    # compute something
    new_data = [...]

    # always return full state with updates merged in
    return {
        **state,
        "zone_classifications": new_data,
        "reasoning_trace": state["reasoning_trace"] + [{
            "node_name": "my_node",
            "inputs": {"zones_count": len(state["zones"])},
            "outputs": {"classified_count": len(new_data)}
        }]
    }
```

## Graph wiring pattern (graph.py)
```python
from langgraph.graph import StateGraph
from app.agent.state import AgentState

def build_graph():
    graph = StateGraph(AgentState)

    graph.add_node("context_builder", context_builder)
    graph.add_node("zone_classifier", zone_classifier)
    graph.add_node("risk_evaluator", risk_evaluator)
    graph.add_node("action_generator", action_generator)
    graph.add_node("output_formatter", output_formatter)

    graph.set_entry_point("context_builder")
    graph.add_edge("context_builder", "zone_classifier")
    graph.add_edge("zone_classifier", "risk_evaluator")
    graph.add_edge("risk_evaluator", "action_generator")
    graph.add_edge("action_generator", "output_formatter")
    graph.set_finish_point("output_formatter")

    return graph.compile(checkpointer=get_redis_checkpointer())
```

## Gotchas
- datetime objects crash Redis serialization — always call .isoformat() before
  putting any date/time into state
- LangGraph's StateGraph requires ALL state keys to be present in the initial
  invoke call — initialize missing keys to [] or {} or "" not None
- tool_choice={"type": "tool", "name": "..."} forces Claude to always use the
  tool — without this it may respond in text and break your parser
- The checkpointer persists state between retries — if a node fails and retries,
  it will see the state from the previous partial run
- add_edge after set_finish_point raises a silent error — call set_finish_point last

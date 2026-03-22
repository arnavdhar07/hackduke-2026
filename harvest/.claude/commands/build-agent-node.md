---
description: Build or modify a single LangGraph agent node. Always reads
  the current AgentState definition and adjacent nodes before writing.
argument-hint: "<node name: context_builder|zone_classifier|risk_evaluator|action_generator|output_formatter>"
---

Build the LangGraph node: $ARGUMENTS

Sequence:

Step 1 — read context (main context):
Read backend/app/agent/state.py for the full AgentState definition.
Read the node files immediately before and after this node in the pipeline
to understand what inputs this node receives and what outputs the next
node expects.

Step 2 — @langgraph-agent implementation:
Write the node function.
The function signature must be: def node_name(state: AgentState) -> AgentState
The return must be {**state, "updated_key": new_value, "reasoning_trace": state["reasoning_trace"] + [...]}
If this node calls Claude, use tool_use structured output — never free-form text parsing.
All values placed in state must be JSON-serializable.

Step 3 — verify serialization (main context):
Run: python -c "import json; from app.agent.nodes.$ARGUMENTS import *; print('ok')"
If the node builds state objects, also run:
python -c "import json; json.dumps(sample_output)" to confirm serializability.

Return: the complete node function and a sample state dict showing
what this node adds to state.

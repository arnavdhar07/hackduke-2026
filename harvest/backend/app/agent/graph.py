from __future__ import annotations

from langgraph.graph import StateGraph

from app.agent.state import AgentState
from app.agent.nodes.context_builder import context_builder
from app.agent.nodes.zone_classifier import zone_classifier
from app.agent.nodes.risk_evaluator import risk_evaluator
from app.agent.nodes.action_generator import action_generator
from app.agent.nodes.output_formatter import output_formatter
from app.agent.checkpointer import get_redis_checkpointer


def build_graph():
    """Build and compile the 5-node LangGraph harvest-recommendation pipeline.

    Node order:
        context_builder → zone_classifier → risk_evaluator
            → action_generator → output_formatter

    NOTE: set_finish_point() is always called LAST — calling add_edge() after it
    raises a silent error in LangGraph.
    """
    graph = StateGraph(AgentState)

    # Register nodes
    graph.add_node("context_builder", context_builder)
    graph.add_node("zone_classifier", zone_classifier)
    graph.add_node("risk_evaluator", risk_evaluator)
    graph.add_node("action_generator", action_generator)
    graph.add_node("output_formatter", output_formatter)

    # Entry point
    graph.set_entry_point("context_builder")

    # Edges — define the linear pipeline
    graph.add_edge("context_builder", "zone_classifier")
    graph.add_edge("zone_classifier", "risk_evaluator")
    graph.add_edge("risk_evaluator", "action_generator")
    graph.add_edge("action_generator", "output_formatter")

    # Finish point — MUST be called after all add_edge() calls
    graph.set_finish_point("output_formatter")

    # No checkpointer for now — simplifies Celery async (graph.ainvoke is used)
    return graph.compile()

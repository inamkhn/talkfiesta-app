"""Compiled LangGraph workflow for initial assessment evaluation."""

from __future__ import annotations

from functools import lru_cache

from langgraph.graph import END, START, StateGraph

from app.modules.assessment.ai.nodes import (
    placement_node,
    speaking_node,
    writing_node,
)
from app.modules.assessment.ai.state import AssessmentGraphState


@lru_cache
def build_assessment_graph():
    """Build and compile the assessment evaluation graph."""
    graph = StateGraph(AssessmentGraphState)
    graph.add_node("evaluate_speaking", speaking_node)
    graph.add_node("evaluate_writing", writing_node)
    graph.add_node("determine_placement", placement_node)

    graph.add_edge(START, "evaluate_speaking")
    graph.add_edge("evaluate_speaking", "evaluate_writing")
    graph.add_edge("evaluate_writing", "determine_placement")
    graph.add_edge("determine_placement", END)
    return graph.compile()


from typing import TypedDict, Dict, Any, Optional
from langgraph.graph import StateGraph, START, END

from app.services.speaking_evaluator import (
    evaluate_grammar,
    evaluate_vocabulary,
    evaluate_fluency,
    aggregate_speaking_feedback
)

class SpeakingFeedbackState(TypedDict):
    # Inputs
    transcript: str
    duration_sec: int
    word_count: int
    pause_count: int
    filler_words_count: int
    
    # Intermediate Results
    grammar_res: Optional[Dict[str, Any]]
    vocab_res: Optional[Dict[str, Any]]
    fluency_res: Optional[Dict[str, Any]]
    
    # Final Output
    final_results: Optional[Dict[str, Any]]


def grammar_node(state: SpeakingFeedbackState) -> SpeakingFeedbackState:
    res = evaluate_grammar(state["transcript"])
    return {"grammar_res": res}

def vocab_node(state: SpeakingFeedbackState) -> SpeakingFeedbackState:
    res = evaluate_vocabulary(state["transcript"])
    return {"vocab_res": res}

def fluency_node(state: SpeakingFeedbackState) -> SpeakingFeedbackState:
    res = evaluate_fluency(
        transcript=state["transcript"],
        duration_sec=state["duration_sec"],
        word_count=state["word_count"],
        pause_count=state["pause_count"],
        filler_words_count=state["filler_words_count"]
    )
    return {"fluency_res": res}

def aggregate_node(state: SpeakingFeedbackState) -> SpeakingFeedbackState:
    final = aggregate_speaking_feedback(
        grammar_res=state.get("grammar_res") or {},
        vocab_res=state.get("vocab_res") or {},
        fluency_res=state.get("fluency_res") or {},
        transcript=state.get("transcript") or ""
    )
    return {"final_results": final}

# Build Graph
workflow = StateGraph(SpeakingFeedbackState)

workflow.add_node("grammar", grammar_node)
workflow.add_node("vocabulary", vocab_node)
workflow.add_node("fluency", fluency_node)
workflow.add_node("aggregate", aggregate_node)

# Parallel branching (Fan-out)
workflow.add_edge(START, "grammar")
workflow.add_edge(START, "vocabulary")
workflow.add_edge(START, "fluency")

# Fan-in
workflow.add_edge(["grammar", "vocabulary", "fluency"], "aggregate")

# Terminate
workflow.add_edge("aggregate", END)

feedback_graph_app = workflow.compile()

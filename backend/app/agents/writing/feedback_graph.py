from typing import TypedDict, Dict, Any, List, Optional
from langgraph.graph import StateGraph, END
from app.services.gemini_client import generate_structured_response


class FeedbackState(TypedDict):
    text_content: str
    prompt_text: str
    prompt_type: str
    target_cefr_level: str
    grammar_report: Optional[Dict[str, Any]]
    structure_report: Optional[Dict[str, Any]]
    vocabulary_report: Optional[Dict[str, Any]]
    coherence_report: Optional[Dict[str, Any]]
    supervisor_report: Optional[Dict[str, Any]]


def start_node(state: FeedbackState) -> Dict[str, Any]:
    """Starting entry node for graph state initialization."""
    return {}


def grammar_node(state: FeedbackState) -> Dict[str, Any]:
    """Grammar checking node (low temp, rules-focused)."""
    prompt = f"""Evaluate the grammar, spelling, punctuation, and tense usage of the student's text.
Text to evaluate:
\"\"\"{state['text_content']}\"\"\"

Identify errors and provide replacements with explanations. Provide a grammar score out of 100."""

    schema = {
        "type": "object",
        "properties": {
            "score": {"type": "integer"},
            "issues": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "type": {"type": "string"},
                        "description": {"type": "string"},
                        "original_text": {"type": "string"},
                        "replacement_text": {"type": "string"},
                        "explanation": {"type": "string"},
                    },
                    "required": [
                        "type",
                        "description",
                        "original_text",
                        "replacement_text",
                        "explanation",
                    ],
                },
            },
        },
        "required": ["score", "issues"],
    }

    try:
        report = generate_structured_response(prompt, schema, temperature=0.1)
    except Exception as e:
        report = {
            "score": 70,
            "issues": [],
            "error": f"Failed to grade grammar: {str(e)}",
        }

    return {"grammar_report": report}


def structure_node(state: FeedbackState) -> Dict[str, Any]:
    """Structure & organization evaluation node."""
    prompt = f"""Evaluate the structure and flow of the student's text.
Focus on: paragraph organization, introduction/body/conclusion layout, transition words, and sentence length variety.
Text to evaluate:
\"\"\"{state['text_content']}\"\"\"

Provide a structure score out of 100, observation notes, and specific structure improvements."""

    schema = {
        "type": "object",
        "properties": {
            "score": {"type": "integer"},
            "notes": {"type": "array", "items": {"type": "string"}},
            "suggestions": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["score", "notes", "suggestions"],
    }

    try:
        report = generate_structured_response(prompt, schema, temperature=0.2)
    except Exception as e:
        report = {
            "score": 70,
            "notes": ["Failed to analyze structure due to an error."],
            "suggestions": [],
            "error": str(e),
        }

    return {"structure_report": report}


def vocabulary_node(state: FeedbackState) -> Dict[str, Any]:
    """Vocabulary Choice and CEFR level matching node."""
    prompt = f"""Evaluate the vocabulary choice of the student's text.
Target CEFR level: {state['target_cefr_level']}
Focus on: word repetition, overused basic words, CEFR-appropriate word upgrades, and context-correct usage.
Text to evaluate:
\"\"\"{state['text_content']}\"\"\"

Provide a vocabulary score out of 100, and a list of specific vocabulary upgrades."""

    schema = {
        "type": "object",
        "properties": {
            "score": {"type": "integer"},
            "suggestions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "original_word": {"type": "string"},
                        "suggested_word": {"type": "string"},
                        "context": {"type": "string"},
                        "explanation": {"type": "string"},
                    },
                    "required": [
                        "original_word",
                        "suggested_word",
                        "context",
                        "explanation",
                    ],
                },
            },
        },
        "required": ["score", "suggestions"],
    }

    try:
        report = generate_structured_response(prompt, schema, temperature=0.2)
    except Exception as e:
        report = {
            "score": 70,
            "suggestions": [],
            "error": f"Failed to grade vocabulary: {str(e)}",
        }

    return {"vocabulary_report": report}


def coherence_node(state: FeedbackState) -> Dict[str, Any]:
    """Coherence, reasoning flow, and prompt relevance evaluation node."""
    prompt = f"""Evaluate the coherence and topic relevance of the student's text relative to the given writing prompt.
Writing Prompt: "{state['prompt_text']}"
Prompt Type: {state['prompt_type']}

Text to evaluate:
\"\"\"{state['text_content']}\"\"\"

Provide a coherence score out of 100, evaluation notes, and notes on topic relevance."""

    schema = {
        "type": "object",
        "properties": {
            "score": {"type": "integer"},
            "notes": {"type": "array", "items": {"type": "string"}},
            "topic_relevance": {"type": "string"},
        },
        "required": ["score", "notes", "topic_relevance"],
    }

    try:
        report = generate_structured_response(prompt, schema, temperature=0.2)
    except Exception as e:
        report = {
            "score": 70,
            "notes": ["Failed to evaluate coherence due to an error."],
            "topic_relevance": "Unknown",
            "error": str(e),
        }

    return {"coherence_report": report}


def supervisor_node(state: FeedbackState) -> Dict[str, Any]:
    """Supervisor agent that merges inputs, resolves conflicts, and writes final verdict."""
    reports_text = f"""
Grammar Report: {state.get('grammar_report')}
Structure Report: {state.get('structure_report')}
Vocabulary Report: {state.get('vocabulary_report')}
Coherence Report: {state.get('coherence_report')}
"""

    prompt = f"""You are the ESL Supervisor. Your task is to merge the reports from 4 feedback agents (Grammar, Structure, Vocabulary, Coherence), resolve any overlaps, and compile final consolidated scores and summary feedback.
The student's essay text was written for a {state['prompt_type']} prompt: "{state['prompt_text']}" at a target CEFR level of {state['target_cefr_level']}.

Student Essay:
\"\"\"{state['text_content']}\"\"\"

Here are the individual agent reports:
\"\"\"
{reports_text}
\"\"\"

Calculate the overall score based on the weighted formula:
Overall Score = Grammar Score (30%) + Structure Score (30%) + Vocabulary Score (20%) + Coherence Score (20%).
Ensure the overall score is an integer between 0 and 100.
Provide a warm, encouraging, yet professional narrative summary. List 2-3 strengths, 2-3 improvements, and 3-5 specific actionable tips."""

    schema = {
        "type": "object",
        "properties": {
            "overall_score": {"type": "integer"},
            "grammar_score": {"type": "integer"},
            "structure_score": {"type": "integer"},
            "vocabulary_score": {"type": "integer"},
            "coherence_score": {"type": "integer"},
            "strengths": {"type": "array", "items": {"type": "string"}},
            "improvements": {"type": "array", "items": {"type": "string"}},
            "actionable_tips": {"type": "array", "items": {"type": "string"}},
            "narrative_summary": {"type": "string"},
        },
        "required": [
            "overall_score",
            "grammar_score",
            "structure_score",
            "vocabulary_score",
            "coherence_score",
            "strengths",
            "improvements",
            "actionable_tips",
            "narrative_summary",
        ],
    }

    try:
        report = generate_structured_response(prompt, schema, temperature=0.2)
    except Exception as e:
        def _safe_score(report_key: str) -> int:
            try:
                report = state.get(report_key)
                if isinstance(report, dict):
                    return int(report.get("score", 70))
            except (ValueError, TypeError, AttributeError):
                pass
            return 70

        g_score = _safe_score("grammar_report")
        s_score = _safe_score("structure_report")
        v_score = _safe_score("vocabulary_report")
        c_score = _safe_score("coherence_report")
        
        overall = int(g_score * 0.3 + s_score * 0.3 + v_score * 0.2 + c_score * 0.2)

        report = {
            "overall_score": overall,
            "grammar_score": g_score,
            "structure_score": s_score,
            "vocabulary_score": v_score,
            "coherence_score": c_score,
            "strengths": ["Your attempt is appreciated."],
            "improvements": [
                "Unable to compile detailed feedback due to temporary service availability issues."
            ],
            "actionable_tips": [
                "Review the raw text for flow and resubmit if necessary."
            ],
            "narrative_summary": f"Your essay has been recorded and evaluated. Overall score: {overall}.",
            "error": str(e),
        }

    return {"supervisor_report": report}


# Setup LangGraph workflow graph
workflow = StateGraph(FeedbackState)

# Register Nodes
workflow.add_node("start", start_node)
workflow.add_node("grammar", grammar_node)
workflow.add_node("structure", structure_node)
workflow.add_node("vocabulary", vocabulary_node)
workflow.add_node("coherence", coherence_node)
workflow.add_node("supervisor", supervisor_node)

# Define transitions
workflow.set_entry_point("start")
workflow.add_edge("start", "grammar")
workflow.add_edge("start", "structure")
workflow.add_edge("start", "vocabulary")
workflow.add_edge("start", "coherence")

workflow.add_edge("grammar", "supervisor")
workflow.add_edge("structure", "supervisor")
workflow.add_edge("vocabulary", "supervisor")
workflow.add_edge("coherence", "supervisor")

workflow.add_edge("supervisor", END)

# Compile graph app
feedback_graph = workflow.compile()

from typing import TypedDict, List, Dict, Any
from langgraph.graph import StateGraph, END
from app.services.gemini_client import generate_structured_response


class ComparisonState(TypedDict):
    previous_issues: List[Dict[str, Any]]
    current_issues: List[Dict[str, Any]]
    fixed_issues: List[Dict[str, Any]]
    still_present_issues: List[Dict[str, Any]]
    new_issues_introduced: List[Dict[str, Any]]


def compare_issues_node(state: ComparisonState) -> Dict[str, Any]:
    """
    Compare the previous version's error list against the current version's error list.
    Determines resolved issues, persistent issues, and newly introduced issues.
    """
    prev = state.get("previous_issues", [])
    curr = state.get("current_issues", [])

    if not prev and not curr:
        return {
            "fixed_issues": [],
            "still_present_issues": [],
            "new_issues_introduced": [],
        }

    prompt = f"""Compare the list of writing issues detected in the previous version of the essay vs the issues detected in the current revised version.

Previous issues:
\"\"\"
{prev}
\"\"\"

Current issues:
\"\"\"
{curr}
\"\"\"

Match the issues to determine:
1. Which previous issues have been resolved (fixed_issues).
2. Which previous issues are still present in the current version (still_present_issues).
3. Which new issues were introduced in the current version that were not in the previous version (new_issues_introduced).

Use semantic matching. If the student rephrased a sentence and the issue is still there but described slightly differently, it is "still_present_issues". If the issue is gone, it is "fixed_issues".
Strictly return a structured JSON response matching the required schema."""

    schema = {
        "type": "object",
        "properties": {
            "fixed_issues": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "description": {"type": "string"},
                        "original_text": {"type": "string"},
                    },
                    "required": ["description", "original_text"],
                },
            },
            "still_present_issues": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "description": {"type": "string"},
                        "original_text": {"type": "string"},
                    },
                    "required": ["description", "original_text"],
                },
            },
            "new_issues_introduced": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "description": {"type": "string"},
                        "original_text": {"type": "string"},
                    },
                    "required": ["description", "original_text"],
                },
            },
        },
        "required": [
            "fixed_issues",
            "still_present_issues",
            "new_issues_introduced",
        ],
    }

    try:
        report = generate_structured_response(prompt, schema, temperature=0.1)
    except Exception as e:
        report = {
            "fixed_issues": [],
            "still_present_issues": [],
            "new_issues_introduced": [],
            "error": str(e),
        }

    return report


workflow = StateGraph(ComparisonState)
workflow.add_node("compare", compare_issues_node)
workflow.set_entry_point("compare")
workflow.add_edge("compare", END)

revision_comparison_graph = workflow.compile()

import logging
from typing_extensions import TypedDict
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import uuid
import json

from langgraph.graph import StateGraph, END
from app.db.models.enums import AgentType, InterviewMode, PanelEndReason
from app.services.gemini_client import generate_structured_response

logger = logging.getLogger(__name__)

# ---------------------------------------------------------
# State Definition
# ---------------------------------------------------------
class PanelSessionState(TypedDict):
    session_id: str
    domain: str
    level: str
    role: Optional[str]
    company_style: Optional[str]
    interview_mode: str
    selected_agent_type: Optional[str]
    target_duration_minutes: int
    session_start_time_iso: str
    current_round: str
    current_agent: str
    topics_asked: List[str]
    transcript: List[Dict[str, Any]]
    questions_asked_this_round: int
    round_start_time_iso: str
    wildcards_used: int
    end_reason: Optional[str]
    
    # Turn output fields
    next_question_text: Optional[str]
    reaction_text: Optional[str]
    next_agent_for_ui: Optional[str]
    is_closing: bool


# ---------------------------------------------------------
# Graph Nodes
# ---------------------------------------------------------

def _call_gemini_for_agent(agent_type: str, state: PanelSessionState, system_prompt_extra: str = "") -> dict:
    """Helper to call Gemini for generating a question and reaction."""
    
    transcript_text = "\n".join([f"{t['speaker']}: {t['text']}" for t in state["transcript"][-5:]])
    if not transcript_text:
        transcript_text = "(Start of interview)"
        
    prompt = f"""
    You are the {agent_type} Interviewer for a {state['level']} level role in {state['domain']}.
    {system_prompt_extra}
    
    Recent transcript:
    {transcript_text}
    
    Your task:
    1. Acknowledge or react briefly to the candidate's last answer (reaction_text).
    2. Ask the next question (next_question_text).
    """
    
    schema = {
        "type": "object",
        "properties": {
            "reaction_text": {"type": "string"},
            "next_question_text": {"type": "string"}
        },
        "required": ["reaction_text", "next_question_text"]
    }
    
    try:
        return generate_structured_response(prompt, schema, temperature=0.7)
    except Exception as e:
        logger.error(f"Failed to generate {agent_type} response: {e}")
        return {
            "reaction_text": "Thank you for that answer.",
            "next_question_text": "Could you elaborate more on your experience?"
        }

def hr_agent_node(state: PanelSessionState) -> PanelSessionState:
    res = _call_gemini_for_agent("HR", state, "Focus on culture fit, teamwork, and behavioral scenarios.")
    state["reaction_text"] = res["reaction_text"]
    state["next_question_text"] = res["next_question_text"]
    state["questions_asked_this_round"] += 1
    return state

def technical_agent_node(state: PanelSessionState) -> PanelSessionState:
    res = _call_gemini_for_agent("Technical", state, "Focus on domain-specific hard skills, problem-solving, and technical accuracy.")
    state["reaction_text"] = res["reaction_text"]
    state["next_question_text"] = res["next_question_text"]
    state["questions_asked_this_round"] += 1
    return state

def manager_agent_node(state: PanelSessionState) -> PanelSessionState:
    res = _call_gemini_for_agent("Manager", state, "Focus on big-picture thinking, leadership, and project impact.")
    state["reaction_text"] = res["reaction_text"]
    state["next_question_text"] = res["next_question_text"]
    state["questions_asked_this_round"] += 1
    return state

def closing_node(state: PanelSessionState) -> PanelSessionState:
    state["is_closing"] = True
    state["reaction_text"] = "Thank you for your time today."
    state["next_question_text"] = "We will be in touch with you shortly. Have a great day!"
    
    # Determine end reason based on time
    start_time = datetime.fromisoformat(state["session_start_time_iso"])
    elapsed_minutes = (datetime.now(timezone.utc) - start_time).total_seconds() / 60.0
    
    if elapsed_minutes >= 30:
        state["end_reason"] = PanelEndReason.HARD_CEILING_REACHED.value
    elif elapsed_minutes >= (state["target_duration_minutes"] * 0.85):
        state["end_reason"] = PanelEndReason.USER_TARGET_REACHED.value
    else:
        state["end_reason"] = PanelEndReason.NATURAL.value
        
    return state

def handoff_node(state: PanelSessionState) -> PanelSessionState:
    # Switch agent and round
    current_agent = state["current_agent"]
    
    if state["interview_mode"] == InterviewMode.SINGLE_AGENT.value:
        # Just reset sub-topic counters
        state["questions_asked_this_round"] = 0
        state["reaction_text"] = "Let's pivot to a slightly different topic now."
        state["next_question_text"] = ""
        return state
        
    if current_agent == AgentType.HR.value:
        state["current_agent"] = AgentType.TECHNICAL.value
        state["current_round"] = "2"
        state["reaction_text"] = "I'm going to hand you over to our Technical Lead now."
    elif current_agent == AgentType.TECHNICAL.value:
        state["current_agent"] = AgentType.MANAGER.value
        state["current_round"] = "3"
        state["reaction_text"] = "Great. I'll pass you to the Hiring Manager for the final round."
        
    state["next_agent_for_ui"] = state["current_agent"]
    state["questions_asked_this_round"] = 0
    state["next_question_text"] = "Hello! I'll be taking over for this next segment."
    return state

# ---------------------------------------------------------
# Routing Logic
# ---------------------------------------------------------
def orchestrator_router(state: PanelSessionState) -> str:
    """Decides the next node to execute based on state. Purely reads state."""
    
    # Check elapsed time
    start_time = datetime.fromisoformat(state["session_start_time_iso"])
    elapsed_minutes = (datetime.now(timezone.utc) - start_time).total_seconds() / 60.0
    
    if elapsed_minutes >= 30:
        return "closing_node"
        
    target = state["target_duration_minutes"]
    if elapsed_minutes >= (target * 0.85):
        if not state["is_closing"]:
            return "closing_node"
            
    # Check if current round is complete
    max_questions = 3 if state["interview_mode"] == InterviewMode.FULL_PANEL.value else 10
    
    if state["questions_asked_this_round"] >= max_questions:
        if state["current_round"] == "3" or state["interview_mode"] == InterviewMode.SINGLE_AGENT.value:
            return "closing_node"
        else:
            return "handoff_node"
            
    # Otherwise route to the active agent
    if state["current_agent"] == AgentType.HR.value:
        return "hr_agent_node"
    elif state["current_agent"] == AgentType.TECHNICAL.value:
        return "technical_agent_node"
    elif state["current_agent"] == AgentType.MANAGER.value:
        return "manager_agent_node"
        
    return "closing_node"

# ---------------------------------------------------------
# Graph Compilation
# ---------------------------------------------------------
builder = StateGraph(PanelSessionState)

# Add nodes
builder.add_node("hr_agent_node", hr_agent_node)
builder.add_node("technical_agent_node", technical_agent_node)
builder.add_node("manager_agent_node", manager_agent_node)
builder.add_node("handoff_node", handoff_node)
builder.add_node("closing_node", closing_node)

# Add conditional edges from start (the orchestrator router)
builder.set_conditional_entry_point(
    orchestrator_router,
    {
        "hr_agent_node": "hr_agent_node",
        "technical_agent_node": "technical_agent_node",
        "manager_agent_node": "manager_agent_node",
        "handoff_node": "handoff_node",
        "closing_node": "closing_node"
    }
)

# After an agent/handoff/closing node executes, we just end the graph execution
# because this is a discrete HTTP turn. The updated state is returned to the user.
builder.add_edge("hr_agent_node", END)
builder.add_edge("technical_agent_node", END)
builder.add_edge("manager_agent_node", END)
builder.add_edge("handoff_node", END)
builder.add_edge("closing_node", END)

panel_graph = builder.compile()

def process_interview_turn(state: PanelSessionState) -> PanelSessionState:
    """
    Executes one turn of the interview graph.
    """
    result = panel_graph.invoke(state)
    return result

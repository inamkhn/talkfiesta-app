import logging
from typing import Dict, Any

from app.services.gemini_client import generate_structured_response

logger = logging.getLogger(__name__)

def evaluate_grammar(transcript: str) -> Dict[str, Any]:
    prompt = f"""
    You are an expert English Grammar evaluator. Analyze the following spoken transcript for grammatical correctness.
    Return a score out of 100, and a list of specific grammar corrections if any.
    
    Transcript:
    "{transcript}"
    """
    
    schema = {
        "type": "object",
        "properties": {
            "grammar_score": {"type": "integer"},
            "corrections": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "original": {"type": "string"},
                        "corrected": {"type": "string"},
                        "explanation": {"type": "string"}
                    },
                    "required": ["original", "corrected", "explanation"]
                }
            }
        },
        "required": ["grammar_score", "corrections"]
    }
    
    try:
        return generate_structured_response(prompt, schema, temperature=0.2)
    except Exception as e:
        logger.error(f"Grammar evaluation failed: {e}")
        return {"grammar_score": 0, "corrections": []}


def evaluate_vocabulary(transcript: str) -> Dict[str, Any]:
    prompt = f"""
    You are an expert English Vocabulary evaluator. Analyze the following spoken transcript for vocabulary richness, variety, and appropriateness.
    Return a score out of 100, and a list of vocabulary suggestions (better alternatives for words used).
    
    Transcript:
    "{transcript}"
    """
    
    schema = {
        "type": "object",
        "properties": {
            "vocabulary_score": {"type": "integer"},
            "suggestions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "word_used": {"type": "string"},
                        "better_alternative": {"type": "string"},
                        "reason": {"type": "string"}
                    },
                    "required": ["word_used", "better_alternative", "reason"]
                }
            }
        },
        "required": ["vocabulary_score", "suggestions"]
    }
    
    try:
        return generate_structured_response(prompt, schema, temperature=0.3)
    except Exception as e:
        logger.error(f"Vocabulary evaluation failed: {e}")
        return {"vocabulary_score": 0, "suggestions": []}


def evaluate_fluency(transcript: str, duration_sec: int, word_count: int, pause_count: int, filler_words_count: int) -> Dict[str, Any]:
    wpm = (word_count / duration_sec) * 60 if duration_sec > 0 else 0
    prompt = f"""
    You are an expert English Fluency evaluator. Analyze the following spoken transcript and audio metrics.
    Return a fluency score out of 100.
    
    Metrics:
    - Duration: {duration_sec} seconds
    - Word Count: {word_count}
    - Words Per Minute: {wpm:.1f}
    - Pause Count: {pause_count}
    - Filler Words Count: {filler_words_count}
    
    Transcript:
    "{transcript}"
    """
    
    schema = {
        "type": "object",
        "properties": {
            "fluency_score": {"type": "integer"}
        },
        "required": ["fluency_score"]
    }
    
    try:
        return generate_structured_response(prompt, schema, temperature=0.2)
    except Exception as e:
        logger.error(f"Fluency evaluation failed: {e}")
        return {"fluency_score": 0}


def aggregate_speaking_feedback(
    grammar_res: Dict[str, Any],
    vocab_res: Dict[str, Any],
    fluency_res: Dict[str, Any],
    transcript: str
) -> Dict[str, Any]:
    
    grammar_score = grammar_res.get("grammar_score", 0)
    vocab_score = vocab_res.get("vocabulary_score", 0)
    fluency_score = fluency_res.get("fluency_score", 0)
    
    prompt = f"""
    You are the Lead English Evaluator. You have received reports from Grammar, Vocabulary, and Fluency agents.
    Synthesize their findings into a cohesive final feedback report.
    
    Grammar Score: {grammar_score}/100
    Vocabulary Score: {vocab_score}/100
    Fluency Score: {fluency_score}/100
    
    Transcript: "{transcript}"
    """
    
    schema = {
        "type": "object",
        "properties": {
            "overall_score": {"type": "integer"},
            "fluency_feedback": {"type": "string"},
            "grammar_feedback": {"type": "string"},
            "vocabulary_feedback": {"type": "string"},
            "overall_strengths": {"type": "string"},
            "areas_for_improvement": {"type": "string"}
        },
        "required": ["overall_score", "fluency_feedback", "grammar_feedback", "vocabulary_feedback", "overall_strengths", "areas_for_improvement"]
    }
    
    try:
        synthesis = generate_structured_response(prompt, schema, temperature=0.4)
    except Exception as e:
        logger.error(f"Feedback aggregation failed: {e}")
        synthesis = {
            "overall_score": int((grammar_score + vocab_score + fluency_score) / 3),
            "fluency_feedback": "N/A",
            "grammar_feedback": "N/A",
            "vocabulary_feedback": "N/A",
            "overall_strengths": "N/A",
            "areas_for_improvement": "N/A"
        }
        
    return {
        "grammar_score": grammar_score,
        "vocabulary_score": vocab_score,
        "fluency_score": fluency_score,
        "overall_score": synthesis["overall_score"],
        "grammar_corrections": grammar_res.get("corrections", []),
        "vocabulary_suggestions": vocab_res.get("suggestions", []),
        "ai_feedback": {
            "fluency_feedback": synthesis["fluency_feedback"],
            "grammar_feedback": synthesis["grammar_feedback"],
            "vocabulary_feedback": synthesis["vocabulary_feedback"],
            "overall_strengths": synthesis["overall_strengths"],
            "areas_for_improvement": synthesis["areas_for_improvement"]
        }
    }

def process_transcript_evaluation(
    transcript: str, 
    duration_sec: int, 
    word_count: int, 
    pause_count: int, 
    filler_words_count: int
) -> Dict[str, Any]:
    """
    Orchestrates the Multi-Agent evaluation pipeline.
    Runs Grammar, Vocabulary, and Fluency evaluations sequentially, then aggregates.
    """
    # 1. Grammar Agent
    grammar_res = evaluate_grammar(transcript)
    
    # 2. Vocabulary Agent
    vocab_res = evaluate_vocabulary(transcript)
    
    # 3. Fluency Agent
    fluency_res = evaluate_fluency(transcript, duration_sec, word_count, pause_count, filler_words_count)
    
    # 4. Aggregator
    final_results = aggregate_speaking_feedback(grammar_res, vocab_res, fluency_res, transcript)
    
    return final_results

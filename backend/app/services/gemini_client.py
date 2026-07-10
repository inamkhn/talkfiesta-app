import json
import logging
from typing import Any, Dict
from google import genai
from google.genai.errors import APIError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.core.config import settings

logger = logging.getLogger("app.services.gemini")


class GeminiAPIError(Exception):
    """Exception raised when the Gemini API returns an error or fails."""
    pass


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((APIError, GeminiAPIError)),
    reraise=True,
)
def generate_structured_response(
    prompt: str,
    response_schema: Dict[str, Any],
    temperature: float = 0.2,
    model: str = "gemini-1.5-flash",
) -> Dict[str, Any]:
    """
    Call Gemini API with a prompt and retrieve a validated structured JSON response.
    Uses the official google-genai SDK.
    """
    api_key = settings.GEMINI_API_KEY
    if not api_key:
        logger.error("GEMINI_API_KEY is not set in environment or configuration.")
        raise ValueError("GEMINI_API_KEY is not configured")

    client = genai.Client(api_key=api_key)
    
    try:
        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=genai.types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=response_schema,
                temperature=temperature,
            ),
        )
        
        text_response = response.text
        if not text_response:
            raise GeminiAPIError("Empty text block returned from Gemini")
            
        return json.loads(text_response)
        
    except APIError as exc:
        logger.error(f"Google GenAI SDK API error: {exc}")
        raise exc
    except json.JSONDecodeError as exc:
        logger.error(f"Failed to parse Gemini API response as JSON: {exc}")
        raise GeminiAPIError(f"Malformed JSON response from Gemini API: {exc}")
    except Exception as exc:
        logger.error(f"Unexpected error calling Gemini API: {exc}")
        raise GeminiAPIError(f"Unexpected error calling Gemini API: {exc}")


def grade_context_sentences(word_sentence_pairs: list) -> dict:
    """
    Evaluates 5 word-sentence pairs for correct grammar and vocabulary usage.
    Returns list of evaluations.
    """
    prompt = "You are a professional ESL teacher. Evaluate the following list of words and sentences written by a student. " \
             "Determine if the student used the target word correctly in context and if the sentence is grammatically correct. " \
             "Provide actionable and encouraging feedback. Here are the submissions:\n\n"
             
    for idx, item in enumerate(word_sentence_pairs):
        prompt += f"Pair {idx+1}:\n- Target Word: {item['word']}\n- Definition: {item['definition']}\n- Student Sentence: {item['sentence']}\n\n"
        
    prompt += "Evaluate each pair. You must strictly output JSON matching the required schema."
    
    # OpenAPI Schema for the expected response
    schema = {
        "type": "object",
        "properties": {
            "results": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "word_id": {"type": "string"},
                        "is_correct": {"type": "boolean"},
                        "feedback": {"type": "string"},
                    },
                    "required": ["word_id", "is_correct", "feedback"],
                },
            }
        },
        "required": ["results"],
    }
    
    try:
        response_data = generate_structured_response(prompt, schema)
        return response_data
    except Exception as exc:
        logger.error(f"Failed to grade context sentences using Gemini: {exc}")
        # Graceful degradation: fallback if AI fails, mark everything as True with a warning feedback
        fallback_results = []
        for item in word_sentence_pairs:
            fallback_results.append({
                "word_id": str(item["word_id"]),
                "is_correct": True,
                "feedback": "Grading failed due to temporary AI unavailability. Your sentence has been accepted.",
            })
        return {"results": fallback_results}

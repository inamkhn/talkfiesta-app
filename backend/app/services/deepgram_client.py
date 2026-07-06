import logging
import httpx
import random
from typing import Optional

from app.core.config import settings

logger = logging.getLogger("app.services.deepgram")


class DeepgramAPIError(Exception):
    """Exception raised when Deepgram API returns an error or fails."""
    pass


def transcribe_audio(audio_url: str, target_word: Optional[str] = None) -> str:
    """
    Transcribes audio from a URL using Deepgram REST API.
    If DEEPGRAM_API_KEY is not configured or an error occurs, falls back to
    a simulated transcription of the target word for dev testing.
    """
    api_key = settings.DEEPGRAM_API_KEY
    if not api_key:
        logger.warning("DEEPGRAM_API_KEY not configured. Using simulated transcription.")
        return _simulate_transcription(target_word)

    url = "https://api.deepgram.com/v1/listen?model=nova-2&smart_format=true"
    headers = {
        "Authorization": f"Token {api_key}",
        "Content-Type": "application/json"
    }
    payload = {"url": audio_url}

    try:
        with httpx.Client(timeout=15.0) as client:
            response = client.post(url, json=payload, headers=headers)
            if response.status_code != 200:
                logger.error(f"Deepgram API error ({response.status_code}): {response.text}")
                raise DeepgramAPIError(f"Deepgram returned status {response.status_code}")
            
            data = response.json()
            channels = data.get("results", {}).get("channels", [])
            if not channels:
                raise DeepgramAPIError("Malformed Deepgram response (no channels)")
            
            alternatives = channels[0].get("alternatives", [])
            if not alternatives:
                raise DeepgramAPIError("Malformed Deepgram response (no alternatives)")
                
            transcript = alternatives[0].get("transcript", "").strip()
            return transcript
            
    except Exception as e:
        logger.error(f"Deepgram transcription failed: {e}. Falling back to simulation.")
        return _simulate_transcription(target_word)


def _simulate_transcription(target_word: Optional[str]) -> str:
    """
    Simulates pronunciation transcription for MVP/development.
    Returns the target word exactly 80% of the time, and a slightly incorrect word 20% of the time.
    """
    if not target_word:
        return "hello"
        
    target_word = target_word.strip()
    
    # 80% chance of correct pronunciation
    if random.random() < 0.8:
        return target_word
        
    # 20% chance of a minor typo or deviation
    if len(target_word) > 3:
        idx = random.randint(0, len(target_word) - 1)
        # Substitute a character
        substitute_char = random.choice("aeiou" if target_word[idx] in "aeiou" else "bcdfghjklmnpqrstvwxyz")
        simulated = target_word[:idx] + substitute_char + target_word[idx+1:]
        # Ensure it's not the same
        if simulated == target_word:
            simulated += "s"
        return simulated
    return target_word + "s"

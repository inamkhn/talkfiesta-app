import logging
from typing import List
from sqlalchemy.orm import Session

from app.services.gemini_client import generate_structured_response
from app.schemas.generation import (
    GeneratedSpeakingBatch,
    GeneratedWritingBatch,
    GeneratedVocabularyBatch
)
from app.db.models.speaking import SpeakingExercise
from app.db.models.writing import WritingPrompt
from app.db.models.vocabulary import VocabularyWord, VocabularyExerciseBank
from app.db.models.enums import ContentSource, ReviewStatus, SpeakingExerciseType, WritingPromptType

logger = logging.getLogger(__name__)


def generate_speaking_exercises(
    db: Session, cefr_level: str, cycle: int, start_day: int, count: int = 1
) -> List[SpeakingExercise]:
    """Generates and saves speaking exercises using Gemini."""
    logger.info(f"Generating {count} speaking exercises for CEFR {cefr_level}, Cycle {cycle}, starting Day {start_day}")
    
    prompt = f"""
    You are an expert ESL curriculum designer. 
    Generate {count} unique speaking exercises for a {cefr_level} level English learner.
    The exercises should be conversational topics or roleplays.
    Ensure difficulty and vocabulary matches {cefr_level}.
    """
    
    # Passing the Pydantic schema class directly
    try:
        response_dict = generate_structured_response(prompt, response_schema=GeneratedSpeakingBatch)
        batch = GeneratedSpeakingBatch(**response_dict)
    except Exception as e:
        logger.error(f"Failed to generate speaking exercises: {e}")
        raise e

    exercises = []
    for i, ex in enumerate(batch.exercises):
        new_exercise = SpeakingExercise(
            cycle=cycle,
            day=start_day + i,
            type=SpeakingExerciseType.CONVERSATIONAL,
            topic=ex.topic,
            difficulty_level=ex.difficulty_level,
            prompt_text=ex.prompt_text,
            target_duration_seconds=ex.target_duration_seconds,
            instructions=ex.instructions,
            target_cefr_level=cefr_level,
            goal_tags=ex.goal_tags,
            generated_by=ContentSource.AI_GENERATED,
            review_status=ReviewStatus.AUTO_APPROVED
        )
        db.add(new_exercise)
        exercises.append(new_exercise)
        
    db.commit()
    logger.info(f"Successfully saved {len(exercises)} speaking exercises.")
    return exercises


def generate_writing_prompts(
    db: Session, cefr_level: str, cycle: int, start_day: int, count: int = 1
) -> List[WritingPrompt]:
    """Generates and saves writing prompts using Gemini."""
    logger.info(f"Generating {count} writing prompts for CEFR {cefr_level}, Cycle {cycle}, starting Day {start_day}")
    
    prompt = f"""
    You are an expert ESL curriculum designer. 
    Generate {count} unique writing prompts for a {cefr_level} level English learner.
    The prompts should vary (e.g., email, essay, creative story) but fit the {cefr_level} level perfectly.
    """
    
    try:
        response_dict = generate_structured_response(prompt, response_schema=GeneratedWritingBatch)
        batch = GeneratedWritingBatch(**response_dict)
    except Exception as e:
        logger.error(f"Failed to generate writing prompts: {e}")
        raise e

    prompts = []
    for i, p in enumerate(batch.prompts):
        new_prompt = WritingPrompt(
            cycle=cycle,
            day=start_day + i,
            type=WritingPromptType.ESSAY,  # Defaulting to essay for simplicity
            difficulty_level=p.difficulty_level,
            prompt_title=p.prompt_title,
            prompt_text=p.prompt_text,
            target_word_count=p.target_word_count,
            time_limit_minutes=p.time_limit_minutes,
            focus_areas=p.focus_areas,
            writing_tips=p.writing_tips,
            sample_outline=p.sample_outline,
            generated_by=ContentSource.AI_GENERATED,
            review_status=ReviewStatus.AUTO_APPROVED
        )
        db.add(new_prompt)
        prompts.append(new_prompt)
        
    db.commit()
    logger.info(f"Successfully saved {len(prompts)} writing prompts.")
    return prompts


def generate_vocabulary_words(
    db: Session, cefr_level: str, cycle: int, start_day: int, count: int = 1
) -> List[VocabularyWord]:
    """Generates and saves vocabulary words and their exercises using Gemini."""
    logger.info(f"Generating {count} vocabulary words for CEFR {cefr_level}, Cycle {cycle}, starting Day {start_day}")
    
    prompt = f"""
    You are an expert ESL curriculum designer. 
    Generate {count} unique, highly useful vocabulary words for a {cefr_level} level English learner.
    For each word, provide definitions, examples, and generate a specific quiz bank (fill in the blank, and 3 matching distractors).
    """
    
    try:
        response_dict = generate_structured_response(prompt, response_schema=GeneratedVocabularyBatch)
        batch = GeneratedVocabularyBatch(**response_dict)
    except Exception as e:
        logger.error(f"Failed to generate vocabulary words: {e}")
        raise e

    words = []
    for i, w in enumerate(batch.words):
        # We might have multiple words per day, but here we just map 1 word = 1 day for simplicity of the script, 
        # or we could put them all on the same day. Let's increment day per word for now.
        new_word = VocabularyWord(
            word=w.word.lower(),
            definition=w.definition,
            part_of_speech=w.part_of_speech,
            difficulty_level=w.difficulty_level,
            pronunciation_ipa=w.pronunciation_ipa,
            example_sentences=w.example_sentences,
            synonyms=w.synonyms,
            antonyms=w.antonyms,
            usage_tips=w.usage_tips,
            category=w.category,
            target_cefr_level=cefr_level,
            cycle=cycle,
            day=start_day + i,
            generated_by=ContentSource.AI_GENERATED,
            review_status=ReviewStatus.AUTO_APPROVED
        )
        db.add(new_word)
        db.flush() # get ID
        
        # Add the exercise bank
        exercise_bank = VocabularyExerciseBank(
            word_id=new_word.id,
            fill_blank_sentence=w.exercises.fill_blank_sentence,
            fill_blank_correct_answer=w.exercises.fill_blank_correct_answer,
            match_definition_distractor_1=w.exercises.match_definition_distractor_1,
            match_definition_distractor_2=w.exercises.match_definition_distractor_2,
            match_definition_distractor_3=w.exercises.match_definition_distractor_3
        )
        db.add(exercise_bank)
        words.append(new_word)
        
    db.commit()
    logger.info(f"Successfully saved {len(words)} vocabulary words and exercises.")
    return words

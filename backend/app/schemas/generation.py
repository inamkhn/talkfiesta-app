from pydantic import BaseModel, Field
from typing import List, Optional

# ----------------------------------------
# Speaking Generation Schema
# ----------------------------------------
class GeneratedSpeakingExercise(BaseModel):
    """Schema for Gemini to generate a single speaking exercise."""
    topic: str = Field(description="The main topic of the speaking exercise.")
    difficulty_level: str = Field(description="The CEFR level (e.g., A1, B2, C1).")
    prompt_text: str = Field(description="The main question or scenario the user must speak about.")
    target_duration_seconds: int = Field(description="Suggested duration in seconds (e.g. 60, 120).")
    instructions: str = Field(description="Brief instructions for the user (e.g., 'Make sure to mention X and Y').")
    goal_tags: List[str] = Field(description="2-4 learning goals or tags (e.g., 'Past Tense', 'Travel Vocabulary').")


class GeneratedSpeakingBatch(BaseModel):
    exercises: List[GeneratedSpeakingExercise]


# ----------------------------------------
# Writing Generation Schema
# ----------------------------------------
class GeneratedWritingPrompt(BaseModel):
    """Schema for Gemini to generate a single writing prompt."""
    difficulty_level: str = Field(description="The CEFR level (e.g., A1, B2, C1).")
    prompt_title: str = Field(description="A catchy, concise title for the essay or writing task.")
    prompt_text: str = Field(description="The detailed prompt explaining what the user needs to write.")
    target_word_count: int = Field(description="Recommended word count (e.g., 150, 250).")
    time_limit_minutes: int = Field(description="Suggested time limit in minutes.")
    focus_areas: List[str] = Field(description="2-4 grammatical or stylistic focus areas (e.g., 'Use transitional phrases').")
    writing_tips: str = Field(description="A short tip to help the user start.")
    sample_outline: str = Field(description="A 3-4 bullet point outline to guide the user's structure.")


class GeneratedWritingBatch(BaseModel):
    prompts: List[GeneratedWritingPrompt]


# ----------------------------------------
# Vocabulary Generation Schema
# ----------------------------------------
class GeneratedVocabularyExerciseBank(BaseModel):
    """Schema for Gemini to generate exercises associated with a specific word."""
    fill_blank_sentence: str = Field(description="A sentence demonstrating the word, with the word replaced by '_____'.")
    fill_blank_correct_answer: str = Field(description="The exact word that goes in the blank.")
    match_definition_distractor_1: str = Field(description="A plausible but incorrect definition for a matching quiz.")
    match_definition_distractor_2: str = Field(description="Another plausible but incorrect definition.")
    match_definition_distractor_3: str = Field(description="A third plausible but incorrect definition.")


class GeneratedVocabularyWord(BaseModel):
    """Schema for Gemini to generate a single vocabulary word and its metadata."""
    word: str = Field(description="The vocabulary word itself.")
    definition: str = Field(description="Clear, CEFR-appropriate definition of the word.")
    part_of_speech: str = Field(description="Part of speech (e.g., noun, verb, adjective).")
    difficulty_level: str = Field(description="The CEFR level (e.g., A1, B2, C1).")
    pronunciation_ipa: str = Field(description="The International Phonetic Alphabet (IPA) spelling.")
    example_sentences: List[str] = Field(description="2-3 example sentences using the word in context.")
    synonyms: List[str] = Field(description="2-4 synonyms.")
    antonyms: List[str] = Field(description="2-4 antonyms.")
    usage_tips: str = Field(description="A tip on how to naturally use the word in conversation.")
    category: str = Field(description="The semantic category (e.g., 'Business', 'Travel', 'Emotions').")
    exercises: GeneratedVocabularyExerciseBank = Field(description="Quiz questions for this word.")


class GeneratedVocabularyBatch(BaseModel):
    words: List[GeneratedVocabularyWord]

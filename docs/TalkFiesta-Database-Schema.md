# 🗄️ TalkFiesta — Database Schema Design

**Companion document to `TalkFiesta-Codebase-Structure.md`**

> Defines the PostgreSQL database schema for the TalkFiesta application, using SQLAlchemy models. This schema integrates with **JWT + NextAuth.js** for authentication.

---

## Table of Contents

1. Authentication & Users (JWT + NextAuth)
2. Speaking Module
3. Vocabulary Module
4. Writing Module
5. Interview Panel Module
6. Progress & Achievements
7. Offline Content Generation

---

## 1. Authentication & Users (JWT + NextAuth)

The application uses **JWT-based authentication** via FastAPI's `security.py` on the backend and **NextAuth.js** on the frontend for session/cookie handling. Passwords are hashed (bcrypt) and stored in the `users` table. Social OAuth (Google) is handled via NextAuth.js, which forwards validated identity to the FastAPI backend.

### `users`
Core identity table. JWT tokens are issued against this record.

| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | `PRIMARY KEY` | Internal database unique identifier (uuid4). |
| `email` | `String` | `UNIQUE`, `INDEX`, `NOT NULL` | User's email address. |
| `hashed_password` | `String` | `NULLABLE` | bcrypt-hashed password (NULL for OAuth-only users). |
| `first_name` | `String` | `NULLABLE` | |
| `last_name` | `String` | `NULLABLE` | |
| `avatar_url` | `String` | `NULLABLE` | |
| `oauth_provider` | `Enum` | `NULLABLE` | `GOOGLE` (NULL for email/password users). |
| `oauth_provider_id` | `String` | `NULLABLE` | The user's ID from the OAuth provider. |
| `onboarding_completed`| `Boolean`| `DEFAULT FALSE` | Has the user completed level assessment + goal selection? |
| `is_active` | `Boolean` | `DEFAULT TRUE` | Soft-delete / account disable flag. |
| `created_at` | `DateTime` | `DEFAULT NOW()` | Record creation timestamp. |
| `updated_at` | `DateTime` | `DEFAULT NOW()` | Record update timestamp. |
| `last_login_at` | `DateTime` | `NULLABLE` | Tracks the last time the user logged in. |

### `user_learning_profiles`
Separates the user's core identity from their TalkFiesta learning state and preferences. Created during onboarding after level assessment and goal selection.

| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | `PRIMARY KEY` | Unique identifier (uuid4). |
| `user_id` | `UUID` | `UNIQUE`, `FOREIGN KEY (users.id)` | Link to the core user record (`ON DELETE CASCADE`). |
| `current_cycle` | `Integer` | `DEFAULT 1` | The user's current 21-day learning cycle (1-5). |
| `current_day` | `Integer` | `DEFAULT 1` | The user's current day within the cycle (1-21). |
| `goal` | `Enum` | `NOT NULL` | User's learning goal: `FLUENCY`, `BUSINESS`, `EXAM`, `TRAVEL`. |
| `target_cefr_level` | `String` | `NOT NULL` | Assessed CEFR level from onboarding quiz (e.g., "A2", "B1", "B2", "C1"). |
| `native_language` | `String` | `NULLABLE` | Used for personalized feedback context. |
| `timezone` | `String` | `DEFAULT 'UTC'` | User's local timezone. |
| `daily_reminder_enabled`| `Boolean`| `DEFAULT TRUE` | Preference for push/email reminders. |
| `created_at` | `DateTime` | `DEFAULT NOW()` | |
| `updated_at` | `DateTime` | `DEFAULT NOW()` | |

---

## 2. Speaking Module

Handles both Batch (Scripted) exercises and Streaming (Live) sessions.

### `speaking_exercises`
Pre-generated exercise prompts for the 21-day cycle. Generated once per cycle by the offline content pipeline and shared across all users.

| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | `PRIMARY KEY` |  |
| `cycle` | `Integer` | `NOT NULL` | Cycle number (1-5). |
| `day` | `Integer` | `NOT NULL` | Day number (1-21). |
| `type` | `Enum` | `NOT NULL` | `CONVERSATIONAL`, `PUBLIC_SPEAKING`, `IMPROMPTU`. |
| `topic` | `String` | `NOT NULL` | Topic title for display (e.g., "Talking About Your Hometown"). |
| `difficulty_level` | `String` | `NOT NULL` | Difficulty label (e.g., "A2-B1"). |
| `prompt_text` | `Text` | `NOT NULL` | The full scenario and instructions given to the user. |
| `target_duration_seconds`| `Integer`| `NOT NULL` | Recommended speaking duration. |
| `instructions` | `Text` | `NULLABLE` | Additional guidance for the exercise. |
| `target_cefr_level`| `String` | `NOT NULL` | CEFR level this exercise targets (e.g., "B1"). |
| `goal_tags` | `JSONB` | `DEFAULT '[]'` | Which goal-specific Tier 2 variants exist (e.g., `["business", "exam"]`). |
| `topic_embedding` | `VECTOR` | `NULLABLE` | Embedding for deduplication similarity search against all exercises. |
| `generated_by` | `Enum` | `NOT NULL` | `AI`, `HUMAN`. |
| `review_status` | `Enum` | `NOT NULL` | `DRAFT`, `APPROVED`, `REJECTED`, `PUBLISHED`. |
| `reviewed_by` | `UUID` | `NULLABLE`, `FOREIGN KEY (users.id)` | Admin user who reviewed this exercise. |
| `generation_batch_id`| `UUID` | `FOREIGN KEY` | Link to the `content_generation_batches` row. |
| `created_at` | `DateTime` | `DEFAULT NOW()` |  |
| `updated_at` | `DateTime` | `DEFAULT NOW()` |  |

### `speaking_submissions`
User's recorded response to an exercise and the resulting multi-agent feedback. Processed asynchronously via the Celery job queue.

| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | `PRIMARY KEY` |  |
| `user_id` | `UUID` | `FOREIGN KEY (users.id)` |  |
| `exercise_id` | `UUID` | `FOREIGN KEY (speaking_exercises.id)` |  |
| `daily_activity_id` | `UUID` | `NULLABLE`, `FOREIGN KEY` | Link to `daily_progress` for unified tracking. |
| `audio_url` | `String` | `NOT NULL` | S3 / Supabase storage link. |
| `transcript` | `Text` | `NULLABLE` | Full transcription from Deepgram. |
| `duration_seconds` | `Integer` | `NULLABLE` | Length of the recording. |
| `word_count` | `Integer` | `NULLABLE` | Words spoken (from transcript). |
| `words_per_minute` | `Float` | `NULLABLE` | Speaking pace. |
| `pause_count` | `Integer` | `NULLABLE` | Gaps > 0.5s detected between words. |
| `filler_words_count` | `Integer` | `NULLABLE` | Count of "um", "uh", "like", "you know". |
| `filler_words_list` | `JSONB` | `NULLABLE` | Array of detected filler words with positions. |
| `fluency_score` | `Integer` | `NULLABLE` | 0–100 score from Fluency Agent (pace, pauses, fillers). |
| `grammar_score` | `Integer` | `NULLABLE` | 0–100 score from Grammar Agent. |
| `vocabulary_score` | `Integer` | `NULLABLE` | 0–100 score from Vocabulary Agent. |
| `pronunciation_score` | `Integer`| `NULLABLE` | 0–100 score from Pronunciation analysis. |
| `overall_score` | `Integer`| `NULLABLE` | Weighted aggregate score (0–100). |
| `grammar_corrections` | `JSONB` | `NULLABLE` | Inline error list with positions and explanations. |
| `vocabulary_suggestions`| `JSONB` | `NULLABLE` | Word upgrade suggestions from Vocabulary Agent. |
| `ai_feedback` | `JSONB` | `NULLABLE` | Merged narrative feedback from the Score Aggregator node. |
| `status` | `Enum` | `DEFAULT 'PENDING'` | `PENDING`, `PROCESSING`, `COMPLETED`, `FAILED`. |
| `processing_job_id` | `String` | `NULLABLE` | Celery task ID for the async feedback pipeline. |
| `submitted_at` | `DateTime` | `DEFAULT NOW()` |  |
| `completed_at` | `DateTime` | `NULLABLE` | When feedback processing finished. |

### `live_conversation_sessions`
Real-time voice conversations using Gemini 3.1 Flash Live (WebSocket). The client connects directly to Gemini; the backend issues an ephemeral token and handles post-session analysis only.

| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | `PRIMARY KEY` |  |
| `user_id` | `UUID` | `FOREIGN KEY (users.id)` |  |
| `topic` | `String` | `NOT NULL` | Conversation topic (e.g., "Daily Life", "Business", or custom). |
| `persona` | `Enum` | `NOT NULL` | `FRIENDLY_TUTOR`, `NATIVE_PEER`, `EXAMINER`, `INTERVIEWER`. |
| `target_duration_seconds`| `Integer`| `NOT NULL` | Planned session length. |
| `actual_duration_seconds`| `Integer`| `NULLABLE` | Actual duration (set on session end). |
| `transcript_json` | `JSONB` | `NULLABLE` | Full dual-speaker transcript: `[{speaker: "user"|"ai", text, timestamp}]`. |
| `turn_count` | `Integer` | `NULLABLE` | Number of back-and-forth exchanges. |
| `avg_response_time_seconds`| `Float`| `NULLABLE` | Average user response latency. |
| `avg_response_length_words`| `Float`| `NULLABLE` | Average words per user turn. |
| `topic_relevance_score` | `Integer`| `NULLABLE` | 0–100 score of how on-topic the user stayed. |
| `status` | `Enum` | `DEFAULT 'ACTIVE'` | `ACTIVE`, `ENDED`, `TIMED_OUT`, `ERROR`. |
| `submission_id` | `UUID` | `NULLABLE`, `FOREIGN KEY (speaking_submissions.id)` | Links to the shared scoring record once post-session analysis completes. |
| `ephemeral_token_issued_at`| `DateTime`| `NULLABLE` | When the Gemini Live ephemeral token was created. |
| `started_at` | `DateTime` | `DEFAULT NOW()` |  |
| `ended_at` | `DateTime` | `NULLABLE` |  |

---

## 3. Vocabulary Module

Handles spaced repetition (fixed-interval, not SM-2), 4 daily exercise types, and personalized "weak word" extraction from the user's speaking/writing history.

### `vocabulary_words`
The master dictionary of words pre-generated for the curriculum. Generated once per cycle by the offline content pipeline and shared across all users.

| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | `PRIMARY KEY` |  |
| `word` | `String` | `UNIQUE`, `NOT NULL`| The word itself. |
| `definition` | `Text` | `NOT NULL` |  |
| `part_of_speech` | `String` | `NOT NULL` | e.g., "noun", "verb", "adjective". |
| `difficulty_level` | `String` | `NOT NULL` | Difficulty label (e.g., "A2-B1"). |
| `pronunciation_ipa` | `String` | `NULLABLE` | IPA phonetic transcription. |
| `pronunciation_audio_url`| `String` | `NULLABLE` | Pre-generated TTS audio of correct pronunciation. |
| `example_sentences`| `JSONB` | `NOT NULL` | Array of 3 example sentences. |
| `synonyms` | `JSONB` | `DEFAULT '[]'` | Array of synonym strings. |
| `antonyms` | `JSONB` | `DEFAULT '[]'` | Array of antonym strings. |
| `usage_tips` | `Text` | `NULLABLE` | Contextual usage guidance for learners. |
| `category` | `String` | `NOT NULL` | Semantic category (e.g., "Daily Life", "Academic"). |
| `target_cefr_level`| `String` | `NOT NULL` | CEFR level this word targets (e.g., "B1"). |
| `cycle` | `Integer` | `NOT NULL` | Introduced in this cycle (1-5). |
| `day` | `Integer` | `NOT NULL` | Introduced on this day (1-21). |
| `word_embedding` | `VECTOR` | `NULLABLE` | Embedding for deduplication similarity search. |
| `generated_by` | `Enum` | `NOT NULL` | `AI`, `HUMAN`. |
| `review_status` | `Enum` | `NOT NULL` | `DRAFT`, `APPROVED`, `REJECTED`, `PUBLISHED`. |
| `reviewed_by` | `UUID` | `NULLABLE`, `FOREIGN KEY (users.id)` | Admin user who reviewed this word. |
| `generation_batch_id`| `UUID` | `FOREIGN KEY` | Link to the `content_generation_batches` row. |
| `created_at` | `DateTime` | `DEFAULT NOW()` |  |
| `updated_at` | `DateTime` | `DEFAULT NOW()` |  |

### `vocabulary_exercise_bank`
Pre-generated deterministic exercises per word (fill-in-the-blank sentences and matching distractors). Generated once alongside the word in the offline content pipeline — no AI call needed at runtime.

| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | `PRIMARY KEY` |  |
| `word_id` | `UUID` | `FOREIGN KEY (vocabulary_words.id)` | The word this exercise is for. |
| `fill_blank_sentence` | `Text` | `NOT NULL` | Sentence with the target word removed (blank marker). |
| `fill_blank_correct_answer`| `String` | `NOT NULL` | The word itself — used for exact-match grading. |
| `match_definition_distractor_1`| `Text` | `NOT NULL` | Wrong definition from another word in the same day's set. |
| `match_definition_distractor_2`| `Text` | `NOT NULL` | Second wrong definition for the matching exercise. |
| `match_definition_distractor_3`| `Text` | `NOT NULL` | Third wrong definition for the matching exercise. |

### `user_vocabulary`
Spaced repetition state tracking per user per word. Uses a **fixed-interval schedule** (review on Day 2, 4, 8, 15 after first learning), not SM-2.

| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | `PRIMARY KEY` |  |
| `user_id` | `UUID` | `FOREIGN KEY (users.id)` |  |
| `word_id` | `UUID` | `FOREIGN KEY (vocabulary_words.id)` |  |
| `day_number` | `Integer` | `NOT NULL` | The cycle day when this word was first introduced. |
| `mastery_level` | `Integer` | `DEFAULT 1` | Fixed-interval stage: 1=New, 2=Learning, 3=Reviewing, 4=Practiced, 5=Mastered. |
| `status` | `Enum` | `DEFAULT 'LEARNING'` | `LEARNING`, `REVIEWING`, `MASTERED`. |
| `times_practiced` | `Integer`| `DEFAULT 0` | Total times the user has practiced this word. |
| `times_reviewed` | `Integer`| `DEFAULT 0` | Total review attempts. |
| `interval_days` | `Integer`| `DEFAULT 1` | Current fixed interval: 1, 2, 4, 7, or 14 days. |
| `next_review_date`| `DateTime`| `NOT NULL` | When this word is next due for review. |
| `last_reviewed_at`| `DateTime`| `NULLABLE` | Timestamp of last review attempt. |
| `learned_at` | `DateTime`| `DEFAULT NOW()` | When the word was first introduced. |
| `mastered_at` | `DateTime`| `NULLABLE` | When mastery_level reached 5. |

### `vocabulary_practice_sessions`
Tracks each daily vocabulary practice session for progress and analytics.

| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | `PRIMARY KEY` |  |
| `user_id` | `UUID` | `FOREIGN KEY (users.id)` |  |
| `daily_activity_id` | `UUID` | `NULLABLE`, `FOREIGN KEY` | Link to `daily_progress`. |
| `day_number` | `Integer` | `NOT NULL` | The cycle day this session corresponds to. |
| `fill_blank_score` | `Integer`| `NULLABLE` | Score out of 5. |
| `match_score` | `Integer`| `NULLABLE` | Score out of 5. |
| `context_score` | `Integer`| `NULLABLE` | Score out of 5 (from AI-graded "Use in Context"). |
| `pronunciation_score` | `Integer`| `NULLABLE` | Aggregate pronunciation score. |
| `overall_score` | `Integer`| `NULLABLE` | Weighted session score (0–100). |
| `completed_at` | `DateTime` | `DEFAULT NOW()` |  |

### `personalized_vocab_suggestions`
Words extracted asynchronously from the user's speaking/writing mistakes. Runs as a background job after speaking/writing submissions complete — non-blocking, bonus-only feature.

| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | `PRIMARY KEY` |  |
| `user_id` | `UUID` | `FOREIGN KEY (users.id)` |  |
| `source_type` | `Enum` | `NOT NULL` | `SPEAKING`, `WRITING`. |
| `source_submission_id`| `UUID` | `NULLABLE` | FK back to the original speaking or writing submission. |
| `original_word` | `String` | `NOT NULL` | The overused/weak word (e.g., "good"). |
| `original_sentence` | `Text` | `NOT NULL` | The user's actual sentence using the weak word. |
| `suggested_word` | `String` | `NOT NULL` | The stronger alternative (e.g., "commendable"). |
| `rewritten_sentence` | `Text` | `NOT NULL` | The user's sentence rewritten with the suggested word. |
| `status` | `Enum` | `DEFAULT 'PENDING'` | `PENDING`, `SHOWN`, `ADDED_TO_QUEUE`, `DISMISSED`. |
| `created_at` | `DateTime` | `DEFAULT NOW()` |  |

---

## 4. Writing Module

Handles the multi-agent revision loop. Submissions run through 4 parallel LangGraph agents (Grammar, Structure, Vocabulary, Coherence) and a Supervisor Aggregator.

### `writing_prompts`
Pre-generated prompts for the 21-day cycle. Generated once per cycle by the offline content pipeline and shared across all users.

| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | `PRIMARY KEY` |  |
| `cycle` | `Integer` | `NOT NULL` | Cycle number (1-5). |
| `day` | `Integer` | `NOT NULL` | Day number (1-21). |
| `type` | `Enum` | `NOT NULL` | `DESCRIPTIVE`, `NARRATIVE`, `ARGUMENTATIVE`. |
| `difficulty_level` | `String` | `NOT NULL` | Difficulty label (e.g., "B1-B2"). |
| `prompt_title` | `String` | `NOT NULL` | Short title for display. |
| `prompt_text` | `Text` | `NOT NULL` | The full writing prompt. |
| `target_word_count` | `Integer`| `NOT NULL` | Recommended word count (scales up per cycle). |
| `time_limit_minutes` | `Integer`| `NULLABLE` | Optional time limit. |
| `focus_areas` | `JSONB` | `DEFAULT '[]'` | Specific skills this prompt targets (e.g., ["adjectives", "sensory detail"]). |
| `writing_tips` | `Text` | `NULLABLE` | Guidance specific to this prompt type. |
| `sample_outline` | `Text` | `NULLABLE` | Optional structural outline suggestion. |
| `sensitivity_flagged`| `Boolean`| `DEFAULT FALSE` | Reviewer marks prompts touching personal/emotional territory for UI softening. |
| `prompt_embedding` | `VECTOR` | `NULLABLE` | Embedding for deduplication similarity search. |
| `generated_by` | `Enum` | `NOT NULL` | `AI`, `HUMAN`. |
| `review_status` | `Enum` | `NOT NULL` | `DRAFT`, `APPROVED`, `REJECTED`, `PUBLISHED`. |
| `reviewed_by` | `UUID` | `NULLABLE`, `FOREIGN KEY (users.id)` | Admin user who reviewed this prompt. |
| `generation_batch_id`| `UUID` | `FOREIGN KEY` | Link to the `content_generation_batches` row. |
| `created_at` | `DateTime` | `DEFAULT NOW()` |  |
| `updated_at` | `DateTime` | `DEFAULT NOW()` |  |

### `writing_submissions`
The parent container for a user's writing attempt (which may have up to 3 revisions). Holds the submission-level metadata and aggregate scores.

| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | `PRIMARY KEY` |  |
| `user_id` | `UUID` | `FOREIGN KEY (users.id)` |  |
| `prompt_id` | `UUID` | `FOREIGN KEY (writing_prompts.id)` |  |
| `daily_activity_id` | `UUID` | `NULLABLE`, `FOREIGN KEY` | Link to `daily_progress`. |
| `revision_count` | `Integer`| `DEFAULT 1` | Cannot exceed max_revisions (3). |
| `word_count` | `Integer`| `NULLABLE` | Word count of the latest version. |
| `time_spent_seconds` | `Integer`| `NULLABLE` | Total time spent writing. |
| `grammar_score` | `Integer`| `NULLABLE` | 0–100 score from Grammar Agent (weighted 30%). |
| `structure_score` | `Integer`| `NULLABLE` | 0–100 score from Structure Agent (weighted 30%). |
| `vocabulary_score` | `Integer`| `NULLABLE` | 0–100 score from Vocabulary Agent (weighted 20%). |
| `coherence_score` | `Integer`| `NULLABLE` | 0–100 score from Coherence Agent (weighted 20%). |
| `overall_score` | `Integer`| `NULLABLE` | Weighted aggregate (0–100). |
| `status` | `Enum` | `DEFAULT 'PENDING'` | `PENDING`, `PROCESSING`, `COMPLETED`, `FAILED`. |
| `processing_job_id` | `String` | `NULLABLE` | Celery task ID for the async feedback pipeline. |
| `submitted_at` | `DateTime` | `DEFAULT NOW()` |  |
| `completed_at` | `DateTime` | `NULLABLE` | When feedback processing finished. |

### `writing_submission_versions`
Individual drafts of a submission and their respective multi-agent feedback. Each revision creates a new version row.

| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | `PRIMARY KEY` |  |
| `submission_id` | `UUID` | `FOREIGN KEY (writing_submissions.id)` | Link to parent submission. |
| `version_number` | `Integer`| `NOT NULL` | 1 = original, 2–4 = revisions. |
| `text_content` | `Text` | `NOT NULL` | The actual essay text for this version. |
| `grammar_score` | `Integer`| `NULLABLE` | This version's grammar score. |
| `structure_score` | `Integer`| `NULLABLE` | This version's structure score. |
| `vocabulary_score` | `Integer`| `NULLABLE` | This version's vocabulary score. |
| `coherence_score` | `Integer`| `NULLABLE` | This version's coherence score. |
| `overall_score` | `Integer`| `NULLABLE` | This version's aggregate score. |
| `ai_feedback` | `JSONB` | `NULLABLE` | Full multi-agent feedback report for this version (Grammar/Structure/Vocab/Coherence agent outputs + Supervisor merge). |
| `fixed_issues` | `JSONB` | `NULLABLE` | Comparison output from revision step: `{fixedIssues, stillPresentIssues, newIssuesIntroduced}`. Populated for versions 2+. |
| `created_at` | `DateTime` | `DEFAULT NOW()` |  |

---

## 5. Interview Panel Module

Handles the stateful, 3-agent mock interview (HR, Technical/Role, Manager). Uses a sequential LangGraph orchestrator with turn-based HTTP rounds for MVP.

### `domain_question_bank`
Pre-generated, human-reviewed domain-specific questions. Generated once per (domain × level) combination by the offline content pipeline.

| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | `PRIMARY KEY` |  |
| `domain` | `Enum` | `NOT NULL` | `SOFTWARE_TECH`, `BUSINESS_FINANCE`, `HEALTHCARE`, `SALES_MARKETING`, `CUSTOMER_SERVICE`, `ACADEMIC_RESEARCH`, `GENERAL`. |
| `level` | `Enum` | `NOT NULL` | `ENTRY`, `MID`, `SENIOR`. |
| `agent_type` | `Enum` | `NOT NULL` | `HR`, `TECHNICAL`, `MANAGER`. |
| `question_text` | `Text` | `NOT NULL` |  |
| `sub_category` | `String` | `NOT NULL` | e.g., "clinical judgment", "system design". |
| `expected_answer_notes`| `Text` | `NOT NULL` | Grounding for the post-session verdict agent — what a strong answer should cover. |
| `research_grounded`| `Boolean`| `DEFAULT FALSE` | Was this question validated against real-world sourcing? |
| `review_status` | `Enum` | `NOT NULL` | `DRAFT`, `APPROVED`, `REJECTED`, `PUBLISHED`. |
| `reviewed_by` | `UUID` | `NULLABLE`, `FOREIGN KEY (users.id)` | Domain-familiar reviewer. |
| `generation_batch_id`| `UUID` | `FOREIGN KEY` | Link to the `content_generation_batches` row. |
| `created_at` | `DateTime` | `DEFAULT NOW()` |  |
| `updated_at` | `DateTime` | `DEFAULT NOW()` |  |

### `wildcard_question_bank`
Random "curveball" questions used across all domains. Generated once as a domain-agnostic batch.

| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | `PRIMARY KEY` |  |
| `question_text` | `Text` | `NOT NULL` | e.g., "Where do you see yourself in 5 years?" |
| `category` | `Enum` | `NOT NULL` | `CLASSIC_CURVEBALL`, `BRAIN_TEASER`, `SELF_REFLECTION`, `PRESSURE_TEST`. |
| `suitable_agent_types`| `JSONB` | `NOT NULL` | Array of agent types that can ask this (e.g., `["HR", "MANAGER"]`). |
| `min_level` | `Enum` | `DEFAULT 'ENTRY'`| `ENTRY`, `MID`, `SENIOR`. |
| `review_status` | `Enum` | `NOT NULL` | `DRAFT`, `APPROVED`, `REJECTED`, `PUBLISHED`. |
| `generation_batch_id`| `UUID` | `FOREIGN KEY` | Link to the `content_generation_batches` row. |
| `created_at` | `DateTime` | `DEFAULT NOW()` |  |

### `interview_panel_sessions`
State tracking for a live turn-based panel session. The `session_state` JSONB column stores the full `PanelSessionState` object (domain, level, role, currentRound, currentAgent, topicsAsked, transcript, wildcardsUsed, etc.) — rehydrated from DB on every turn since each turn is its own HTTP request.

| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | `PRIMARY KEY` |  |
| `user_id` | `UUID` | `FOREIGN KEY (users.id)` |  |
| `domain` | `Enum` | `NOT NULL` |  |
| `level` | `Enum` | `NOT NULL` | `ENTRY`, `MID`, `SENIOR`. |
| `role` | `String` | `NULLABLE` | Optional free-text role (e.g., "Backend Developer"). |
| `company_style` | `Enum` | `NULLABLE` | `STARTUP`, `CORPORATE` — changes tone, not content. |
| `interview_mode` | `Enum` | `NOT NULL` | `FULL_PANEL`, `SINGLE_AGENT`. |
| `selected_agent_type`| `Enum` | `NULLABLE` | `HR`, `TECHNICAL`, `MANAGER` — set only for `SINGLE_AGENT` mode. |
| `target_duration_minutes`| `Integer`| `NOT NULL` | User-selected, capped at 30. |
| `actual_duration_minutes`| `Integer`| `NULLABLE` | Computed at session end. |
| `session_state` | `JSONB` | `NULLABLE` | Full `PanelSessionState` object persisted/rehydrated between turns (currentRound, currentAgent, topicsAsked, transcript[], wildcardsUsed, round_start_time, etc.). |
| `wildcards_used` | `Integer`| `DEFAULT 0` | Count of wildcard questions used (capped at 2 per session). |
| `status` | `Enum` | `DEFAULT 'ACTIVE'`| `ACTIVE`, `ENDED`, `ABANDONED`. |
| `end_reason` | `Enum` | `NULLABLE` | `NATURAL`, `USER_TARGET_REACHED`, `HARD_CEILING_REACHED`. |
| `overall_verdict` | `Enum` | `NULLABLE` | `STRONG_HIRE`, `HIRE`, `MAYBE`, `NO_HIRE` (set after post-session report completes). |
| `started_at` | `DateTime` | `DEFAULT NOW()` |  |
| `ended_at` | `DateTime` | `NULLABLE` |  |

### `panel_rounds`
Tracks each round within a panel session. In `FULL_PANEL` mode: Round 1 = HR, Round 2 = Technical, Round 3 = Manager. In `SINGLE_AGENT` mode: a single extended round with one agent.

| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | `PRIMARY KEY` |  |
| `session_id` | `UUID` | `FOREIGN KEY (interview_panel_sessions.id)` |  |
| `agent_type` | `Enum` | `NOT NULL` | `HR`, `TECHNICAL`, `MANAGER`. |
| `round_number` | `Integer`| `NOT NULL` | 1, 2, or 3. |
| `questions_asked` | `JSONB` | `DEFAULT '[]'` | Array of question IDs/text asked in this round. |
| `started_at` | `DateTime` | `DEFAULT NOW()` |  |
| `ended_at` | `DateTime` | `NULLABLE` |  |

### `panel_responses`
Individual Q&A turns within a round. Each turn = one question + one user answer.

| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | `PRIMARY KEY` |  |
| `round_id` | `UUID` | `FOREIGN KEY (panel_rounds.id)` |  |
| `question_text` | `Text` | `NOT NULL` | The question asked by the agent. |
| `user_answer_transcript`| `Text` | `NOT NULL` | Transcribed user answer. |
| `agent_reaction_text`| `Text` | `NULLABLE` | Brief agent reaction/acknowledgment. |
| `audio_url` | `String` | `NOT NULL` | S3 / Supabase storage link for the user's recorded answer. |
| `is_wildcard` | `Boolean`| `DEFAULT FALSE` | Was this pulled from `wildcard_question_bank`? |
| `submitted_at` | `DateTime` | `DEFAULT NOW()` |  |

### `panel_agent_feedback`
Individual agent verdicts generated post-session by the parallel multi-agent report pipeline.

| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | `PRIMARY KEY` |  |
| `session_id` | `UUID` | `FOREIGN KEY (interview_panel_sessions.id)` |  |
| `agent_type` | `Enum` | `NOT NULL` | `HR`, `TECHNICAL`, `MANAGER`, `SUMMARY` (the Panel Summary Agent). |
| `score_contribution`| `JSONB` | `NOT NULL` | This agent's category scores (e.g., `{"domain_knowledge": 82, "communication": 75}`). |
| `verdict_notes` | `Text` | `NOT NULL` | The agent's narrative feedback. |
| `best_answer_reference`| `UUID` | `NULLABLE`, `FOREIGN KEY (panel_responses.id)` | Which user answer was strongest. |
| `weakest_answer_reference`| `UUID`| `NULLABLE`, `FOREIGN KEY (panel_responses.id)` | Which user answer was weakest. |
| `created_at` | `DateTime` | `DEFAULT NOW()` |  |

---

## 6. Progress & Achievements

### `daily_progress`
Tracks daily completion of the 21-day cycle. One row per user per day. Used by the dashboard, streak computation, and analytics.

| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | `PRIMARY KEY` |  |
| `user_id` | `UUID` | `FOREIGN KEY (users.id)` |  |
| `date` | `Date` | `NOT NULL` | The calendar date for this progress row. |
| `cycle` | `Integer` | `NOT NULL` | The cycle this day belongs to. |
| `day` | `Integer` | `NOT NULL` | The day number within the cycle (1-21). |
| `speaking_done` | `Boolean`| `DEFAULT FALSE` | Flow A exercise completed today. |
| `vocab_done` | `Boolean`| `DEFAULT FALSE` | Vocabulary session completed today. |
| `writing_done` | `Boolean`| `DEFAULT FALSE` | Writing submission completed today. |
| `total_practice_seconds`| `Integer`| `DEFAULT 0` | Aggregate practice time across all modules today. |
| `created_at` | `DateTime` | `DEFAULT NOW()` |  |
| `updated_at` | `DateTime` | `DEFAULT NOW()` |  |

**Index:** `UNIQUE (user_id, date)` — prevents duplicate rows for the same user+date.

### `achievements`
Catalog of all possible achievement badges.

| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | `PRIMARY KEY` |  |
| `key` | `String` | `UNIQUE`, `NOT NULL` | Programmatic identifier (e.g., "7_DAY_STREAK", "FIRST_PERFECT_SCORE"). |
| `title` | `String` | `NOT NULL` | Display title (e.g., "Week Warrior"). |
| `description` | `Text` | `NOT NULL` | What the user did to earn it. |
| `icon_url` | `String` | `NULLABLE` | Badge icon/image URL. |
| `module` | `Enum` | `NULLABLE` | `SPEAKING`, `VOCABULARY`, `WRITING`, or NULL for global achievements. |
| `created_at` | `DateTime` | `DEFAULT NOW()` |  |

### `user_achievements`
Join table tracking which user earned which achievement and when.

| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | `PRIMARY KEY` |  |
| `user_id` | `UUID` | `FOREIGN KEY (users.id)` |  |
| `achievement_id` | `UUID` | `FOREIGN KEY (achievements.id)` |  |
| `earned_at` | `DateTime` | `DEFAULT NOW()` | When the achievement was unlocked. |

**Index:** `UNIQUE (user_id, achievement_id)` — a user can only earn each achievement once.

---

## 7. Offline Content Generation

### `content_generation_batches`
Tracks AI offline generation runs for quality control and auditing. One batch = one cycle's worth of content for one module (e.g., "Cycle 2 Speaking exercises").

| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | `PRIMARY KEY` |  |
| `module_type` | `Enum` | `NOT NULL` | `SPEAKING`, `VOCABULARY`, `WRITING`, `INTERVIEW_PANEL`. |
| `cycle_number` | `Integer`| `NOT NULL` | Which cycle this batch is for (1-5). |
| `prompt_version` | `String` | `NOT NULL` | Link to prompt version used for generation. |
| `triggered_by` | `UUID` | `NOT NULL`, `FOREIGN KEY (users.id)` | Admin user who triggered the generation. |
| `total_slots` | `Integer`| `NOT NULL` | How many content items were generated (e.g., 210 words, 63 exercises). |
| `approved_count` | `Integer`| `DEFAULT 0` | Items approved during review. |
| `rejected_count` | `Integer`| `DEFAULT 0` | Items rejected during review. |
| `status` | `Enum` | `NOT NULL` | `PLANNING`, `GENERATING`, `IN_REVIEW`, `PUBLISHED`. |
| `created_at` | `DateTime` | `DEFAULT NOW()` |  |
| `published_at` | `DateTime` | `NULLABLE` | When the batch was fully approved and published. |

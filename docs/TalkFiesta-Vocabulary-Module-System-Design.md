# 📚 TalkFiesta — Vocabulary Module System Design

**Companion document to `TalkFiesta.md`, `TalkFiesta-AI-Engineering.md`, and `TalkFiesta-Speaking-Module-System-Design.md`**

> Covers the full technical system design for the Vocabulary Module: word content generation per cycle, the 4 daily exercise types, spaced repetition scheduling, and the personalized "words from your own mistakes" feature.

---

## Table of Contents

1. Module Scope
2. Key Design Insight — Not Every Exercise Needs AI
3. High-Level Architecture
4. Content Generation — Word Bank & Exercise Bank Per Cycle
5. Runtime Flow — Daily Vocabulary Session
6. Spaced Repetition Engine — Review Scheduling
7. Personalization — Vocabulary From Your Own Mistakes
8. Component Breakdown
9. API Design
10. Database Schema
11. Sequence Diagrams
12. Infrastructure & Scalability
13. Failure Modes & Error Handling
14. Cost & Performance Considerations
15. How This Connects to Guardrails

---

## 1. Module Scope

Per cycle: 10 new words/day × 21 days = 210 words, with 4 practice exercises per day plus a rolling review session of previously-learned words.

| Sub-Feature | Description |
|---|---|
| **Daily New Words** | 10 words/day with definition, pronunciation, examples, synonyms/antonyms |
| **Fill in the Blanks** | 5 questions/day — sentence with missing word |
| **Match Definitions** | 5 pairs/day — drag-and-drop matching |
| **Use in Context** | 5 sentences/day — user writes original sentence, AI checks correctness |
| **Pronunciation Practice** | 10 words/day — user records, gets pronunciation feedback |
| **Spaced Repetition Review** | 5–10 words/day pulled from prior days, due for review |
| **Personal Vocabulary Bank** | Browsable archive of everything learned |
| **Vocabulary From Your Own Mistakes** *(personalization layer)* | AI-surfaced word suggestions based on the user's own speaking/writing history |

---

## 2. Key Design Insight — Not Every Exercise Needs AI

This is the most important architectural decision in this module, and it directly controls cost and latency. Of the 4 daily exercise types, only **2 of them actually need a live AI call**:

| Exercise | Needs AI at Runtime? | Why |
|---|---|---|
| Fill in the Blanks | ❌ No | Correct answer is pre-defined at content-generation time — this is a simple string/exact-match comparison, handled entirely in application code |
| Match Definitions | ❌ No | Pre-defined pairs — pure client/server logic, no model call |
| Use in Context | ✅ **Yes** | User writes an original sentence — correctness depends on their specific wording, which cannot be pre-defined. Requires a live Gemini call to judge grammatical correctness + appropriate word usage |
| Pronunciation Practice | ✅ **Yes** | Requires audio analysis — STT + pronunciation scoring |

**Why this matters:** if every exercise routed through an LLM call, you'd be making ~15 AI calls per user per day just for vocabulary (10 words review + 5 fill-blank + 5 match + 5 context + 10 pronunciation). By recognizing that 2 of the 4 exercise types are **deterministic**, that drops to roughly 5 AI-touching calls per day (context sentences get batched into a single call — see Section 5) — a meaningful cost and latency win at scale, and it's the same principle behind why Flow A vs Flow B was split in the Speaking Module design.

---

## 3. High-Level Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                              CLIENT (Next.js)                         │
│  ┌────────────────┐  ┌──────────────────┐  ┌───────────────────┐    │
│  │  Word Cards UI  │  │  Exercise UI       │  │  Review Session UI  │   │
│  │  (learn phase)  │  │  (4 types)          │  │  (spaced repetition) │   │
│  └────────────────┘  └──────────────────┘  └───────────────────┘    │
└──────────────────────────────────────────────────────────────────────┘
                    │                    │                    │
                    ▼                    ▼                    ▼
┌──────────────────────────────────────────────────────────────────────┐
│                        NEXT.JS API / BACKEND LAYER                    │
│  ┌────────────────┐  ┌──────────────────┐  ┌───────────────────┐    │
│  │ Word Bank API    │  │ Exercise Grading    │  │ Review Scheduler API │  │
│  │ /api/vocabulary/ │  │ API (split by type)  │  │ /api/vocabulary/     │  │
│  │ day/:day          │  │                       │  │ review/today            │  │
│  └────────────────┘  └──────────────────┘  └───────────────────┘    │
└──────────────────────────────────────────────────────────────────────┘
         │                    │                          │
         ▼                    ▼                          ▼
┌────────────────┐   ┌──────────────────────┐   ┌──────────────────┐
│  PostgreSQL       │   │  Deterministic Grader   │   │  Gemini 3.5 Flash   │
│  (word bank,        │   │  (fill-blank, matching —  │   │  (Use in Context     │
│   pre-generated       │   │   pure code, no AI call)  │   │   grading — batched    │
│   exercises)            │   └──────────────────────┘   │   per user per day)      │
└────────────────┘                                     └──────────────────┘
         ▲                                                        │
         │                                                        ▼
┌──────────────────────────────────────┐               ┌──────────────────┐
│  OFFLINE CONTENT GENERATION PIPELINE     │               │  Pronunciation      │
│  (LangGraph — see Section 4)               │               │  Scoring Pipeline     │
│  Word Planner → Word Writer → Exercise      │               │  (Deepgram/ElevenLabs │
│  Generator → Dedup Check → Human Review       │               │   + Gemini comparison)  │
└──────────────────────────────────────┘               └──────────────────┘

┌──────────────────────────────────────────────────────────────────────┐
│        PERSONALIZATION PIPELINE (async, triggered by Speaking/         │
│        Writing submissions — see Section 7)                              │
│  Scans user's own transcripts/writing → surfaces "words you could         │
│  have used" → feeds into that user's vocabulary queue                     │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 4. Content Generation — Word Bank & Exercise Bank Per Cycle

Same two-tier philosophy as the Speaking Module: **generated once per cycle, offline, human-reviewed, shared across all users** — not generated live per user.

### 4.1 Word Selection Pipeline (LangGraph, Admin-Triggered)

```
Trigger: "Generate Cycle 2 vocabulary batch" (210 words)
                    │
                    ▼
      ┌──────────────────────────┐
      │  Word List Planner Agent     │
      │  - Reads Category & CEFR       │
      │    Progression Model (4.2)      │
      │  - For each of 21 days, decides   │
      │    the CATEGORY + CEFR band for     │
      │    that day's 10 words                │
      │  - Checks against ALL words already    │
      │    used across every prior cycle         │
      │    (global uniqueness — no repeats          │
      │    across 1,050 total words)                  │
      └────────────┬─────────────┘
                   ▼
      ┌──────────────────────────┐
      │  Word Content Writer Agent    │
      │  (Gemini 3.5 Flash — one call     │
      │   per word)                          │
      │  - Generates: definition, part of      │
      │    speech, 3 example sentences,           │
      │    synonyms, antonyms, usage tips,           │
      │    IPA pronunciation guide                     │
      └────────────┬─────────────┘
                   ▼
      ┌──────────────────────────┐
      │  Exercise Generator Agent      │
      │  - For each word, generates:       │
      │    · 1 fill-in-the-blank sentence     │
      │      (with the word removed)             │
      │    · 1 definition-matching entry            │
      │  - These are stored alongside the word,       │
      │    NOT generated live (Section 2 principle)      │
      └────────────┬─────────────┘
                   ▼
      ┌──────────────────────────┐
      │  Audio Generation Step         │
      │  - TTS (ElevenLabs/OpenAI) for     │
      │    correct pronunciation of each      │
      │    word → stored as audio_url           │
      └────────────┬─────────────┘
                   ▼
      ┌──────────────────────────┐
      │  Duplicate/Quality Checker      │
      │  Agent                              │
      │  - Embeds word+definition              │
      │  - Vector similarity check against       │
      │    entire existing word bank                │
      │  - Flags near-duplicate meanings               │
      │    (e.g. "happy" and "glad" both being         │
      │    added in the same cycle unnoticed)             │
      │  - Checks CEFR appropriateness                       │
      └────────────┬─────────────┘
                   ▼
      ┌──────────────────────────┐
      │  Human Review Gate               │
      │  - Reviewer checks definitions are    │
      │    accurate (this is the highest-risk      │
      │    failure mode — a wrong definition          │
      │    actively teaches the user something          │
      │    false)                                            │
      └────────────┬─────────────┘
                   ▼
      Publish to VOCABULARY_WORDS + VOCABULARY_EXERCISE_BANK
```

**Why human review matters more here than almost anywhere else in the app:** a wrong grammar correction on one user's submission is a contained, single-user error. A wrong *definition* published to the shared word bank is taught, confidently, to every single user who reaches that word — this is the highest-leverage place in the entire app for a factual AI error to cause real harm to learning outcomes. Definitions should arguably get double review (AI Quality Checker + human) before publishing, more so than any other content type in TalkFiesta.

### 4.2 Category & CEFR Progression Model (Per Cycle)

Mirrors the Speaking Module's approach — a config-driven rules engine, not left to AI discretion:

| Days (within cycle) | Category | CEFR Target (shifts up per cycle, same as Speaking Module Section 4.4) |
|---|---|---|
| 1–7 | Daily life & essential communication | Cycle-appropriate floor (e.g. A2–B1 in Cycle 1) |
| 8–14 | Academic & professional/workplace | One band above the floor |
| 15–21 | Advanced & abstract concepts | Two bands above the floor |

Same formula pattern as Speaking: `target_cefr = base_cefr_for_cycle[cycle_number] + week_adjustment[day_range]`, `category = week_category_table[day_number]`.

### 4.3 Data Model Additions (Content Generation)

```
VOCABULARY_WORDS  (extends the table from TalkFiesta.md)
  ...existing fields (id, word, definition, part_of_speech,
     difficulty_level, cefr_level, pronunciation_ipa,
     pronunciation_audio_url, example_sentences, synonyms,
     antonyms, usage_tips, category)...

  cycle_number             INT                          ← NEW
  day_number                INT                          ← NEW
  generated_by               ENUM (AI | HUMAN)             ← NEW
  review_status              ENUM (DRAFT | APPROVED |
                                    REJECTED | PUBLISHED)   ← NEW
  reviewed_by                 user_id (nullable)            ← NEW
  word_embedding               VECTOR                       ← NEW (dedup search)
  generation_batch_id           FK → ContentGenerationBatch    ← NEW

VOCABULARY_EXERCISE_BANK   ← NEW TABLE
  id
  word_id (FK → VocabularyWords)
  fill_blank_sentence          (the word removed, with a blank marker)
  fill_blank_correct_answer     (= the word itself, stored for exact-match grading)
  match_definition_distractor_1  (2-3 wrong definitions pulled from OTHER
  match_definition_distractor_2   words in the same day's set, used to
  match_definition_distractor_3   build the matching exercise UI)
```

---

## 5. Runtime Flow — Daily Vocabulary Session

```
STEP 1 — Fetch Today's Words
  GET /api/vocabulary/day/:day
  → Backend looks up VOCABULARY_WORDS by (cycle_number, day_number)
  → Returns 10 word cards + their pre-generated exercise data
    (fill-blank sentences, matching distractors) — all pulled
    from the static bank, no AI call needed for this step

STEP 2 — User Reviews Word Cards
  Client-only, no backend interaction beyond initial fetch
  User taps through 10 cards, plays pronunciation audio (pre-generated,
  served directly from storage — no TTS call at runtime)

STEP 3a — Fill in the Blanks (deterministic)
  User submits answer
  POST /api/vocabulary/exercise/fill-blank/submit
  → Backend does a simple string comparison against
    fill_blank_correct_answer (case-insensitive, trimmed)
  → Instant response, NO AI call, NO queue — this is a synchronous,
    sub-100ms operation

STEP 3b — Match Definitions (deterministic)
  Client-side drag-and-drop, submits final matches
  POST /api/vocabulary/exercise/match/submit
  → Backend compares submitted pairs against known correct pairs
  → Instant response, NO AI call

STEP 3c — Use in Context (AI required)
  User writes 5 original sentences (one per word)
  Client BATCHES all 5 into ONE submission, not 5 separate calls
  POST /api/vocabulary/exercise/context/submit
  Body: { wordId1: sentence1, wordId2: sentence2, ... } (5 pairs)
  → Backend makes ONE Gemini 3.5 Flash call covering all 5 sentences
    (structured prompt: "here are 5 word+sentence pairs, evaluate
    each for correct grammar and appropriate word usage")
  → Returns structured JSON: per-sentence pass/fail + brief feedback
  → This single-batched-call design is the key cost optimization
    referenced in Section 2

STEP 3d — Pronunciation Practice (AI required)
  User records themselves saying each of 10 words
  POST /api/vocabulary/exercise/pronunciation/submit (per word, or batched
    as one audio file with word boundaries — implementation choice)
  → Backend runs STT (Deepgram) to get what was actually said
  → Compares against expected word (phonetic similarity, not just
    exact text match — accounts for near-correct pronunciation)
  → For close/ambiguous cases, escalates to Gemini for a qualitative
    pronunciation tip (e.g. "you're stressing the second syllable —
    it should be on the first")
  → Returns score + tip per word

STEP 4 — Session Score & Progress Update
  Client aggregates all 4 exercise results (already returned per-exercise
  above) into a session score
  POST /api/vocabulary/session/:id/complete
  → Marks DailyActivity as COMPLETED
  → Updates each word's UserVocabulary row: increments times_practiced,
    sets initial mastery_level, schedules first review date
    (see Section 6)
  → Updates streak, checks achievements
```

**Why Step 3c batches into one AI call instead of 5:** identical cost-reduction logic to Section 2 — 5 separate Gemini calls for 5 sentences is 5x the latency and cost of one well-structured call that evaluates all 5 sentences in a single structured JSON response. This only works because the sentences don't depend on each other (no conversational state needed), making batching safe here in a way it wouldn't be for, say, a multi-turn conversation.

---

## 6. Spaced Repetition Engine — Review Scheduling

This is a **pure scheduling algorithm**, not an AI feature — it runs entirely in application logic against the database.

### 6.1 Scheduling Rule (Fixed-Interval, as defined in `TalkFiesta.md`)

```
On first learning a word (Day N):
  next_review_at = Day N + 1   (review on Day N+2... using the
                                 documented schedule: Day 2, 4, 8, 15
                                 after learning)

On each successful review:
  mastery_level += 1  (capped at 5: New → Learning → Reviewing →
                        Practiced → Mastered)
  next_review_at = current_day + interval[mastery_level]
    where interval = [1, 2, 4, 7, 14]  (days, roughly doubling —
                       matches the Day 2/4/8/15 pattern from the
                       word's first learning)

On a FAILED review (wrong answer):
  mastery_level = max(1, mastery_level - 2)   (drop back significantly,
                                                 don't reset to zero —
                                                 avoids over-punishing
                                                 a single slip)
  next_review_at = current_day + 1   (review again soon)
```

### 6.2 Daily Review Queue Composition

```
GET /api/vocabulary/review/today
  → Query: SELECT * FROM UserVocabulary
           WHERE user_id = :user AND next_review_at <= TODAY
           ORDER BY next_review_at ASC
           LIMIT 10   (cap review session size — don't overwhelm
                        the user even if many words are due at once)
  → If more than 10 words are due, prioritize by:
      1. Lowest mastery_level first (weakest words surface first)
      2. Oldest next_review_at first (most overdue)
  → Remaining overdue words roll over to tomorrow's queue automatically
    (next_review_at doesn't change until the word is actually reviewed)
```

This is a straightforward indexed database query — no AI, no queue, sub-second response. The review *exercises themselves* reuse the same 4 exercise types and grading logic from Section 5 (a review session is really just Section 5's exercises pointed at old words instead of today's new words).

---

## 7. Personalization — Vocabulary From Your Own Mistakes

This is the async, background pipeline that powers the feature described in `TalkFiesta.md` — surfacing better word choices based on a user's *own* speaking/writing history, rather than only the generic pre-generated bank.

### 7.1 Trigger

```
Runs automatically after:
  - A Speaking submission completes analysis (Speaking Module Flow A/B,
    Section 8's LangGraph pipeline)
  - A Writing submission completes analysis

Does NOT run synchronously in the user's session — this is a
background job, decoupled from the exercise flow the user is
actively doing.
```

### 7.2 Pipeline

```
                ┌──────────────────────────┐
                │  Trigger: submission            │
                │  analysis just completed          │
                └────────────┬─────────────┘
                             ▼
                ┌──────────────────────────┐
                │  Pattern Detector                │
                │  - Scans the user's transcript/       │
                │    writing text for OVERUSED,           │
                │    simple words (e.g. "good," "very,"     │
                │    "happy," "said")                          │
                │  - Checks frequency against the user's         │
                │    OWN rolling history (last 7-14 days),          │
                │    not a single submission — avoids                │
                │    over-triggering on one-off word use               │
                └────────────┬─────────────┘
                             ▼
                ┌──────────────────────────┐
                │  Vocabulary Upgrade Agent        │
                │  (Gemini 3.5 Flash)                  │
                │  - Given: overused word + the user's     │
                │    actual sentence(s) that used it          │
                │  - Generates: 2-3 stronger alternative         │
                │    words (CEFR-appropriate — not wildly           │
                │    harder than their current level)                 │
                │  - Rewrites their ORIGINAL sentence using             │
                │    each suggested word, so the example is                │
                │    personally relevant, not generic                        │
                └────────────┬─────────────┘
                             ▼
                ┌──────────────────────────┐
                │  Dedup Check                       │
                │  - Skip if this word was already        │
                │    suggested to this user recently          │
                │  - Skip if it's already in their               │
                │    UserVocabulary as MASTERED                     │
                └────────────┬─────────────┘
                             ▼
                Write to PERSONAL_VOCAB_SUGGESTIONS table
                             │
                             ▼
                Surfaced in tomorrow's vocabulary session as
                1-2 "bonus" words alongside the standard 10 —
                clearly labeled ("Based on your recent speaking:
                you said 'very happy' — try 'elated'")
```

### 7.3 Data Model Addition

```
PERSONAL_VOCAB_SUGGESTIONS   ← NEW TABLE
  id
  user_id (FK → Users)
  source_type (SPEAKING | WRITING)
  source_submission_id (FK — links back to the original submission)
  original_word (the overused word, e.g. "good")
  original_sentence (their actual sentence, quoted for context)
  suggested_word (the upgrade, e.g. "commendable")
  rewritten_sentence (their sentence, rewritten with the new word)
  status (PENDING | SHOWN | ADDED_TO_QUEUE | DISMISSED)
  created_at
```

**Design note — this pipeline is intentionally decoupled from the main daily vocabulary flow.** It doesn't block or slow down Section 5's runtime flow; it runs asynchronously after other modules finish their own analysis, and its output simply appears as bonus content the next time the user opens their vocabulary session. If this pipeline fails or is delayed, the core 10-words-a-day experience is completely unaffected.

---

## 8. Component Breakdown

| Component | Responsibility |
|---|---|
| **Word Cards UI** | Displays daily word content, plays pre-generated pronunciation audio |
| **Exercise UI (4 types)** | Renders fill-blank, matching, context-writing, and pronunciation-recording interfaces |
| **Word Bank API** | Serves pre-generated word + exercise content for a given day (no AI at request time) |
| **Deterministic Grader** | Pure application logic for fill-blank and matching — no model call |
| **Context Grading Service** | Batches and sends "Use in Context" sentences to Gemini in one call per session |
| **Pronunciation Scoring Pipeline** | STT + phonetic comparison + occasional Gemini qualitative tip |
| **Review Scheduler** | Pure DB-query-driven spaced repetition logic (Section 6) |
| **Content Generation Pipeline** | Offline, admin-triggered, produces the shared word + exercise bank (Section 4) |
| **Personalization Pipeline** | Async background job scanning user history for vocabulary upgrade opportunities (Section 7) |

---

## 9. API Design

| Endpoint | Method | AI Call? | Purpose |
|---|---|---|---|
| `/api/vocabulary/day/:day` | GET | ❌ No | Fetch today's 10 words + pre-generated exercises |
| `/api/vocabulary/exercise/fill-blank/submit` | POST | ❌ No | Deterministic grading |
| `/api/vocabulary/exercise/match/submit` | POST | ❌ No | Deterministic grading |
| `/api/vocabulary/exercise/context/submit` | POST | ✅ Yes (1 batched call) | Grades all 5 "Use in Context" sentences together |
| `/api/vocabulary/exercise/pronunciation/submit` | POST | ✅ Yes (STT + occasional Gemini) | Pronunciation scoring |
| `/api/vocabulary/review/today` | GET | ❌ No | Returns due-for-review words (DB query only) |
| `/api/vocabulary/review/submit` | POST | Depends on exercise type used | Reuses the same grading endpoints as Section 5 |
| `/api/vocabulary/session/:id/complete` | POST | ❌ No | Finalizes session score, updates streak/mastery |
| `/api/vocabulary/personal-suggestions` | GET | ❌ No (pre-computed) | Fetches any pending personalized word suggestions |
| `/api/vocabulary/bank` | GET | ❌ No | Full personal vocabulary bank browse/search |

---

## 10. Database Schema (Vocabulary Module — Full Picture)

```
VOCABULARY_WORDS               (Section 4.3 — shared content bank)
VOCABULARY_EXERCISE_BANK        (Section 4.3 — pre-generated exercises)
USER_VOCABULARY                 (from TalkFiesta.md, extended below)
  ...existing fields (id, user_id, word_id, day_number, status,
     mastery_level, times_reviewed, times_practiced,
     last_reviewed_at, next_review_at, learned_at, mastered_at)...
  interval_days           INT      ← NEW (current spaced-repetition interval)

VOCABULARY_PRACTICE_SESSIONS    (from TalkFiesta.md — unchanged)
PERSONAL_VOCAB_SUGGESTIONS      (Section 7.3 — NEW)
CONTENT_GENERATION_BATCH        (shared with Speaking Module design —
                                  same table tracks both modules' batches,
                                  differentiated by a module_type field)
```

---

## 11. Sequence Diagrams

### Daily Vocabulary Session (Steps 1–4)

```
User          Client UI        API              Deterministic     Gemini        DB
 │                │              │                  Grader           │            │
 │  Open Day 4     │              │                  │                │            │
 │───────────────▶│  GET /day/4    │                  │                │            │
 │                │─────────────▶│  Lookup word bank    │                │            │
 │                │              │  (no AI)               │                │            │
 │                │              │──────────────────────────────────────────────────▶│
 │                │◀─────────────│  10 words + exercises   │                │            │
 │  Review cards    │              │                  │                │            │
 │◀───────────────│              │                  │                │            │
 │  Fill blanks     │              │                  │                │            │
 │───────────────▶│  POST fill-blank │                │                │            │
 │                │─────────────▶│─────────────────▶│                │            │
 │                │◀───────────── instant result ────│                │            │
 │  Match defs      │              │                  │                │            │
 │───────────────▶│  POST match      │                │                │            │
 │                │─────────────▶│─────────────────▶│                │            │
 │                │◀───────────── instant result ────│                │            │
 │  Write 5          │              │                  │                │            │
 │  context sentences│              │                  │                │            │
 │───────────────▶│  POST context     │                │                │            │
 │                │  (batched, 5 pairs) │                │                │            │
 │                │─────────────▶│  ONE batched call ─────────────────▶│            │
 │                │◀─────────────│◀── 5 results in 1 response ─────────│            │
 │  Record 10 words   │              │                  │                │            │
 │───────────────▶│  POST pronunciation │              │                │            │
 │                │─────────────▶│  STT + phonetic compare │            │            │
 │                │              │  (+ Gemini tip if needed) │            │            │
 │                │◀─────────────│  scores + tips             │            │            │
 │  Session done       │              │                  │                │            │
 │───────────────▶│  POST complete      │                │                │            │
 │                │─────────────▶│  Update mastery, streak,   │                │            │
 │                │              │  schedule next reviews        │                │            │
 │                │              │────────────────────────────────────────────────▶│
 │◀───────────────│◀─────────────│                  │                │            │
```

### Personalization Pipeline (Async, Triggered Externally)

```
Speaking/Writing        Job Queue        Personalization      Gemini         DB
Submission Complete                       Worker
       │                    │                  │                 │            │
       │  Analysis done       │                  │                 │            │
       │───────────────────▶│  Enqueue pattern    │                 │            │
       │                    │  detection job          │                 │            │
       │                    │────────────────────▶│                 │            │
       │                    │                  │  Scan rolling history │            │
       │                    │                  │  for overused words       │            │
       │                    │                  │────────────────────────────────▶│
       │                    │                  │◀───────────────────────────────│
       │                    │                  │  If found: request         │            │
       │                    │                  │  upgrade suggestions          │            │
       │                    │                  │────────────────────▶│            │
       │                    │                  │◀────────────────────│            │
       │                    │                  │  Dedup check + write        │            │
       │                    │                  │  suggestion                    │            │
       │                    │                  │────────────────────────────────▶│
       │                    │                  │                 │            │
       (User sees it next time they open their vocabulary session —
        no real-time interaction with this pipeline at all)
```

---

## 12. Infrastructure & Scalability

| Concern | Approach |
|---|---|
| **Deterministic grading load** | Fill-blank and matching are pure CPU/DB operations — trivially scalable, no external API dependency, no rate-limit risk |
| **Context grading batching** | The 1-call-per-session batching (Section 5, Step 3c) is the single biggest lever for keeping this module's AI cost predictable at scale |
| **Pronunciation pipeline** | Reuses the same STT infrastructure (Deepgram) already provisioned for the Speaking Module — no separate scaling concern |
| **Content generation pipeline** | Runs rarely (once per cycle release), can run on a slower/cheaper compute path than user-facing request paths |
| **Personalization pipeline** | Fully async, queue-based — can be deprioritized under load without affecting the core learning experience (Section 7's design note) |
| **Review queue queries** | Indexed on `(user_id, next_review_at)` — this is a hot query path (runs every time a user might have due reviews) and should be a covered index |

---

## 13. Failure Modes & Error Handling

| Failure | Handling |
|---|---|
| Context grading batched call fails/times out | Retry the full batch once; on second failure, mark those 5 sentences as "pending review" rather than blocking the whole session — user can continue to pronunciation practice while this resolves |
| Pronunciation STT fails | Allow the user to re-record; if repeated failures, let them skip that word and flag it as "needs review" rather than blocking session completion |
| Review queue empty | Not a failure — just means nothing is due; client shows an encouraging empty state ("All caught up! Come back tomorrow for review") |
| Personalization pipeline fails silently | Non-blocking by design (Section 7) — failures here should be logged/monitored but never surface as user-facing errors, since the feature is a bonus layer, not core path |
| Word bank content generation produces a bad definition that slips through review | Needs a post-launch correction path — an admin "flag/edit this word" tool, since even with human review, occasional errors will reach production |

---

## 14. Cost & Performance Considerations

- **Per-session AI cost:** roughly 1 batched Gemini call (context grading) + up to 10 pronunciation-related calls (though most can resolve via phonetic comparison alone, only escalating to Gemini for ambiguous cases) — meaningfully cheaper than a naive "call AI for everything" design
- **Content generation cost:** paid once per cycle (210 words × several agent calls each), amortized across every user who ever reaches that cycle — this is why the shared-bank model (Section 4) is so much more cost-efficient than per-user generation
- **Latency targets:** fill-blank/matching should feel instant (<200ms, no network round-trip to an LLM); context grading batch should return within 3-5s; pronunciation feedback within 3-5s per word

---

## 15. How This Connects to Guardrails

| Guardrail | Where It Plugs Into This Design |
|---|---|
| Structured output validation (AI Engineering doc, Section 2) | Context Grading Service's batched response and the Word Content Writer Agent's output (Section 4.1) both require strict schema validation |
| Hallucination guardrails for factual content (AI Engineering doc, Section 2) | Directly addressed by the elevated Human Review Gate for word definitions (Section 4.1) — this module has the highest stakes for factual AI error in the whole app |
| Grounding via RAG (AI Engineering doc, Section 12) | Same principle as Speaking Module's grammar rules reference — word definitions could optionally be checked against a dictionary API as a grounding source before publishing, not just generated from the model's parametric memory |
| Rate limiting (AI Engineering doc, Section 5) | Applied per-user on the personalization pipeline trigger frequency, preventing runaway suggestion generation from a very active user |
| LangSmith tracing (AI Engineering doc, Section 6) | Wraps the content generation pipeline (Section 4) and the personalization pipeline (Section 7) |
| Cost observability (AI Engineering doc, Section 14) | Directly motivates the batching design in Section 5 and the deterministic-vs-AI split in Section 2 |
| Graceful degradation (AI Engineering doc, Section 17) | Reflected throughout Section 13's failure modes — no exercise type should be able to fully block session completion |

---

**Project:** TalkFiesta
**Document:** Vocabulary Module — System Design
**Companion to:** `TalkFiesta.md`, `TalkFiesta-AI-Engineering.md`, `TalkFiesta-Speaking-Module-System-Design.md`
**Status:** Ready for implementation planning

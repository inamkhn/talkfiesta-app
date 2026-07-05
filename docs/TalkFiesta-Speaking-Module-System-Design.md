# 🎤 TalkFiesta — Speaking Module System Design

**Companion document to `TalkFiesta.md` and `TalkFiesta-AI-Engineering.md`**

> Covers the full technical system design for the Speaking Module: scripted exercises (Conversation, Public Speaking, Impromptu) and the Real-Time AI Conversation feature (Gemini Live).

---

## Table of Contents

1. Module Scope
2. Two Distinct System Flows
3. High-Level Architecture
4. Exercise Content Generation — How Exercises Are Created Per Cycle
5. Flow A — Scripted Exercise Pipeline (Batch)
6. Flow B — Real-Time Conversation Pipeline (Streaming)
7. Component Breakdown
8. LangGraph Feedback Pipeline Design
9. API Design
10. Database Schema
11. Sequence Diagrams
12. Infrastructure & Scalability
13. Failure Modes & Error Handling
14. Cost & Performance Considerations
15. How This Connects to Guardrails

---

## 1. Module Scope

The Speaking Module covers 5 exercise types, which split into **two fundamentally different system flows**:

| Exercise Type | Flow Type |
|---|---|
| Conversational Speaking (daily topics) | **Batch** (record → upload → analyze → feedback) |
| Public Speaking Practice | **Batch** |
| Impromptu Speaking | **Batch** (with a prep-timer step added) |
| Mock Interviews (Multi-Agent Panel) | **Batch + Multi-Agent** (see `TalkFiesta.md` Section 9 for panel-specific design) |
| Real-Time AI Conversation | **Streaming** (live, bidirectional) |

This document designs both flows end-to-end, since they share a database and frontend shell but have almost entirely different backend paths.

---

## 2. Two Distinct System Flows

```
┌─────────────────────────────────────────────────────────────────┐
│                      SPEAKING MODULE                              │
│                                                                     │
│   ┌────────────────────────┐      ┌────────────────────────┐    │
│   │      FLOW A            │      │       FLOW B            │    │
│   │   Batch / Scripted     │      │   Real-Time / Streaming │    │
│   │                        │      │                          │    │
│   │  Record → Upload       │      │  Open WebSocket          │    │
│   │  → Transcribe          │      │  → Stream audio both ways│    │
│   │  → AI Analysis         │      │  → Live transcript        │    │
│   │  → Score & Feedback    │      │  → End session             │    │
│   │                        │      │  → Analyze full transcript│    │
│   │  Used by:              │      │                          │    │
│   │  - Conversation Days   │      │  Used by:                │    │
│   │  - Public Speaking     │      │  - Real-Time Conversation │    │
│   │  - Impromptu           │      │    feature only           │    │
│   └────────────────────────┘      └────────────────────────┘    │
│                                                                     │
│         Both flows write to the same PracticeSession /            │
│         SpeakingSubmissions tables for unified progress tracking   │
└─────────────────────────────────────────────────────────────────┘
```

**Why two flows instead of one:** Flow A optimizes for accuracy and depth of analysis (can afford a few extra seconds since the user already finished speaking). Flow B optimizes for latency and naturalness (must feel like a real conversation, sub-second response times, using Gemini 3.1 Flash Live's native audio-to-audio path rather than a STT→LLM→TTS chain).

---

## 3. High-Level Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                              CLIENT (Next.js)                         │
│  ┌────────────────┐  ┌──────────────────┐  ┌───────────────────┐    │
│  │  Recorder UI    │  │  Live Voice UI    │  │  Feedback/Results  │   │
│  │  (Flow A)       │  │  (Flow B)         │  │  UI                │   │
│  └────────────────┘  └──────────────────┘  └───────────────────┘    │
└──────────────────────────────────────────────────────────────────────┘
         │  HTTPS (upload)         │  WSS (audio stream)      │ HTTPS
         ▼                         ▼                          ▼
┌──────────────────────────────────────────────────────────────────────┐
│                        NEXT.JS API / BACKEND LAYER                   │
│  ┌────────────────┐  ┌──────────────────┐  ┌───────────────────┐    │
│  │ Upload Handler  │  │ Live Session      │  │ Results/Progress   │   │
│  │ /api/speaking/  │  │ Gateway           │  │ API                 │   │
│  │ submit          │  │ /api/speaking/    │  │ /api/speaking/      │   │
│  │                 │  │ live/session       │  │ session/:id          │   │
│  └────────────────┘  └──────────────────┘  └───────────────────┘    │
└──────────────────────────────────────────────────────────────────────┘
         │                         │                          │
         ▼                         ▼                          ▼
┌────────────────────┐  ┌──────────────────────┐   ┌──────────────────┐
│   JOB QUEUE          │  │  GEMINI LIVE API      │   │   PostgreSQL      │
│   (Redis/BullMQ)      │  │  (WebSocket, direct    │   │  (Prisma ORM)     │
│   → async processing  │  │   audio-to-audio)      │   │                    │
└────────────────────┘  └──────────────────────┘   └──────────────────┘
         │                         │
         ▼                         ▼
┌────────────────────┐  ┌──────────────────────┐
│  WORKER SERVICE       │  │  Post-Session          │
│  - STT (Deepgram)      │  │  Analysis Worker        │
│  - Audio metrics        │  │  (reuses Flow A's       │
│    (WPM, pauses,        │  │   LangGraph pipeline     │
│    fillers)              │  │   on the full transcript)│
│  - LangGraph Feedback    │  └──────────────────────┘
│    Pipeline (Gemini)     │
└────────────────────┘
         │
         ▼
┌────────────────────┐         ┌──────────────────────┐
│  Supabase Storage /   │         │   LangSmith            │
│  S3 (audio files)      │         │  (tracing all AI calls) │
└────────────────────┘         └──────────────────────┘
```

**Key architectural decision:** Flow B's live audio never touches your backend servers directly for the audio stream itself — the client connects to Gemini Live over a WebSocket (via an ephemeral token your backend issues for security). Your backend's job in Flow B is session setup, ephemeral token issuance, and **post-session** analysis — not proxying live audio.

---

## 4. Exercise Content Generation — How Exercises Are Created Per Cycle

This answers the question underneath Flow A's Step 1 ("Fetch Exercise"): **where does the Day 10 exercise actually come from?**

### 4.1 The Core Decision: Shared Curated Bank, Not Per-User Generation

TalkFiesta generates exercises **once, offline, into a shared content bank** — not live, per-user, on every request. All users on Cycle 2 / Day 10 / Public Speaking see the same base exercise (topic, prompt, instructions).

**Why not generate fresh per user on every request:**
- **Quality control** — a human (or review agent) can check a batch of 21×3 exercises before 10,000 users ever see them; you cannot realistically review a unique AI generation for every single user session
- **Consistency** — progress/benchmarking features ("compare your Day 1 vs Day 21") assume the exercise content is stable, not different each time
- **Cost** — generating once and reusing across all users is dramatically cheaper than generating per-request
- **Deduplication** — a shared bank lets you check new content against everything already written, so Day 15 doesn't accidentally repeat Day 3's topic

This is the same content-strategy decision already made in `TalkFiesta.md` (Cycle 1 written for MVP, Cycles 2–3 post-launch, Cycles 4–5 in expansion) — this section defines **how** that writing actually happens.

### 4.2 Two-Tier Content Model

```
┌───────────────────────────────────────────────────────────┐
│  TIER 1 — Static Curated Bank                                │
│  Generated once per cycle, offline, human-reviewed            │
│  → Same base exercise for every user at (cycle, day, type)     │
└───────────────────────────────────────────────────────────┘
                          │
                          ▼  (at fetch time, optional)
┌───────────────────────────────────────────────────────────┐
│  TIER 2 — Dynamic Personalization Layer                       │
│  Lightweight, cached, applied when a user opens the exercise    │
│  → Reframes the SAME base exercise for the user's goal            │
│    (Business / Exam / Travel / Fluency) and can reference          │
│    their own recent weak areas                                       │
└───────────────────────────────────────────────────────────┘
```

Tier 1 is the expensive, quality-controlled step, done rarely (once per cycle, ahead of that cycle's release). Tier 2 is cheap and fast, done often (every time a user with a specific goal opens an exercise), and is fully optional — if it's skipped or fails, the user still gets the solid Tier 1 base exercise.

### 4.3 Tier 1 — Offline Generation Pipeline (LangGraph, Admin-Triggered)

This runs as an internal admin/content tool, not part of the live user-facing app — triggered manually by whoever is preparing a cycle's content batch (you, or later a content team).

```
                ┌──────────────────────────┐
                │  Trigger: "Generate Cycle 2  │
                │  content batch"                │
                └────────────┬─────────────┘
                             ▼
                ┌──────────────────────────┐
                │  Curriculum Planner Agent    │
                │  - Reads the Difficulty &      │
                │    Topic Progression Model      │
                │    (Section 4.4)                  │
                │  - Decides: for each of 21 days ×  │
                │    3 exercise types, what CATEGORY  │
                │    and rough CEFR target             │
                │  - Checks against Tier 1 bank for      │
                │    topics already used in prior cycles  │
                │    (avoid repetition)                     │
                └────────────┬─────────────┘
                             ▼
                ┌──────────────────────────┐
                │  Content Writer Agent          │
                │  (Gemini 3.5 Flash — one call      │
                │   per exercise slot)                 │
                │  - Given: category, CEFR target,       │
                │    exercise type, target duration        │
                │  - Generates: topic title, full prompt     │
                │    text, instructions, example response      │
                │    (optional), focus areas                     │
                └────────────┬─────────────┘
                             ▼
                ┌──────────────────────────┐
                │  Duplicate/Quality Checker      │
                │  Agent                              │
                │  - Embeds the new topic text            │
                │  - Vector similarity search against       │
                │    ALL existing exercises (all cycles)      │
                │  - Flags if similarity > threshold             │
                │  - Also checks: appropriate for CEFR level,      │
                │    no unsafe/sensitive content, correct format      │
                └────────────┬─────────────┘
                             ▼
                ┌──────────────────────────┐
                │  Human Review Gate               │
                │  - Content appears in an admin        │
                │    dashboard queue                       │
                │  - Reviewer approves / edits / rejects     │
                │  - Rejected items go back to Content         │
                │    Writer Agent with feedback for regen         │
                └────────────┬─────────────┘
                             ▼
                ┌──────────────────────────┐
                │  Publish to SPEAKING_EXERCISES   │
                │  table, status: PUBLISHED             │
                └──────────────────────────┘
```

**Why a Human Review Gate, even though this is "just" content generation:** Unlike per-submission feedback (which is graded against a user's own speech and can tolerate occasional imperfection), a bad exercise prompt is seen by *every single user* who reaches that day. One confusing or poorly-calibrated prompt at Day 10 of Cycle 1 will be hit by every new user forever. This is exactly the kind of high-leverage, low-frequency AI output where human review is worth the friction.

### 4.4 Difficulty & Topic Progression Model (The Rules Engine)

This is the deterministic logic the Curriculum Planner Agent follows — it is **not** left to the AI to decide freely; the AI fills in content within a structure defined by you.

**Within-cycle shape (repeats every cycle, same 3-week arc):**

| Days | Category | Sub-focus |
|---|---|---|
| 1–7 | Personal / concrete topics | Daily life, routines, familiar subjects |
| 8–14 | Opinion / storytelling | Preferences, experiences, simple arguments |
| 15–21 | Abstract / critical thinking | Social issues, hypotheticals, nuanced arguments |

**Across-cycle shift (the same 3-week arc, but the CEFR floor rises each cycle):**

| Cycle | CEFR Baseline | What Changes vs Cycle 1 |
|---|---|---|
| Cycle 1 — Foundation | A2–B1 | Simpler vocabulary, shorter target durations, more scaffolding/instructions |
| Cycle 2 — Intermediate | B1–B2 | Workplace/professional topics enter the "Personal" week |
| Cycle 3 — Advanced | B2–C1 | Abstract week gets genuinely open-ended, multi-perspective prompts |
| Cycle 4 — Expert | C1 | Nuanced, ambiguous prompts across all 3 weeks, less scaffolding |
| Cycle 5 — Master | C1–C2 | Near-native complexity, minimal instructions, closer to real unscripted speaking |

**Formula the Planner Agent actually uses:**
```
target_cefr = base_cefr_for_cycle[cycle_number] + week_adjustment[day_range]
target_duration = base_duration_for_cycle[cycle_number] + 10s × (day_number % 7)
category = week_category_table[day_number]  // from the within-cycle table above
```

The Planner Agent doesn't invent this structure — it reads it from a config, then asks the Content Writer Agent to produce content that fits the specific `(category, target_cefr, exercise_type)` slot. This keeps the curriculum coherent and lets you tune the *shape* of the whole program by editing one config table, without touching any prompts.

### 4.5 Data Model Additions (Tier 1)

```
SPEAKING_EXERCISES  (extends the table from TalkFiesta.md)
  ...existing fields (id, day_number, cycle_number, difficulty_level,
     topic, prompt_text, target_duration_seconds, instructions,
     exercise_type)...

  generated_by            ENUM (AI | HUMAN)              ← NEW
  review_status           ENUM (DRAFT | APPROVED |
                                 REJECTED | PUBLISHED)     ← NEW
  reviewed_by              user_id (nullable)              ← NEW
  topic_embedding          VECTOR                          ← NEW (for dedup search)
  goal_tags                JSON array                      ← NEW
                            (e.g. ["business","exam"] —
                             which goal-specific Tier 2
                             variants exist/are relevant)
  generation_batch_id       FK → ContentGenerationBatch      ← NEW

CONTENT_GENERATION_BATCH   ← NEW TABLE
  id, cycle_number, triggered_by, status
  (PLANNING | GENERATING | IN_REVIEW | PUBLISHED),
  total_slots, approved_count, rejected_count,
  created_at, published_at
```

### 4.6 Tier 2 — Dynamic Personalization at Fetch Time

This runs live, in the user-facing app, when a user actually opens an exercise — but it's deliberately lightweight and cached.

```
User opens Day 10 → GET /api/speaking/exercise/:day
                          │
                          ▼
              Look up base exercise from
              SPEAKING_EXERCISES by
              (cycle_number, day_number, exercise_type)
                          │
                          ▼
              Does user have a non-default goal
              (Business / Exam / Travel)?
                 │                    │
                NO                   YES
                 │                    │
                 ▼                    ▼
        Return base exercise    Check cache: has this
        as-is                   (exercise_id + goal)
                                 combo been personalized
                                 before?
                                    │           │
                                  YES           NO
                                    │           │
                                    ▼           ▼
                          Return cached    Run lightweight
                          personalized      Personalization Agent
                          variant           (Gemini 3.5 Flash,
                                             single fast call):
                                             reframes the SAME
                                             topic/instructions
                                             through the user's
                                             goal lens
                                                │
                                                ▼
                                       Cache result keyed by
                                       (exercise_id, goal) —
                                       NOT per-user, since users
                                       sharing a goal can share
                                       the same personalized variant
                                                │
                                                ▼
                                          Return to user
```

**Important cost/design detail:** the cache key is `(exercise_id, goal)`, not `(exercise_id, user_id)`. Every "Business English" user on Day 10 gets the same personalized variant as each other — this keeps the personalization cheap (generated once per goal per exercise, ~4 variants max per exercise, not once per user) while still feeling tailored compared to the generic default.

A further, optional per-user layer (referencing the specific user's own recent mistakes — the "Vocabulary from Your Own Mistakes" pattern) can be layered on top of this as a small injected hint line, generated fresh per user but kept to a single short sentence to control cost — e.g. *"Try to use 'nevertheless' somewhere in your answer — you tend to default to 'but.'"*

### 4.7 What Happens After Cycle 5 (Infinite Content)

Once a user finishes all 5 pre-generated cycles, there's no more Tier 1 content to serve. This is where the earlier "Day 22 — Never Actually Ends" idea plugs in as its own, separate pipeline:

- A **Curriculum Generator Agent** runs per-user (not shared), reading that user's full history — weak areas, topics they've responded well to, goal — and generates a fresh, personal Cycle 6+ on demand
- This is intentionally a different pipeline from Tier 1: lower review overhead (one user sees it, not thousands), generated just-in-time rather than batched in advance, and stored against that user's own exercise history rather than the shared bank

### 4.8 Summary — Answering the Original Question

- **How are exercises generated?** Offline, in batches, by a LangGraph pipeline (Planner → Writer → Quality Checker → Human Review), not live per request
- **How does it work per cycle?** A config-driven Difficulty & Topic Progression Model tells the Planner Agent what category/CEFR/duration each of the 21×3 slots in a cycle should target; the Writer Agent fills in the actual content within that structure
- **Does every user get identical content?** Yes at the base (Tier 1) level — this is what keeps quality high and cost low. Goal-based framing (Tier 2) is cached per-goal, not per-user, striking a balance between personalization and cost
- **What about after all 5 cycles?** A separate, per-user Curriculum Generator Agent takes over, since at that point low review overhead matters more than shared-bank efficiency

---

## 5. Flow A — Scripted Exercise Pipeline (Batch)

Used for: Conversation Days, Public Speaking, Impromptu Speaking.

```
STEP 1 — Fetch Exercise
  Client requests today's exercise
  GET /api/speaking/exercise/:day
  → Returns prompt, instructions, target duration, topic

STEP 2 — Record
  Client records audio locally (MediaRecorder API)
  Shows waveform + timer, no server interaction yet

STEP 3 — Upload
  POST /api/speaking/submit  (multipart audio upload)
  → Backend saves raw audio to Supabase Storage/S3
  → Creates SpeakingSubmission row (status: PROCESSING)
  → Pushes job to Redis/BullMQ queue
  → Returns submissionId immediately (client shows "Processing..." screen)

STEP 4 — Async Worker Picks Up Job
  Worker Service:
    a) Downloads audio from storage
    b) Sends to Deepgram → gets transcription + word-level timestamps
    c) Computes audio metrics locally:
       - Duration, word count, words-per-minute
       - Pause detection (gaps > 0.5s between words)
       - Filler word detection (um, uh, like, you know)
    d) Passes transcript + metrics into the LangGraph Feedback Pipeline
       (see Section 8) → Gemini 3.5 Flash generates structured feedback
    e) Validates output against schema (retry up to 3x on failure)
    f) Writes final scores + feedback JSON to SpeakingSubmission row
       (status: COMPLETE)

STEP 5 — Client Polls / Subscribes for Result
  Client polls GET /api/speaking/session/:id every 2s
  (or uses Supabase Realtime / SSE for push-based update)
  → When status = COMPLETE, renders Results screen

STEP 6 — Progress Update
  On completion:
    - Mark DailyActivity as COMPLETED
    - Update streak
    - Unlock next day
    - Check + award achievements
```

**Why async/queue instead of synchronous request-response:** STT + LangGraph analysis can take 5-15 seconds. Blocking an HTTP request that long is unreliable (timeouts, poor UX). A queue lets the upload return instantly and the client shows a proper "Analyzing your speech..." loading state while polling.

---

## 6. Flow B — Real-Time Conversation Pipeline (Streaming)

Used for: Real-Time AI Conversation feature only.

```
STEP 1 — Session Setup
  Client requests to start a conversation
  POST /api/speaking/live/session
  Body: { topic, persona, targetDuration }
  → Backend creates a LiveConversationSession row (status: ACTIVE)
  → Backend generates an EPHEMERAL TOKEN scoped to this session
    (short-lived, single-use credential — client never sees the real API key)
  → Returns { sessionId, ephemeralToken, wsEndpoint }

STEP 2 — Client Connects Directly to Gemini Live
  Client opens WebSocket directly to Gemini Live API using the ephemeral token
  → System instructions sent at connection start:
    - Persona (Friendly Tutor / Native Peer / Examiner / Interviewer)
    - Topic
    - Instruction to keep replies short (1-3 sentences), conversational
    - Instruction to redirect gently if user goes off-topic

STEP 3 — Live Bidirectional Audio
  User speaks → audio streams to Gemini Live continuously
  Gemini's built-in VAD detects turn-taking automatically
  Gemini streams audio response back → played through client speakers
  Gemini also streams a live transcript of both sides back over the
    same connection → client renders rolling captions in real time

STEP 4 — Client-Side Session Monitoring
  - Timer counts elapsed time
  - At 90% of target duration, a gentle UI cue appears ("wrapping up soon")
  - Hard timeout enforced client-side AND server-side (guardrail —
    see TalkFiesta-AI-Engineering.md Section 3)

STEP 5 — End Session
  User taps "End Conversation" (or timeout triggers it)
  Client closes WebSocket
  Client sends full transcript (received live from Gemini) to backend:
  POST /api/speaking/live/session/:id/end
  Body: { fullTranscript, durationSeconds }

STEP 6 — Post-Session Analysis (Reuses Flow A's Pipeline)
  Backend pushes a job to the SAME worker queue used in Flow A
  Worker runs the transcript (already have it — no STT step needed here)
  through the same LangGraph Feedback Pipeline
  → Produces the same score categories: Fluency, Grammar, Vocabulary,
    Confidence, plus conversation-specific metrics (response time,
    turn count, avg response length, topic relevance)

STEP 7 — Results
  Same Results screen pattern as Flow A, with added conversation metrics
  and the dual-speaker transcript (You / AI labeled)
```

**Key design decision — ephemeral tokens:** The client connects directly to Gemini Live rather than your backend proxying audio, because proxying live audio through your own server adds latency and infrastructure cost for no benefit. Your backend's role is issuing a short-lived, scoped credential so the real API key never reaches the client — this is a standard pattern for client-side realtime AI connections.

---

## 7. Component Breakdown

| Component | Responsibility | Flow |
|---|---|---|
| **Recorder UI** | MediaRecorder capture, waveform display, upload trigger | A |
| **Live Voice UI** | WebSocket connection, mic streaming, live caption rendering, VAD-driven UI states | B |
| **Upload Handler API** | Receives audio, stores it, creates DB row, enqueues job | A |
| **Live Session Gateway API** | Issues ephemeral tokens, creates session row, handles session-end payload | B |
| **Job Queue (Redis/BullMQ)** | Decouples upload from processing; retry handling for failed jobs | A, B (post-session) |
| **Worker Service** | Runs STT (Flow A only), computes audio metrics, invokes LangGraph pipeline | A, B |
| **LangGraph Feedback Pipeline** | Multi-step AI analysis producing structured scores/feedback | A, B |
| **Results/Progress API** | Polling endpoint for submission status, triggers streak/achievement updates | A, B |
| **Storage (Supabase/S3)** | Raw audio files (Flow A only — Flow B has no recorded audio file, only transcript) | A |
| **LangSmith** | Traces every LangGraph run for debugging and quality monitoring | A, B |

---

## 8. LangGraph Feedback Pipeline Design

Both flows converge on the same feedback pipeline once a transcript exists. This is a LangGraph state machine, not a single prompt call:

```
                    ┌─────────────────────┐
                    │   Input: transcript   │
                    │   + audio metrics      │
                    │   (WPM, pauses,         │
                    │   filler words)          │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │   Orchestrator Node    │
                    │  (validates input,      │
                    │   routes to analyzers)   │
                    └──────────┬───────────┘
             ┌─────────────────┼─────────────────┐
             ▼                 ▼                 ▼
   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
   │ Grammar Agent  │  │ Vocabulary     │  │ Fluency Agent  │
   │ Node           │  │ Agent Node      │  │ Node            │
   │ (low temp,      │  │ (word choice,   │  │ (uses audio      │
   │  finds errors,  │  │  variety,        │  │  metrics, not     │
   │  grounded on     │  │  suggestions)     │  │  just text —       │
   │  rules ref)      │  │                  │  │  pace, pauses,      │
   │                  │  │                  │  │  fillers)            │
   └────────┬─────────┘  └────────┬─────────┘  └────────┬─────────┘
            │                     │                     │
            └─────────────────────┼─────────────────────┘
                                  ▼
                       ┌─────────────────────┐
                       │  Score Aggregator      │
                       │  Node                   │
                       │  (merges 3 reports,      │
                       │   computes overall score, │
                       │   resolves overlaps)        │
                       └──────────┬───────────┘
                                  ▼
                       ┌─────────────────────┐
                       │  Schema Validation      │
                       │  (Zod/Pydantic)          │
                       │  → retry up to 3x on      │
                       │    failure                 │
                       └──────────┬───────────┘
                                  ▼
                       ┌─────────────────────┐
                       │  Output: structured     │
                       │  JSON feedback           │
                       │  → saved to DB            │
                       └─────────────────────┘
```

**Why split into 3 parallel agent nodes instead of one prompt:** Consistent with the Multi-Agent Interview Panel design in `TalkFiesta.md` — specialist agents with narrow jobs produce sharper analysis than one agent trying to do grammar + vocabulary + fluency simultaneously. Grammar and Vocabulary agents can run in parallel (both just need the transcript); the Fluency agent needs the audio metrics too. The Aggregator node is the only place where a merge/conflict-resolution decision happens.

**Model routing within this pipeline:**
- Grammar/Vocabulary/Fluency agents → **Gemini 3.5 Flash** (fast, cheap, high volume — this runs on every single submission)
- Score Aggregator → **Gemini 3.5 Flash** normally, escalate to **Gemini 3 Pro** only if the three agent reports significantly conflict with each other (rare edge case, handled by a confidence-check before aggregation)

---

## 9. API Design

| Endpoint | Method | Flow | Purpose |
|---|---|---|---|
| `/api/speaking/exercise/:day` | GET | A | Fetch today's scripted exercise prompt |
| `/api/speaking/submit` | POST | A | Upload recorded audio, kicks off async processing |
| `/api/speaking/session/:id` | GET | A, B | Poll submission status + retrieve results when ready |
| `/api/speaking/live/session` | POST | B | Create a live conversation session, returns ephemeral token |
| `/api/speaking/live/session/:id/end` | POST | B | Submit final transcript, triggers post-session analysis |
| `/api/speaking/live/session/:id/heartbeat` | POST | B | Optional — server-side session timeout enforcement |
| `/api/speaking/progress` | GET | A, B | Aggregate speaking plan progress (days completed, avg score) |

---

## 10. Database Schema (Speaking Module)

Extends the tables already defined in `TalkFiesta.md`, with additions specific to this system design:

```
SPEAKING_EXERCISES  (Flow A — unchanged from main doc)
  id, day_number, cycle_number, difficulty_level, topic,
  prompt_text, target_duration_seconds, instructions, exercise_type
  (exercise_type: CONVERSATION | PUBLIC_SPEAKING | IMPROMPTU)

SPEAKING_SUBMISSIONS  (Flow A result — unchanged core, status field added)
  id, user_id, exercise_id, daily_activity_id,
  audio_url, transcription, duration_seconds, word_count, words_per_minute,
  fluency_score, grammar_score, vocabulary_score, pronunciation_score, overall_score,
  pause_count, filler_words_count, filler_words_list,
  ai_feedback (JSON), grammar_corrections (JSON), vocabulary_suggestions (JSON),
  status (PROCESSING | COMPLETE | FAILED),      ← NEW
  processing_job_id,                             ← NEW
  submitted_at

LIVE_CONVERSATION_SESSIONS   ← NEW TABLE (Flow B)
  id
  user_id (FK → Users)
  topic
  persona (FRIENDLY_TUTOR | NATIVE_PEER | EXAMINER | INTERVIEWER)
  target_duration_seconds
  actual_duration_seconds
  status (ACTIVE | ENDED | TIMED_OUT | ERROR)
  ephemeral_token_issued_at
  full_transcript (JSON — array of {speaker, text, timestamp})
  turn_count
  avg_response_time_seconds
  avg_response_length_words
  topic_relevance_score
  submission_id (FK → SpeakingSubmissions — links to the shared
                  scoring/feedback record once post-session analysis runs)
  started_at
  ended_at
```

**Design note:** `LIVE_CONVERSATION_SESSIONS` stores the live-specific metadata (persona, turn count, response timing), while the actual scores (fluency/grammar/vocabulary/overall) live in the **same** `SPEAKING_SUBMISSIONS` table as Flow A, linked via `submission_id`. This keeps all progress-tracking and analytics queries (Section 6 of `TalkFiesta.md`) working identically regardless of which flow produced the score — the Progress dashboard doesn't need to know or care which flow was used.

---

## 11. Sequence Diagrams

### Flow A — Scripted Exercise

```
User          Client UI        API           Queue        Worker         Gemini/Deepgram    DB
 │                │              │              │             │                  │            │
 │  Start Day 4    │              │              │             │                  │            │
 │───────────────▶│              │              │             │                  │            │
 │                │  GET exercise │              │             │                  │            │
 │                │─────────────▶│              │             │                  │            │
 │                │◀─────────────│              │             │                  │            │
 │  Record speech  │              │              │             │                  │            │
 │───────────────▶│              │              │             │                  │            │
 │                │  POST submit  │              │             │                  │            │
 │                │  (audio file)  │              │             │                  │            │
 │                │─────────────▶│  Save to      │             │                  │            │
 │                │              │  storage       │             │                  │  Save row  │
 │                │              │───────────────────────────────────────────────────────────▶│
 │                │              │  Enqueue job    │             │                  │            │
 │                │              │──────────────▶│             │                  │            │
 │                │◀─────────────│  submissionId   │             │                  │            │
 │  "Analyzing..." │              │              │  Job picked │                  │            │
 │◀───────────────│              │              │  up          │                  │            │
 │                │              │              │────────────▶│                  │            │
 │                │              │              │             │  Transcribe        │            │
 │                │              │              │             │──────────────────▶│            │
 │                │              │              │             │◀──────────────────│            │
 │                │              │              │             │  LangGraph          │            │
 │                │              │              │             │  feedback pipeline   │            │
 │                │              │              │             │──────────────────▶│            │
 │                │              │              │             │◀──────────────────│            │
 │                │              │              │             │  Write results       │            │
 │                │              │              │             │────────────────────────────────▶│
 │                │  Poll status   │              │             │                  │            │
 │                │─────────────▶│──────────────────────────────────────────────────────────▶│
 │                │◀───────────── COMPLETE + scores ─────────────────────────────────────────│
 │  See results    │              │              │             │                  │            │
 │◀───────────────│              │              │             │                  │            │
```

### Flow B — Real-Time Conversation

```
User          Client UI          Backend API        Gemini Live (WSS)      Worker/DB
 │                │                    │                     │                  │
 │  Pick topic +   │                    │                     │                  │
 │  persona, Start │                    │                     │                  │
 │───────────────▶│                    │                     │                  │
 │                │  POST /live/session  │                     │                  │
 │                │───────────────────▶│  Create session row   │                  │
 │                │                    │──────────────────────────────────────▶│
 │                │                    │  Generate ephemeral    │                  │
 │                │                    │  token                  │                  │
 │                │◀───────────────────│                     │                  │
 │                │  { token, wsEndpoint }                    │                  │
 │                │  Open WSS connection directly to Gemini Live                  │
 │                │────────────────────────────────────────▶│                  │
 │                │  Send system instructions (persona/topic)  │                  │
 │                │────────────────────────────────────────▶│                  │
 │  Speak           │                    │                     │                  │
 │───────────────▶│  Stream audio ─────────────────────────▶│                  │
 │                │◀──────── Stream audio response ──────────│                  │
 │  Hear AI reply   │                    │                     │                  │
 │◀───────────────│◀──────── Live transcript chunks ─────────│                  │
 │  ... conversation continues, multiple turns ...            │                  │
 │  Tap "End"       │                    │                     │                  │
 │───────────────▶│  Close WSS ────────────────────────────▶│                  │
 │                │  POST /live/session/:id/end                │                  │
 │                │  (full transcript)                          │                  │
 │                │───────────────────▶│  Enqueue post-session   │                  │
 │                │                    │  analysis job (same       │                  │
 │                │                    │  worker/pipeline as Flow A)│                  │
 │                │                    │──────────────────────────────────────▶│
 │                │  Poll status         │                     │                  │
 │                │───────────────────▶│──────────────────────────────────────▶│
 │                │◀────────────── COMPLETE + scores ───────────────────────────│
 │  See results     │                    │                     │                  │
 │◀───────────────│                    │                     │                  │
```

---

## 12. Infrastructure & Scalability

| Concern | Approach |
|---|---|
| **Job queue** | Redis + BullMQ — handles retries, concurrency limits, dead-letter queue for repeatedly failing jobs |
| **Worker scaling** | Stateless worker processes, horizontally scalable (add more workers as submission volume grows); separate worker pool from the main Next.js API process |
| **WebSocket load (Flow B)** | Since clients connect **directly** to Gemini Live, your own infrastructure doesn't bear the WebSocket audio load — this is a major scalability advantage over building your own STT/TTS relay |
| **Ephemeral token issuance** | Lightweight, stateless endpoint — easy to scale, short-lived tokens limit blast radius if leaked |
| **Audio storage** | Flow A audio files → S3/Supabase with lifecycle policy (e.g., auto-delete raw audio after 30-90 days per your data retention policy — see `TalkFiesta-AI-Engineering.md` Section 15) |
| **Database read load** | Progress/analytics queries (Section 6 of `TalkFiesta.md`) should read from indexed, denormalized `DailyProgress` rows rather than aggregating raw submissions on every dashboard load |
| **Rate limiting** | Per-user daily caps on both submission count (Flow A) and live conversation minutes (Flow B) — enforced at the API layer before job/session creation |

---

## 13. Failure Modes & Error Handling

| Failure | Handling |
|---|---|
| Audio upload fails/interrupted | Client retries upload with exponential backoff; partial uploads discarded, not processed |
| Deepgram transcription fails | Worker retries transcription up to 2x; if still failing, mark submission FAILED, show user a clear "couldn't process your recording, please try again" state (never silently drop it) |
| LangGraph pipeline schema validation fails after retries | Mark submission FAILED with a generic fallback message rather than showing garbled AI output (per `TalkFiesta-AI-Engineering.md` Section 17 — Graceful Degradation) |
| Gemini Live WebSocket drops mid-conversation | Client detects disconnect, attempts one reconnect; if reconnect fails, ends session gracefully and sends whatever partial transcript was captured for analysis — user still gets a (partial) feedback report rather than losing the session entirely |
| User exceeds daily rate limit | Clear UI message with reset time, not a silent failure or generic error |
| Worker queue backlog grows (traffic spike) | Auto-scale worker pool; if still backlogged, submissions show an honest "Processing may take a few extra minutes" message rather than an indefinite spinner |

---

## 14. Cost & Performance Considerations

- **Flow A cost per submission:** Deepgram transcription (per-minute) + 3 parallel Gemini 3.5 Flash calls (Grammar/Vocab/Fluency) + 1 Aggregator call — track this as a per-submission cost metric (see `TalkFiesta-AI-Engineering.md` Section 14)
- **Flow B cost per session:** Gemini Live pricing is typically higher per-minute than batch text calls, which is exactly why session length caps matter — a hard 10-minute session limit isn't just a UX choice, it's a cost control
- **Latency targets:**
  - Flow A: exercise fetch < 500ms, submission upload acknowledgment < 1s, full analysis result available within 15s of upload (shown as a progress state, not a blocking wait)
  - Flow B: audio round-trip latency should feel conversational — sub-second response start is the target Gemini Live is built for; this is why Flow B must NOT be routed through your own backend as an audio proxy

---

## 15. How This Connects to Guardrails

This system design assumes the guardrails defined in `TalkFiesta-AI-Engineering.md` are implemented at these specific points:

| Guardrail | Where It Plugs Into This Design |
|---|---|
| Structured output validation (AI Engineering doc, Section 2) | The "Schema Validation" node in the LangGraph pipeline (Section 8 here) |
| LangGraph step/loop limits (AI Engineering doc, Section 4) | Orchestrator Node in Section 8 — hard cap on retries and agent calls |
| Session timeouts (AI Engineering doc, Section 3) | Client + server-side enforcement in Flow B, Step 4 (Section 6) |
| Content moderation for sensitive disclosures (AI Engineering doc, Section 1) | Runs on the transcript inside the Fluency/Grammar agent pass, before feedback is generated — flagged content routes to a support-resource response instead of normal scoring |
| Rate limiting (AI Engineering doc, Section 5) | Enforced at `/api/speaking/submit` and `/api/speaking/live/session` before any job/session is created |
| LangSmith tracing (AI Engineering doc, Section 6) | Wraps every node in both the content generation pipeline (Section 4) and the feedback pipeline (Section 8) |
| Human review as a guardrail (AI Engineering doc, Section 9 — Evaluation) | The Human Review Gate in Tier 1 content generation (Section 4.3) — the same "don't trust AI output blindly" principle applied to curriculum content, not just per-user feedback |
| Duplicate/quality checking before publish | Section 4.3's Duplicate/Quality Checker Agent — a content-specific guardrail not covered elsewhere, since it's unique to batch-generated curriculum rather than per-submission feedback |

---

**Project:** TalkFiesta
**Document:** Speaking Module — System Design
**Companion to:** `TalkFiesta.md`, `TalkFiesta-AI-Engineering.md`
**Status:** Ready for implementation planning

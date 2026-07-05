# 🗂️ TalkFiesta — Codebase Structure

**Companion document to `TalkFiesta.md`, `TalkFiesta-AI-Engineering.md`, `TalkFiesta-Speaking-Module-System-Design.md`, `TalkFiesta-Vocabulary-Module-System-Design.md`, and `TalkFiesta-Writing-Module-System-Design.md`**

> Defines the actual repo/folder structure for a Python FastAPI backend + Next.js frontend, mapped directly onto the module system designs already written.

---

## Table of Contents

1. Key Architectural Decisions
2. Backend Folder Structure — `talkfiesta-backend/`
3. Frontend Folder Structure — `talkfiesta-frontend/`
4. How This Maps to the System Design Docs
5. Notes & Rationale

---

## 1. Key Architectural Decisions

Since the AI layer (LangGraph, LangChain, Gemini SDK) is deeply Python-native, splitting into a **Python FastAPI backend + Next.js frontend** makes more sense than cramming everything into Next.js API routes.

| Decision          | Recommendation                                                                 | Why                                                                                                                                                                 |
| ----------------- | ------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Backend framework | **FastAPI**                                                                    | Native async, first-class Pydantic (matches structured-output guardrail needs from `TalkFiesta-AI-Engineering.md` Section 2), best-in-class for LangGraph/LangChain |
| ORM               | **SQLAlchemy + Alembic** (not Prisma)                                          | Prisma's Python client is far less mature than its JS one — SQLAlchemy is the standard pairing with FastAPI                                                         |
| Job queue         | **Celery** or **ARQ** (not BullMQ)                                             | Python-native async task queue, replaces the BullMQ/Redis pattern used throughout the module system design docs 1:1                                                 |
| Frontend          | **Next.js — pure frontend, no business-logic API routes**                      | Next.js talks to FastAPI over HTTP; keep Next.js API routes empty or thin (auth cookie handling only)                                                               |
| Type sync         | Generate TypeScript types from FastAPI's OpenAPI schema (`openapi-typescript`) | Keeps frontend types and Pydantic schemas from drifting apart                                                                                                       |

---

## 2. Backend Folder Structure — `talkfiesta-backend/`

```
talkfiesta-backend/
├── app/
│   ├── main.py                        # FastAPI app entrypoint
│   │
│   ├── core/
│   │   ├── config.py                  # Pydantic Settings (env vars)
│   │   ├── security.py                # JWT auth, Gemini Live ephemeral token issuance
│   │   ├── logging.py
│   │   └── curriculum_config.py       # cycle→CEFR progression tables (Section 4 of each module doc)
│   │
│   ├── db/
│   │   ├── session.py                 # SQLAlchemy engine/session
│   │   ├── base.py
│   │   └── models/                    # one file per domain, mirrors the schemas in the design docs
│   │       ├── user.py
│   │       ├── speaking.py            # SpeakingExercise, SpeakingSubmission, LiveConversationSession
│   │       ├── vocabulary.py          # VocabularyWord, UserVocabulary, PersonalizedVocabSuggestion
│   │       ├── writing.py             # WritingPrompt, WritingSubmission, WritingSubmissionVersion
│   │       ├── progress.py            # DailyProgress, Achievement, UserAchievement
│   │       └── content_generation.py  # shared ContentGenerationBatch table
│   │
│   ├── schemas/                       # Pydantic request/response models (API contracts)
│   │   ├── speaking.py
│   │   ├── vocabulary.py
│   │   ├── writing.py
│   │   ├── auth.py
│   │   └── progress.py
│   │
│   ├── api/
│   │   ├── deps.py                    # get_current_user, get_db, shared dependencies
│   │   └── v1/
│   │       ├── router.py              # aggregates all sub-routers
│   │       ├── auth.py
│   │       ├── speaking.py            # maps to endpoints in Speaking System Design Section 9
│   │       ├── vocabulary.py          # maps to Vocabulary doc Section 9
│   │       ├── writing.py             # maps to Writing doc Section 10
│   │       ├── progress.py
│   │       └── live.py                # POST /speaking/live/session (ephemeral token issuance)
│   │
│   ├── agents/                        # LangGraph pipelines — ONE package per module
│   │   ├── speaking/
│   │   │   ├── feedback_graph.py      # Grammar/Vocab/Fluency agents + aggregator
│   │   │   ├── content_generation_graph.py
│   │   │   └── prompts/               # versioned prompt templates (externalized, per AI Eng doc Section 8)
│   │   ├── vocabulary/
│   │   │   ├── context_eval_graph.py
│   │   │   ├── weak_word_extraction_graph.py
│   │   │   ├── word_bank_generation_graph.py
│   │   │   └── prompts/
│   │   ├── writing/
│   │   │   ├── feedback_graph.py      # Grammar/Structure/Vocab/Coherence + supervisor
│   │   │   ├── revision_comparison_graph.py
│   │   │   ├── prompt_generation_graph.py
│   │   │   └── prompts/
│   │   └── interview_panel/
│   │       ├── panel_graph.py         # HR/Technical/Manager orchestrator
│   │       └── prompts/
│   │
│   ├── services/                      # external API clients
│   │   ├── gemini_client.py           # Gemini 3.5 Flash / 3 Pro wrapper + model routing
│   │   ├── gemini_live_client.py      # Live API session helpers
│   │   ├── deepgram_client.py
│   │   ├── tts_client.py
│   │   ├── storage_client.py          # S3/Supabase
│   │   └── langsmith_tracing.py
│   │
│   ├── workers/                       # Celery/ARQ task consumers (replaces BullMQ)
│   │   ├── celery_app.py
│   │   ├── speaking_tasks.py          # runs feedback_graph on queued submissions
│   │   ├── vocabulary_tasks.py
│   │   └── writing_tasks.py
│   │
│   ├── crud/                          # DB access layer (repository pattern, keeps routers thin)
│   │   ├── speaking.py
│   │   ├── vocabulary.py
│   │   ├── writing.py
│   │   └── user.py
│   │
│   └── middleware/
│       ├── rate_limit.py              # per-user daily caps (Speaking/Vocab/Writing guardrails)
│       └── error_handler.py           # graceful degradation per AI Engineering doc Section 17
│
├── alembic/
│   └── versions/                      # DB migrations
│
├── tests/
│   ├── unit/
│   ├── integration/
│   └── eval/                          # golden dataset regression tests (AI Eng doc Section 9)
│
├── scripts/
│   └── generate_cycle_content.py      # admin CLI — triggers content generation batches
│
├── .env.example
├── pyproject.toml
└── docker-compose.yml                 # api + worker + redis + postgres, one command to run everything
```

---

## 3. Frontend Folder Structure — `talkfiesta-frontend/`

```
talkfiesta-frontend/
├── app/
│   ├── (auth)/
│   │   ├── login/page.tsx
│   │   ├── register/page.tsx
│   │   └── layout.tsx
│   │
│   ├── (onboarding)/
│   │   ├── level-assessment/page.tsx
│   │   ├── goal-selection/page.tsx
│   │   └── layout.tsx
│   │
│   ├── (dashboard)/
│   │   ├── dashboard/page.tsx
│   │   ├── speaking/
│   │   │   ├── page.tsx               # 21-day grid (Flow A entry)
│   │   │   ├── [day]/page.tsx         # exercise + recorder screen
│   │   │   ├── live/page.tsx          # Real-Time Conversation (Flow B)
│   │   │   └── interview-panel/page.tsx
│   │   ├── vocabulary/
│   │   │   ├── page.tsx               # Flow A entry
│   │   │   ├── [day]/page.tsx
│   │   │   ├── review/page.tsx        # Flow B — spaced repetition
│   │   │   └── bank/page.tsx          # personal vocabulary bank
│   │   ├── writing/
│   │   │   ├── page.tsx
│   │   │   ├── [day]/page.tsx         # editor + submit + revise
│   │   │   └── portfolio/page.tsx
│   │   ├── progress/page.tsx
│   │   ├── profile/page.tsx
│   │   └── layout.tsx                 # sidebar/bottom nav shell
│   │
│   ├── layout.tsx
│   ├── page.tsx                       # landing page
│   └── globals.css
│
├── components/
│   ├── ui/                            # shadcn primitives
│   ├── layout/
│   ├── speaking/
│   │   ├── Recorder.tsx
│   │   ├── LiveConversationUI.tsx     # connects DIRECTLY to Gemini Live over WSS
│   │   └── FeedbackReport.tsx
│   ├── vocabulary/
│   │   ├── WordCard.tsx
│   │   ├── FillBlankExercise.tsx
│   │   ├── MatchDefinitions.tsx
│   │   └── ReviewQuiz.tsx
│   ├── writing/
│   │   ├── Editor.tsx
│   │   └── MultiAgentFeedback.tsx     # 4-category breakdown UI
│   ├── progress/
│   │   └── charts/
│   └── shared/
│
├── lib/
│   ├── api/                           # typed client wrapping FastAPI calls
│   │   ├── client.ts                  # base fetch wrapper (auth headers, error handling)
│   │   ├── speaking.ts
│   │   ├── vocabulary.ts
│   │   └── writing.ts
│   ├── gemini-live/
│   │   └── liveClient.ts              # browser-side WSS connection (uses ephemeral token from backend)
│   └── utils/
│
├── hooks/
│   ├── useAudioRecorder.ts
│   ├── useLiveConversation.ts
│   └── usePolling.ts                  # polls /submission/:id until COMPLETE
│
├── store/
│   ├── authStore.ts
│   └── practiceStore.ts
│
├── types/
│   └── generated/                     # auto-generated from FastAPI's OpenAPI schema — never hand-edited
│
├── public/
└── package.json
```

---

## 4. How This Maps to the System Design Docs

| Codebase Location                                      | Maps to Design Doc                                                                             |
| ------------------------------------------------------ | ---------------------------------------------------------------------------------------------- |
| `app/agents/speaking/feedback_graph.py`                | `TalkFiesta-Speaking-Module-System-Design.md` Section 8 (LangGraph Feedback Pipeline)          |
| `app/agents/speaking/content_generation_graph.py`      | `TalkFiesta-Speaking-Module-System-Design.md` Section 4 (Exercise Content Generation)          |
| `app/api/v1/live.py` + `lib/gemini-live/liveClient.ts` | `TalkFiesta-Speaking-Module-System-Design.md` Section 6 (Flow B — ephemeral token pattern)     |
| `app/agents/interview_panel/panel_graph.py`            | `TalkFiesta.md` Section 9 (Multi-Agent Interview Panel)                                        |
| `app/agents/vocabulary/context_eval_graph.py`          | `TalkFiesta-Vocabulary-Module-System-Design.md` Section 9 (Exercise-Specific AI Design)        |
| `app/agents/vocabulary/weak_word_extraction_graph.py`  | `TalkFiesta-Vocabulary-Module-System-Design.md` Section 7 (Flow C — Personalized Vocabulary)   |
| `app/agents/writing/feedback_graph.py`                 | `TalkFiesta-Writing-Module-System-Design.md` Section 7 (Multi-Agent Feedback Pipeline)         |
| `app/agents/writing/revision_comparison_graph.py`      | `TalkFiesta-Writing-Module-System-Design.md` Section 7.4 (Revision Comparison)                 |
| `app/workers/*_tasks.py`                               | The "Job Queue" + "Worker Service" boxes in every module doc's High-Level Architecture diagram |
| `app/middleware/rate_limit.py`                         | `TalkFiesta-AI-Engineering.md` Section 5 (Abuse & Cost Guardrails)                             |
| `app/middleware/error_handler.py`                      | `TalkFiesta-AI-Engineering.md` Section 17 (Graceful Degradation)                               |
| `tests/eval/`                                          | `TalkFiesta-AI-Engineering.md` Section 9 (Evaluation — golden dataset)                         |
| `**/prompts/` subfolders                               | `TalkFiesta-AI-Engineering.md` Section 8 (Prompt Engineering as a Managed System)              |
| `app/core/curriculum_config.py`                        | The Difficulty & Topic Progression Model formula in every module doc's Section 4               |

---

## 5. Notes & Rationale

**1. Next.js API routes aren't gone entirely.** Keep a thin `app/api/auth/[...nextauth]/route.ts` if using NextAuth for session/cookie handling on the frontend, but it should just forward to FastAPI for actual user validation, not duplicate business logic.

**2. `agents/` is the single most important folder.** It's a direct 1:1 mapping to every LangGraph pipeline diagram in the three module design docs. Anyone opening this repo can match `agents/writing/feedback_graph.py` straight to Section 7 of `TalkFiesta-Writing-Module-System-Design.md`.

**3. `prompts/` subfolders under each agent package** operationalize the "version every prompt, externalize from code" guardrail (`TalkFiesta-AI-Engineering.md` Section 8). Keep prompts as separate `.py` or `.yaml` files, not inline strings buried in graph logic.

**4. `tests/eval/`** is where the golden dataset regression tests live (`TalkFiesta-AI-Engineering.md` Section 9). Worth scaffolding this folder on day one, even empty, as a forcing function to actually build it early rather than "later."

**5. The Gemini Live connection stays client-to-Gemini, not backend-proxied.** `lib/gemini-live/liveClient.ts` on the frontend connects directly using the ephemeral token FastAPI's `/api/v1/live` endpoint issues, exactly as designed in the Speaking Module doc.

---

**Project:** TalkFiesta
**Document:** Codebase Structure (FastAPI + Next.js)
**Companion to:** `TalkFiesta.md`, `TalkFiesta-AI-Engineering.md`, `TalkFiesta-Speaking-Module-System-Design.md`, `TalkFiesta-Vocabulary-Module-System-Design.md`, `TalkFiesta-Writing-Module-System-Design.md`
**Status:** Ready for repo scaffolding

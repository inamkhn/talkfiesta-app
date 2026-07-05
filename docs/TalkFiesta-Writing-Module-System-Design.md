# ✍️ TalkFiesta — Writing Module System Design

**Companion document to `TalkFiesta.md`, `TalkFiesta-AI-Engineering.md`, `TalkFiesta-Speaking-Module-System-Design.md`, and `TalkFiesta-Vocabulary-Module-System-Design.md`**

> Covers the full technical system design for the Writing Module: daily prompts, the multi-agent feedback panel, the revision system, and the writing portfolio.

---

## Table of Contents

1. Module Scope
2. Key Design Insight — Writing Needs the Multi-Agent Pattern
3. High-Level Architecture
4. Content Generation — Writing Prompt Bank Per Cycle
5. Flow A — Daily Writing Submission & Feedback
6. Flow B — Revision Loop
7. Multi-Agent Feedback Pipeline Design (LangGraph)
8. Writing Portfolio (Read Path)
9. Component Breakdown
10. API Design
11. Database Schema
12. Sequence Diagrams
13. Infrastructure & Scalability
14. Failure Modes & Error Handling
15. Cost & Performance Considerations
16. How This Connects to Guardrails

---

## 1. Module Scope

The Writing Module covers everything in `TalkFiesta.md` Section 5:

| Sub-Feature | Description |
|---|---|
| **Daily Writing Prompts** | 1 prompt/day × 21 days × 5 cycles = 105 prompts total, rotating Descriptive → Narrative → Argumentative |
| **Writing Editor** | Distraction-free editor, live word count, optional timer, auto-save |
| **AI Feedback** | Grammar (30%), Structure (30%), Vocabulary (20%), Coherence (20%) — weighted overall score |
| **Revision System** | Up to 3 resubmissions per prompt, each re-scored |
| **Writing Portfolio** | All past submissions browsable, score trend over time |

Unlike Speaking (2 flows) and Vocabulary (3 flows), Writing has **one core submission flow with a loop back into itself** (revision), plus a read-only portfolio view — so this design centers on getting that one flow and its feedback pipeline right, rather than splitting into many parallel flows.

---

## 2. Key Design Insight — Writing Needs the Multi-Agent Pattern

Writing feedback is exactly the use case the **Multi-Agent Writing Feedback Panel** concept (raised earlier as a multi-agent idea) was designed for, and this module is where it should actually be built — not as a nice-to-have, but as the core feedback engine.

**Why one generalist prompt is worse here specifically:** Grammar checking is a low-temperature, rules-based task. Structure/flow analysis requires holding the whole essay in view and judging organization. Vocabulary suggestions require comparing word choice against the CEFR level. Coherence is about whether the *argument* makes sense, not whether individual sentences are correct. Asking one Gemini call to juggle all four simultaneously produces shallower results on each than four agents each doing one job well — the same principle already established for the Speaking Module's Grammar/Vocabulary/Fluency split and the Interview Panel's HR/Technical/Manager split.

| Agent | Focus | Independent of the others? |
|---|---|---|
| **Grammar Agent** | Spelling, punctuation, tense, subject-verb agreement, articles, prepositions | ✅ Fully — only needs the raw text |
| **Structure Agent** | Paragraph organization, intro/body/conclusion, transitions, sentence variety | ✅ Fully — only needs the raw text |
| **Vocabulary Agent** | Word choice, repetition, CEFR-appropriate upgrades | ✅ Fully — only needs the raw text |
| **Coherence Agent** | Logical flow, argument strength, topic relevance to the prompt | ⚠️ Needs the *prompt* too, not just the essay |
| **Supervisor/Aggregator Agent** | Merges all 4 reports, resolves overlaps, computes weighted score, writes the final narrative feedback | Depends on all 4 |

---

## 3. High-Level Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                              CLIENT (Next.js)                         │
│  ┌────────────────┐  ┌──────────────────┐  ┌───────────────────┐    │
│  │  Prompt Screen   │  │  Writing Editor    │  │  Feedback/Results   │   │
│  │  (pre-writing      │  │  (auto-save,        │  │  Screen (multi-       │   │
│  │   support)           │  │   word count, timer)  │  │  agent report + revise│   │
│  └────────────────┘  └──────────────────┘  └───────────────────┘    │
└──────────────────────────────────────────────────────────────────────┘
         │                         │                          │
         ▼                         ▼                          ▼
┌──────────────────────────────────────────────────────────────────────┐
│                        NEXT.JS API / BACKEND LAYER                   │
│  ┌────────────────┐  ┌──────────────────┐  ┌───────────────────┐    │
│  │ Prompt API        │  │ Submit API           │  │ Revision API          │   │
│  │ /api/writing/       │  │ /api/writing/          │  │ /api/writing/           │   │
│  │ prompt/:day          │  │ submit                  │  │ submission/:id/revise    │   │
│  └────────────────┘  └──────────────────┘  └───────────────────┘    │
└──────────────────────────────────────────────────────────────────────┘
         │                         │                          │
         ▼                         ▼                          ▼
┌────────────────────┐  ┌──────────────────────┐   ┌──────────────────┐
│  WRITING_PROMPTS       │  │  Job Queue                │   │  PostgreSQL          │
│  (static bank, per       │  │  (Redis/BullMQ) —          │   │  (Prisma ORM)          │
│   cycle — see Section 4)  │  │  same queue used by          │   │                        │
│                            │  │  Speaking/Vocabulary            │   │                        │
└────────────────────┘  └──────────────────────┘   └──────────────────┘
                                    │
                                    ▼
                    ┌───────────────────────────────┐
                    │   MULTI-AGENT FEEDBACK PIPELINE    │
                    │   (LangGraph — see Section 7)        │
                    │                                        │
                    │   Grammar ─┐                            │
                    │   Structure ─┼─▶ Supervisor Agent ─▶ Score │
                    │   Vocabulary ─┤     (merge + weight)         │
                    │   Coherence ─┘                                │
                    └───────────────────────────────┘
                                    │
                                    ▼
                    ┌───────────────────────────────┐
                    │   LangSmith (traces every agent)   │
                    └───────────────────────────────┘
```

**Key architectural decision:** Writing submissions are text, not audio — there's no STT step, no real-time streaming variant needed (unlike Speaking's Flow A/B split). This makes Writing's pipeline simpler in one respect (no audio processing) but the *feedback quality bar* is higher, since users can reread and scrutinize written feedback in a way they can't with spoken feedback — errors or vague feedback are more visible and more likely to erode trust.

---

## 4. Content Generation — Writing Prompt Bank Per Cycle

Same two-tier philosophy established in the Speaking and Vocabulary designs: **generated once per cycle, offline, human-reviewed, shared across all users.**

### 4.1 Prompt Generation Pipeline (LangGraph, Admin-Triggered)

```
Trigger: "Generate Cycle 2 writing prompt batch" (21 prompts)
                    │
                    ▼
        ┌──────────────────────────┐
        │  Prompt Planner Agent          │
        │  - Reads the Type & CEFR           │
        │    Progression Model (4.2)            │
        │  - Days 1-7 → Descriptive prompts        │
        │  - Days 8-14 → Narrative prompts            │
        │  - Days 15-21 → Argumentative/Opinion          │
        │  - Checks against ALL 105 prompts across          │
        │    every cycle already published (no repeat          │
        │    topics — a Descriptive prompt about "your            │
        │    hometown" shouldn't appear twice across the             │
        │    whole program)                                             │
        └────────────┬─────────────┘
                     ▼
        ┌──────────────────────────┐
        │  Prompt Writer Agent            │
        │  (Gemini 3.5 Flash — one            │
        │   call per prompt)                     │
        │  - Generates: prompt title, full          │
        │    prompt text, target word count,           │
        │    optional time limit, writing tips            │
        │    specific to this prompt type, optional          │
        │    sample outline                                     │
        └────────────┬─────────────┘
                     ▼
        ┌──────────────────────────┐
        │  Duplicate/Quality Checker      │
        │  - Embedding similarity check          │
        │    against all 105 program prompts        │
        │  - Flags prompts that are too similar         │
        │    in theme, not just wording                     │
        └────────────┬─────────────┘
                     ▼
        ┌──────────────────────────┐
        │  Human Review Gate               │
        │  - Reviewer checks the prompt is        │
        │    clear, appropriately scoped for          │
        │    the target word count, and free              │
        │    of anything that could surface                  │
        │    distressing personal content                        │
        │    unexpectedly (see Section 16 — the same           │
        │    duty-of-care concern flagged in                       │
        │    `TalkFiesta-AI-Engineering.md` Section 1)               │
        └────────────┬─────────────┘
                     ▼
        Publish to WRITING_PROMPTS, status: PUBLISHED
```

**Why the review gate specifically checks for sensitive-content risk here:** Writing prompts like "describe a difficult experience" or "write about overcoming a challenge" are exactly the kind of prompt category flagged in `TalkFiesta-AI-Engineering.md` Section 1 as likely to surface real personal distress. This is the point in the system where that risk is *authored*, so it's the natural checkpoint to catch and phrase prompts carefully — a well-worded prompt can invite reflection without demanding trauma disclosure.

### 4.2 Prompt Type & CEFR Progression Model

Mirrors the pattern already used in Speaking and Vocabulary — a config-driven rules engine:

| Days (within cycle) | Prompt Type | Focus |
|---|---|---|
| 1–7 | Descriptive | Adjectives, sensory detail, imagery |
| 8–14 | Narrative | Past tenses, sequencing, transitions |
| 15–21 | Argumentative/Opinion | Thesis, supporting points, conclusion |

Same cross-cycle CEFR shift as the other two modules: `target_cefr = base_cefr_for_cycle[cycle_number] + week_adjustment[day_range]`. Target word count also scales up per cycle (e.g., 50–100 words in Cycle 1 → 150–250 words by Cycle 5).

### 4.3 Data Model Additions (Content Generation)

```
WRITING_PROMPTS  (extends the table from TalkFiesta.md)
  ...existing fields (id, day_number, difficulty_level, prompt_title,
     prompt_text, prompt_type, target_word_count, time_limit_minutes,
     focus_areas, writing_tips, sample_outline)...

  cycle_number              INT                          ← NEW
  generated_by                ENUM (AI | HUMAN)             ← NEW
  review_status                ENUM (DRAFT | APPROVED |
                                       REJECTED | PUBLISHED)   ← NEW
  reviewed_by                   user_id (nullable)            ← NEW
  prompt_embedding                VECTOR                       ← NEW (dedup search)
  sensitivity_flagged              BOOLEAN                       ← NEW (reviewer marks
                                    prompts that touch personal/
                                    emotional territory, so the
                                    UI can optionally soften the
                                    framing or add a gentle note)
  generation_batch_id               FK → ContentGenerationBatch
                                     (shared table with Speaking/
                                      Vocabulary, module_type='WRITING')
```

---

## 5. Flow A — Daily Writing Submission & Feedback

```
STEP 1 — Fetch Today's Prompt
  GET /api/writing/prompt/:day
  → Looks up WRITING_PROMPTS by (cycle_number, day_number)
  → Returns prompt text, target word count, tips, optional outline

STEP 2 — Pre-Writing Support (Client-only)
  User reads prompt, optional writing tips, optional sample outline
  No backend interaction

STEP 3 — Writing (Client-only, with auto-save)
  User writes in the editor
  Client auto-saves draft locally / to a lightweight draft endpoint
  every 30s (does NOT trigger AI analysis — pure persistence)
  POST /api/writing/draft/save  (cheap, no AI, just a DB write)

STEP 4 — Submit for Review
  User clicks "Submit for Review" → confirmation dialog
  POST /api/writing/submit
  Body: { promptId, content, wordCount, timeSpentSeconds }
  → Creates WritingSubmission row (status: PROCESSING)
  → Enqueues job to the SAME job queue used by Speaking/Vocabulary
  → Returns submissionId immediately, client shows "Analyzing..." state

STEP 5 — Async Worker Runs Multi-Agent Feedback Pipeline
  Worker picks up job → runs the full LangGraph pipeline from
  Section 7 → writes structured feedback + scores to the
  WritingSubmission row (status: COMPLETE)

STEP 6 — Client Polls / Subscribes for Result
  Same polling pattern as Speaking Module Flow A
  GET /api/writing/submission/:id
  → Renders Results screen when COMPLETE

STEP 7 — Results Screen
  - Overall score (0-100) + 4-category breakdown
  - Original text with inline error highlights (color-coded by
    agent: grammar errors, structure notes, vocabulary suggestions)
  - Expandable feedback cards per category
  - "Revise" or "Complete Exercise" buttons (see Flow B)

STEP 8 — On "Complete Exercise" (no further revision)
  Mark DailyActivity COMPLETED, update streak, check achievements
  Submission becomes part of the Writing Portfolio (Section 8)
```

---

## 6. Flow B — Revision Loop

```
STEP 1 — User Clicks "Revise"
  Client returns to the editor, PRE-FILLED with their original text
  Feedback stays visible in a sidebar (doesn't disappear) so the
  user can actively address specific points while editing

STEP 2 — User Edits
  Same auto-save behavior as Flow A Step 3

STEP 3 — Resubmit
  POST /api/writing/submission/:id/revise
  Body: { newContent, wordCount }
  → Increments revision_count on the ORIGINAL submission record
    (revisions are versions of the same submission, not new rows —
     see data model in Section 11)
  → Enqueues a new feedback pipeline job, same as Flow A Step 5
  → Runs the FULL multi-agent pipeline again on the new text
    (not a diff-based re-check — a fresh, complete evaluation,
     since a full rewrite deserves a full re-read)

STEP 4 — Comparison Results Screen
  Shows: new score vs. previous score (e.g., "74 → 86, +12")
  Highlights which specific issues from the previous round were
  fixed (cross-references the previous feedback's error list against
  the new submission — this comparison IS a small AI-assisted step,
  see Section 7.4)

STEP 5 — Revision Limit
  Maximum 3 revisions per submission (per TalkFiesta.md)
  After the 3rd revision, the "Revise" button is replaced with
  "Complete Exercise" only — this cap exists both for UX (avoid
  endless perfectionism loops) and cost (avoid unbounded re-analysis)
```

**Why revisions re-run the full pipeline instead of a lighter incremental check:** A user might rewrite an entire paragraph based on structure feedback — a diff-based "only check what changed" approach would miss new grammar errors introduced in the rewrite, or fail to notice the structure issue wasn't actually fixed, just moved. A full re-evaluation is more expensive per revision but far more reliable, and the 3-revision cap keeps the total cost bounded and predictable.

---

## 7. Multi-Agent Feedback Pipeline Design (LangGraph)

```
                    ┌─────────────────────┐
                    │   Input: submission     │
                    │   text + prompt context   │
                    │   (prompt text, type,       │
                    │   target word count)          │
                    └──────────┬───────────┘
                               ▼
                    ┌─────────────────────┐
                    │   Orchestrator Node     │
                    │  (validates input length, │
                    │   routes to 4 agent nodes,  │
                    │   enforces step/loop limit)   │
                    └──────────┬───────────┘
         ┌───────────────────┬─┴─┬───────────────────┐
         ▼                   ▼   ▼                   ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│ Grammar Agent  │  │ Structure      │  │ Vocabulary     │  │ Coherence      │
│                 │  │ Agent           │  │ Agent           │  │ Agent           │
│ Input: text      │  │ Input: text      │  │ Input: text      │  │ Input: text +    │
│ only               │  │ only               │  │ only               │  │ PROMPT (needs      │
│ Low temperature      │  │ Checks: intro/       │  │ Checks: repetition,  │  │ this to judge         │
│ (this is a rules-      │  │ body/conclusion,       │  │ overused simple         │  │ topic relevance)         │
│ based check, not a       │  │ transitions, sentence     │  │ words, CEFR-               │  │ Checks: logical              │
│ creative task)             │  │ variety                     │  │ appropriate upgrades         │  │ flow, argument strength,       │
│ Output: error list            │  │ Output: structure             │  │ Output: word-level               │  │ relevance to the prompt           │
│ with positions,                 │  │ notes + score                    │  │ suggestions + score                 │  │ Output: coherence notes              │
│ explanations, score                │  └──────────────┘  └──────────────┘  │ + score                                │
└──────────────┘                                                          └──────────────┘
         │                   │                   │                   │
         └───────────────────┴─────────┬─────────┴───────────────────┘
                                       ▼
                            ┌─────────────────────┐
                            │  Supervisor/Aggregator  │
                            │  Agent                    │
                            │  - Merges all 4 reports      │
                            │  - Resolves overlaps (e.g. if   │
                            │    Grammar and Structure both       │
                            │    flag the same sentence, avoid       │
                            │    redundant feedback)                    │
                            │  - Computes weighted overall score:          │
                            │    Grammar 30% + Structure 30% +                │
                            │    Vocabulary 20% + Coherence 20%                 │
                            │  - Writes final narrative feedback:                 │
                            │    strengths (2-3), improvements (2-3),               │
                            │    specific actionable tips (3-5)                        │
                            └──────────┬───────────┘
                                       ▼
                            ┌─────────────────────┐
                            │  Schema Validation      │
                            │  (Zod/Pydantic)          │
                            │  → retry up to 3x on       │
                            │    failure                   │
                            └──────────┬───────────┘
                                       ▼
                            ┌─────────────────────┐
                            │  Output: structured     │
                            │  JSON feedback →          │
                            │  saved to WritingSubmission│
                            └─────────────────────┘
```

### 7.1 Why Grammar/Structure/Vocabulary Run Fully in Parallel

These three agents each only need the raw submission text — no dependency on each other or on the prompt. Running them concurrently (not sequentially) keeps total pipeline latency close to the *slowest single agent*, not the sum of all four.

### 7.2 Why Coherence Agent Needs the Prompt, Not Just the Text

Judging "does this essay make sense" requires knowing what it was supposed to be about and what type of writing it is — a Narrative prompt's coherence bar (does the story flow) is different from an Argumentative prompt's (does the argument hold together). This agent alone carries prompt context into its evaluation.

### 7.3 Model Routing

- Grammar / Structure / Vocabulary / Coherence agents → **Gemini 3.5 Flash** (fast, cheap, runs on every submission)
- Supervisor/Aggregator → **Gemini 3.5 Flash** normally, escalates to **Gemini 3 Pro** only when the 4 agent reports meaningfully conflict (e.g., Grammar scores it high but Coherence scores it very low — worth a stronger model resolving the tension rather than a shallow merge)

### 7.4 Revision Comparison (Flow B, Step 4)

A small, separate step — not one of the 4 main agents — that runs only during revisions:

```
Input: previous submission's error list + new submission's error list
Task: identify which specific previous issues no longer appear
      (simple set comparison, lightly AI-assisted for near-matches
      where wording changed but the underlying issue is the same)
Output: { fixedIssues: [...], stillPresentIssues: [...],
          newIssuesIntroduced: [...] }
```

This is what powers the "here's what you fixed" comparison in the revision results screen — a small, cheap, single Gemini 3.5 Flash call, not a full pipeline re-run.

---

## 8. Writing Portfolio (Read Path)

Purely a read/query feature over data already produced by Flow A/B — no new AI processing.

```
GET /api/writing/portfolio
  → Returns all of the user's WritingSubmissions (final versions only,
    or with an option to view revision history per submission)
  → Sortable/filterable by: date, prompt type, score
  → Score trend chart data (score over time, across all 105 possible
    prompts as the user progresses through cycles)
```

---

## 9. Component Breakdown

| Component | Responsibility |
|---|---|
| **Prompt Screen UI** | Displays prompt, tips, outline, target word count |
| **Writing Editor UI** | Rich text editing, live word count, timer, auto-save |
| **Feedback/Results UI** | Renders multi-agent score breakdown, inline error highlights, revision comparison |
| **Prompt API** | Serves today's prompt from the static bank |
| **Draft Save API** | Lightweight, frequent, non-AI persistence during writing |
| **Submit/Revise API** | Creates/updates WritingSubmission, enqueues feedback pipeline job |
| **Multi-Agent Feedback Pipeline** | LangGraph orchestration of Grammar/Structure/Vocabulary/Coherence/Supervisor (Section 7) |
| **Revision Comparison Service** | Lightweight diff-of-issues step for revision results (Section 7.4) |
| **Content Generation Pipeline** | Offline LangGraph pipeline producing the 105-prompt bank (Section 4) |
| **Writing Portfolio API** | Read-only aggregation over past submissions |

---

## 10. API Design

| Endpoint | Method | AI Call? | Purpose |
|---|---|---|---|
| `/api/writing/prompt/:day` | GET | ❌ No | Fetch today's writing prompt |
| `/api/writing/draft/save` | POST | ❌ No | Frequent auto-save during writing |
| `/api/writing/submit` | POST | ✅ Async (queued) | Submit for full multi-agent feedback |
| `/api/writing/submission/:id` | GET | — | Poll status / retrieve results |
| `/api/writing/submission/:id/revise` | POST | ✅ Async (queued) | Resubmit a revision, re-runs full pipeline |
| `/api/writing/portfolio` | GET | ❌ No | Browse all past submissions |
| `/api/writing/progress` | GET | ❌ No | Aggregate writing plan progress (days completed, avg score) |

---

## 11. Database Schema (Writing Module)

Extends tables already defined in the earlier architecture doc:

```
WRITING_PROMPTS   — see Section 4.3 for full fields (static bank)

WRITING_SUBMISSIONS   (extends the table from TalkFiesta.md)
  ...existing fields (id, user_id, prompt_id, daily_activity_id,
     content, word_count, time_spent_seconds, grammar_score,
     structure_score, vocabulary_score, coherence_score,
     overall_score, grammar_errors, vocabulary_suggestions,
     structure_feedback, ai_feedback, revision_count,
     submitted_at, last_edited_at)...

  status                    ENUM (PROCESSING | COMPLETE | FAILED)  ← NEW
  processing_job_id                                                 ← NEW

WRITING_SUBMISSION_VERSIONS   ← NEW TABLE
  id
  submission_id (FK → WritingSubmissions)
  version_number (1 = original, 2-4 = revisions)
  content
  overall_score
  grammar_score, structure_score, vocabulary_score, coherence_score
  ai_feedback (JSON — full agent report for THIS version)
  fixed_issues (JSON — from Section 7.4, only populated for
                versions 2+)
  created_at

  -- Storing each version separately (rather than overwriting the
  -- submission row on each revision) is what powers both the
  -- portfolio's revision history view AND the "here's what you
  -- fixed" comparison in Flow B
```

---

## 12. Sequence Diagrams

### Flow A — Daily Writing Submission

```
User          Client UI        API           Queue        Worker         Gemini (4 agents)   DB
 │                │              │              │             │                  │            │
 │  Open Day 6      │              │              │             │                  │            │
 │───────────────▶│              │              │             │                  │            │
 │                │  GET prompt     │              │             │                  │            │
 │                │─────────────▶│              │             │                  │            │
 │                │◀─────────────│              │             │                  │            │
 │  Write essay      │              │              │             │                  │            │
 │  (auto-saves         │              │              │             │                  │            │
 │  every 30s)             │              │              │             │                  │            │
 │───────────────▶│  POST draft/save│              │             │                  │            │
 │                │─────────────▶│──────────────────────────────────────────────────────────▶│
 │  Submit for review    │              │              │             │                  │            │
 │───────────────▶│  POST submit      │              │             │                  │            │
 │                │─────────────▶│  Save row,        │             │                  │            │
 │                │              │  enqueue job         │             │                  │            │
 │                │              │───────────────▶│             │                  │            │
 │                │◀─────────────│  submissionId       │             │                  │            │
 │  "Analyzing..."      │              │              │  Job picked │                  │            │
 │◀───────────────│              │              │  up          │                  │            │
 │                │              │              │────────────▶│                  │            │
 │                │              │              │             │  Grammar/Structure/│            │
 │                │              │              │             │  Vocabulary (parallel)│            │
 │                │              │              │             │──────────────────▶│            │
 │                │              │              │             │◀──────────────────│            │
 │                │              │              │             │  Coherence           │            │
 │                │              │              │             │──────────────────▶│            │
 │                │              │              │             │◀──────────────────│            │
 │                │              │              │             │  Supervisor merge      │            │
 │                │              │              │             │──────────────────▶│            │
 │                │              │              │             │◀──────────────────│            │
 │                │              │              │             │  Write results          │            │
 │                │              │              │             │────────────────────────────────▶│
 │                │  Poll status    │              │             │                  │            │
 │                │─────────────▶│──────────────────────────────────────────────────────────▶│
 │                │◀───────────── COMPLETE + 4-category feedback ──────────────────────────────│
 │  See results       │              │              │             │                  │            │
 │◀───────────────│              │              │             │                  │            │
```

### Flow B — Revision

```
User          Client UI        API           Queue        Worker         DB
 │                │              │              │             │              │
 │  Tap "Revise"     │              │              │             │              │
 │───────────────▶│  (editor opens, pre-filled,      │             │              │
 │                │   feedback stays visible)           │             │              │
 │  Edit + resubmit    │              │              │             │              │
 │───────────────▶│  POST submission/:id/revise           │             │              │
 │                │─────────────▶│  Increment revision_count,│             │              │
 │                │              │  enqueue full re-analysis    │             │              │
 │                │              │───────────────▶│             │              │
 │                │              │              │────────────▶│              │
 │                │              │              │             │  Full 4-agent  │
 │                │              │              │             │  pipeline again  │
 │                │              │              │             │  + revision       │
 │                │              │              │             │  comparison step     │
 │                │              │              │             │────────────────▶│
 │                │  Poll status    │              │             │              │
 │                │─────────────▶│──────────────────────────────────────────▶│
 │                │◀───────────── COMPLETE + new score + comparison ──────────│
 │  See "74→86, +12"    │              │              │             │              │
 │  and what was fixed     │              │              │             │              │
 │◀───────────────│              │              │             │              │
```

---

## 13. Infrastructure & Scalability

| Concern | Approach |
|---|---|
| **Job queue** | Same Redis/BullMQ queue used by Speaking and Vocabulary modules — one unified async processing infrastructure across all three modules, not three separate systems |
| **Parallel agent execution** | The 4 feedback agents (Grammar/Structure/Vocabulary/Coherence) should be dispatched concurrently within the worker, not sequentially — this is a code-level concern (Promise.all-equivalent), not infrastructure, but it's the single biggest latency lever in this pipeline |
| **Revision cost control** | The hard 3-revision cap (Section 6, Step 5) is as much an infrastructure/cost guardrail as a UX one — without it, a small number of highly engaged users could generate disproportionate AI spend |
| **Version storage growth** | `WRITING_SUBMISSION_VERSIONS` grows faster than a naive single-row-per-submission design (up to 4x rows per submission with full revisions) — acceptable given writing submission volume is inherently lower than, e.g., vocabulary exercise attempts |
| **Draft auto-save load** | High-frequency, low-cost writes (every 30s while actively writing) — should hit a lightweight, indexed upsert, not trigger any downstream processing |

---

## 14. Failure Modes & Error Handling

| Failure | Handling |
|---|---|
| One of the 4 parallel agents fails/times out | Orchestrator proceeds with the remaining agents' reports; Supervisor notes the missing category in its output rather than blocking the entire submission (partial feedback is better than none, as long as it's clearly labeled) |
| Supervisor Aggregator fails schema validation after retries | Falls back to a simpler merge (average the 4 raw scores, show each agent's raw notes without the polished narrative) rather than showing nothing — per `TalkFiesta-AI-Engineering.md` Section 17, Graceful Degradation |
| User's browser closes mid-writing (before submit) | Auto-saved draft is recoverable — next time they open Day 6, their draft is restored, not lost |
| Revision comparison step fails | Non-critical — the revision's new score and full feedback still display normally; the "what you fixed" comparison simply doesn't show, rather than blocking the whole results screen |
| User hits the 3-revision cap and disagrees with the score | No system fix needed here — this is a product/UX question (e.g., allow marking a submission as "disputed" for later human review), not an error state |

---

## 15. Cost & Performance Considerations

- **Cost per submission:** 4 parallel Gemini 3.5 Flash calls (Grammar/Structure/Vocabulary/Coherence) + 1 Supervisor call — occasionally + 1 Revision Comparison call on resubmissions
- **Cost per revision cycle:** Same as a fresh submission (full pipeline re-run), ×up to 3 — bounded by the hard revision cap
- **Latency target:** Since all 4 agents run in parallel, total pipeline time ≈ slowest single agent + Supervisor merge time — target under 10-12 seconds end-to-end, shown as a proper "Analyzing your writing..." progressive state (per `TalkFiesta-AI-Engineering.md` Section 10 — Latency & Streaming UX), not a blocking spinner
- **Portfolio reads:** Zero AI cost — purely indexed database queries over already-computed submissions

---

## 16. How This Connects to Guardrails

| Guardrail | Where It Plugs Into This Design |
|---|---|
| Structured output validation (AI Engineering doc, Section 2) | The Schema Validation step after the Supervisor Agent (Section 7) |
| LangGraph step/loop limits (AI Engineering doc, Section 4) | Orchestrator Node in Section 7 enforces max agent calls; the 3-revision cap (Section 6) is the module-specific instance of this principle |
| Content moderation for sensitive disclosures (AI Engineering doc, Section 1) | Directly addressed at the content-generation stage (Section 4.1's Human Review Gate flags sensitivity-prone prompts) AND should run on submitted essay text before/alongside the Coherence Agent's pass, in case a user's response to an ordinary prompt surfaces real distress |
| Hallucination guardrails (AI Engineering doc, Section 2) | Grammar Agent uses low temperature — same principle as Speaking Module's Grammar Agent; a confidently wrong grammar correction in writing feedback is just as damaging as in spoken feedback |
| Human review as a guardrail (AI Engineering doc, Section 9) | The Human Review Gate in prompt generation (Section 4.1) |
| Rate limiting (AI Engineering doc, Section 5) | Applies to `/api/writing/submit` and indirectly caps revision spend via the 3-revision limit |
| LangSmith tracing (AI Engineering doc, Section 6) | Wraps every node in the multi-agent feedback pipeline (Section 7) and the content generation pipeline (Section 4) |
| Graceful degradation (AI Engineering doc, Section 17) | Reflected in Section 14's failure modes — partial agent failure degrades gracefully rather than blocking the whole submission |

---

**Project:** TalkFiesta
**Document:** Writing Module — System Design
**Companion to:** `TalkFiesta.md`, `TalkFiesta-AI-Engineering.md`, `TalkFiesta-Speaking-Module-System-Design.md`, `TalkFiesta-Vocabulary-Module-System-Design.md`
**Status:** Ready for implementation planning

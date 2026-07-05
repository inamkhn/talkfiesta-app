# 🎭 TalkFiesta — Multi-Agent Interview Panel System Design

**Companion document to `TalkFiesta.md` (Section 9), `TalkFiesta-AI-Engineering.md`, and the Speaking/Vocabulary/Writing module design docs**

> Covers the full technical system design for the Multi-Agent Interview Panel: domain/level-adaptive question generation, the HR/Technical/Manager agent orchestration, session flow with hand-offs, and the post-session multi-agent feedback report.

---

## Table of Contents

1. Module Scope
2. Key Design Insight — Sequential Multi-Agent, Not Parallel
3. Two Implementation Approaches (MVP vs Advanced)
4. High-Level Architecture
5. Content Generation — Domain Question Bank Per Domain & Level
6. Flow A — Turn-Based Panel Session (MVP)
7. LangGraph Panel Orchestration Design
8. Post-Session Multi-Agent Feedback Report Pipeline
9. Future Evolution — Continuous Live Session with Dynamic Persona Switching
10. Component Breakdown
11. API Design
12. Database Schema
13. Sequence Diagram
14. Infrastructure & Scalability
15. Failure Modes & Error Handling
16. Cost & Performance Considerations
17. How This Connects to Guardrails

---

## 1. Module Scope

Recap from `TalkFiesta.md` Section 9 — this system design implements:

| Sub-Feature                   | Description                                                                                                                                                                                                                      |
| ----------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Setup**                     | User selects Domain, Level, optional Role, optional Company Style, **Interview Mode** (Full Panel vs Single Agent), **Duration** (user-selectable, hard-capped at 30 min)                                                        |
| **Interview Mode**            | **Full Panel** — all 3 agents, sequential rounds with hand-offs (original design) — or **Single Agent** — user picks just HR, Technical, or Manager to interview them solo, for focused practice                                 |
| **3-Agent Panel**             | HR Agent, Technical/Role Agent, Manager Agent — each with fixed responsibilities that adapt content by domain and level                                                                                                          |
| **Session Flow**              | Full Panel: Intro → Round 1 (HR) → hand-off → Round 2 (Technical, with Manager cross-talk) → hand-off → Round 3 (Manager) → Candidate Q&A → Closing. Single Agent: Intro → extended single-agent round → Candidate Q&A → Closing |
| **Duration Control**          | User picks a target length (e.g. 10/15/20/30 min); system enforces a hard 30-minute ceiling regardless of selection, with the Orchestrator wrapping up gracefully as time runs low rather than cutting off abruptly              |
| **Random/Wildcard Questions** | Agents occasionally inject unpredictable "curveball" questions outside the current structured category — mirrors the unpredictability of real interviews rather than feeling like a fixed script                                 |
| **Post-Session Report**       | Individual agent verdicts merged into one Panel Summary with overall Hire verdict, score breakdown, best/weakest answer highlights                                                                                               |

This module sits logically "on top of" the Speaking Module's infrastructure (it's a specialized, more complex speaking exercise type) but has enough unique orchestration complexity — persona hand-offs, domain-adaptive question generation, multi-agent scoring — to warrant its own system design.

---

## 2. Key Design Insight — Sequential Multi-Agent, Not Parallel

This is architecturally different from every other multi-agent pipeline already designed in TalkFiesta:

| Pipeline                                             | Agent Pattern                                                                                                                                                                          |
| ---------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Speaking feedback (Grammar/Vocab/Fluency)            | **Parallel** — all agents run simultaneously on the same static input, merged once at the end                                                                                          |
| Writing feedback (Grammar/Structure/Vocab/Coherence) | **Parallel** — same pattern                                                                                                                                                            |
| **Interview Panel (this doc)**                       | **Sequential, stateful, turn-based** — agents take turns actively driving a multi-round conversation, react to what the user just said, and hand off control to each other mid-session |

**Why this matters for the design:** Parallel agents are stateless relative to each other — each just needs the final transcript. The Interview Panel's agents are **conversational participants**, not analysts — the HR Agent's second question depends on how the user answered the first, and the Technical Agent needs to know what HR already asked so it doesn't repeat ground. This requires genuine **shared session state** carried across every turn, not a one-shot fan-out/fan-in.

This is exactly the problem LangGraph's stateful graph execution is built for, as opposed to a simple parallel `Promise.all` pattern — the graph _is_ the conversation's state machine, not just a pipeline.

---

## 3. Two Implementation Approaches (MVP vs Advanced)

Before designing the flow in detail, one architectural decision needs to be made explicit: **how does the "conversation" with the panel actually happen technically?**

### Approach A — Turn-Based (Recommended for MVP)

Each question is its own discrete round-trip: agent generates a question → converted to speech (TTS) → played to user → user records an answer → answer transcribed → orchestrator decides the next question/agent → repeat. This reuses the **same batch infrastructure already built for Speaking Module Flow A** (record → upload → transcribe → process → respond), just looped multiple times with an orchestrator making decisions between loops.

**Why this is the right MVP choice:**

- Reuses existing, already-designed infrastructure (job queue, transcription pipeline) rather than requiring new real-time infrastructure
- Much simpler to get multi-persona hand-offs right — each "turn" is a clean discrete unit, no need to switch personas _mid-stream_ within a single continuous audio connection
- Easier to debug and trace (LangSmith sees clean discrete steps, not an ambiguous continuous stream)
- The 1-3 second gap between question and answer (TTS generation + playback) is acceptable for an interview simulation — real interviews also have natural pauses

### Approach B — Continuous Live Session with Dynamic Persona Switching (Future Evolution)

Uses **one continuous Gemini Live WebSocket session** (same infrastructure as Speaking Module Flow B) for the entire panel, with the backend orchestrator injecting "director cues" into the live session to switch which persona Gemini is currently voicing, without ever closing the connection. This feels more natural (no dead air between hand-offs) but is meaningfully more complex — detailed in Section 9 as a Phase 2+ evolution, not the initial build.

**This document designs Approach A (Turn-Based) in full detail**, since it's what should actually ship first, and sketches Approach B separately for later.

---

## 4. High-Level Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                              CLIENT (Next.js)                         │
│  ┌────────────────┐  ┌──────────────────┐  ┌───────────────────┐    │
│  │  Panel Setup UI   │  │  Panel Session UI    │  │  Panel Report Screen│   │
│  │  (domain/level/     │  │  (question audio,      │  │  (multi-agent verdict,│   │
│  │   role selection)     │  │   record answer, agent    │  │   score breakdown)     │   │
│  │                      │  │   avatar indicating who's  │  │                        │   │
│  │                      │  │   speaking)                 │  │                        │   │
│  └────────────────┘  └──────────────────┘  └───────────────────┘    │
└──────────────────────────────────────────────────────────────────────┘
         │                         │                          │
         ▼                         ▼                          ▼
┌──────────────────────────────────────────────────────────────────────┐
│                        FASTAPI BACKEND LAYER                          │
│  ┌────────────────┐  ┌──────────────────┐  ┌───────────────────┐    │
│  │ Panel Setup API   │  │ Panel Turn API       │  │ Panel Report API    │   │
│  │ /api/v1/interview- │  │ /api/v1/interview-    │  │ /api/v1/interview-   │   │
│  │ panel/start          │  │ panel/:id/turn          │  │ panel/:id/report       │   │
│  └────────────────┘  └──────────────────┘  └───────────────────┘    │
└──────────────────────────────────────────────────────────────────────┘
         │                         │                          │
         ▼                         ▼                          ▼
┌────────────────────┐  ┌──────────────────────┐   ┌──────────────────┐
│ DOMAIN_QUESTION_BANK   │  │  LANGGRAPH PANEL             │   │  Job Queue           │
│ (static, per domain/     │  │  ORCHESTRATOR                 │   │  (Celery/ARQ) —       │
│  level — Section 5)        │  │  (Section 7 — stateful,          │   │  post-session report   │
│                              │  │   持续 session graph)              │   │  generation only         │
└────────────────────┘  └──────────────────────┘   └──────────────────┘
                                    │
                                    ▼
                    ┌───────────────────────────────┐
                    │   Gemini 3.5 Flash / 3 Pro        │
                    │   (question generation per turn,     │
                    │    reactions, hand-off decisions)       │
                    └───────────────────────────────┘
                                    │
                                    ▼
                    ┌───────────────────────────────┐
                    │   Deepgram (answer transcription)  │
                    │   TTS (question → speech audio)      │
                    └───────────────────────────────┘
```

**Key architectural decision:** Unlike the Speaking Module's real-time conversation (Flow B), the Panel Turn API is a **synchronous-feeling but actually short-lived request/response** call, not a persistent WebSocket. Each turn is its own HTTP round-trip; the "live" feel comes from keeping each individual turn fast (target under 3 seconds for question generation + TTS), not from a continuous stream.

---

## 5. Content Generation — Domain Question Bank Per Domain & Level

Same two-tier philosophy as every other module: **pre-generate and human-review what can be pre-generated, keep only what genuinely needs live adaptation as a live AI call.**

### 5.1 What Gets Pre-Generated vs. Generated Live

| Content                                                                                  | Pre-Generated (Tier 1) or Live?                                                                                                                                                                                                    |
| ---------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| HR behavioral question **scenarios** (the situational framing)                           | Pre-generated per domain — reused, since "conflict with a colleague" scenarios don't need to be unique per user                                                                                                                    |
| Technical/Role domain-specific question **pool**                                         | Pre-generated per (domain × level) — this is the `DomainQuestionBank`                                                                                                                                                              |
| The **specific sequence and phrasing** used in a given session                           | Generated live, grounded in the pre-generated pool (prevents hallucinated, wrong-sounding technical questions — especially important for niche domains like Healthcare, per `TalkFiesta.md` Section 9's original design rationale) |
| Manager big-picture questions                                                            | Pre-generated pool, same as HR                                                                                                                                                                                                     |
| Agent **reactions** to the user's specific answer ("That's a great example, thank you.") | Always live — inherently has to respond to what the user actually said                                                                                                                                                             |

### 5.2 Generation Pipeline (LangGraph, Admin-Triggered)

```
Trigger: "Generate Domain Question Bank — Healthcare, Mid-Level"
                    │
                    ▼
        ┌──────────────────────────┐
        │  Domain Research Agent         │
        │  - For unfamiliar/niche domains,   │
        │    grounds itself via web search       │
        │    on realistic interview questions       │
        │    actually asked in that field (reduces    │
        │    the exact hallucination risk flagged        │
        │    in TalkFiesta.md Section 9)                    │
        └────────────┬─────────────┘
                     ▼
        ┌──────────────────────────┐
        │  Question Bank Writer Agent    │
        │  - Generates 30-50 candidate        │
        │    questions per (domain, level)       │
        │  - Tags each with: sub-category           │
        │    (clinical judgment / ethics / protocol),  │
        │    difficulty within the level, expected         │
        │    answer characteristics                            │
        └────────────┬─────────────┘
                     ▼
        ┌──────────────────────────┐
        │  Domain Expert Review Gate       │
        │  - CRITICAL for niche domains:        │
        │    a generic reviewer can't validate       │
        │    whether a healthcare/legal/finance         │
        │    question is actually realistic —              │
        │    ideally routed to someone with relevant           │
        │    domain familiarity, not just a general             │
        │    content reviewer                                       │
        └────────────┬─────────────┘
                     ▼
        Publish to DOMAIN_QUESTION_BANK, status: PUBLISHED
```

**Why the Domain Expert Review Gate is called out specially:** Every other content-generation pipeline in TalkFiesta (Speaking exercises, vocabulary words, writing prompts) can be reasonably reviewed by one general content reviewer. Interview questions for Healthcare, Legal, or specialized Finance roles genuinely need domain-familiar review — a generic reviewer might approve a technically-worded-but-actually-unrealistic clinical question. This is worth flagging explicitly as a resourcing consideration, not just a process step.

### 5.3 Wildcard Question Bank (Random/Curveball Questions)

A separate, smaller content pool feeding the "Random/Wildcard Questions" feature from Section 1 — classic unpredictable interview questions that don't belong to any one domain's structured category, generated once and reused across all sessions regardless of domain.

```
WILDCARD_QUESTION_BANK   ← NEW TABLE (separate from DOMAIN_QUESTION_BANK,
                            since these apply across ALL domains/levels,
                            not scoped to one)
  id
  question_text            (e.g. "Where do you see yourself in 5 years?",
                             "What's a time you failed and what did you
                             learn?", "If you were an animal, which would
                             you be and why?" — classic curveballs)
  category                  ENUM (CLASSIC_CURVEBALL | BRAIN_TEASER |
                                   SELF_REFLECTION | PRESSURE_TEST)
  suitable_agent_types        JSON array (which agent(s) could plausibly
                               ask this — e.g. brain-teasers fit Technical,
                               self-reflection fits HR)
  min_level                    ENUM (ENTRY|MID|SENIOR — some curveballs,
                                  like deep pressure-test questions, are
                                  only appropriate at Senior level)
  review_status                 ENUM (DRAFT|APPROVED|REJECTED|PUBLISHED)
  generation_batch_id            FK → ContentGenerationBatch
```

Generated via the same pipeline pattern as Section 5.2 (Writer Agent → Quality Checker → Human Review Gate), but as a one-time, domain-agnostic batch rather than something regenerated per domain — this pool is small (perhaps 50-100 questions total) and doesn't need per-cycle regeneration the way domain content does.

### 5.4 Data Model

```
DOMAIN_QUESTION_BANK   (as introduced in TalkFiesta.md Section 9,
                         fully specified here)
  id
  domain              ENUM (SOFTWARE_TECH | BUSINESS_FINANCE |
                             HEALTHCARE | SALES_MARKETING |
                             CUSTOMER_SERVICE | ACADEMIC_RESEARCH |
                             GENERAL)
  level                ENUM (ENTRY | MID | SENIOR)
  agent_type            ENUM (HR | TECHNICAL | MANAGER)
  question_text
  sub_category           (e.g. "clinical judgment", "system design")
  expected_answer_notes    (grounds what a strong answer looks like —
                            used by the post-session scoring, Section 8)
  research_grounded         BOOLEAN (was this validated against
                            real-world sourcing, per Section 5.2)
  review_status              ENUM (DRAFT|APPROVED|REJECTED|PUBLISHED)
  reviewed_by                 user_id (ideally domain-familiar)
  generation_batch_id          FK → ContentGenerationBatch
                                (module_type='INTERVIEW_PANEL')
```

---

## 6. Flow A — Turn-Based Panel Session (MVP)

```
STEP 1 — Setup
  POST /api/v1/interview-panel/start
  Body: { domain, level, role (optional), companyStyle (optional),
          interviewMode: FULL_PANEL | SINGLE_AGENT,
          selectedAgentType (required only if SINGLE_AGENT):
            HR | TECHNICAL | MANAGER,
          targetDurationMinutes: 10 | 15 | 20 | 30 (user-selected,
            defaults to 15 if not specified) }
  → Validates targetDurationMinutes <= 30 (hard ceiling — see
    Step 4a below; a value above 30 is rejected/clamped, never
    silently allowed through)
  → Creates InterviewPanelSession row (status: ACTIVE)
  → LangGraph Orchestrator initializes session state:
    { domain, level, role, companyStyle, interviewMode,
      selectedAgentType, targetDurationMinutes,
      sessionStartTime: NOW(), currentRound: 1,
      currentAgent: (HR if FULL_PANEL, else selectedAgentType),
      topicsAsked: [], transcript: [], wildcardsUsed: 0 }
  → Returns sessionId + first question (opening question from
    whichever agent is active)

STEP 2 — Present Question
  Client receives question text + TTS audio URL
  UI shows which agent is "speaking" (HR/Technical/Manager avatar)
  If SINGLE_AGENT mode, UI simply shows that one agent throughout —
  no hand-off indicator needed
  A visible session timer counts down from targetDurationMinutes
  Audio plays automatically

STEP 3 — User Records Answer
  Standard recording UI (same component as Speaking Module Flow A)
  User records, submits

STEP 4 — Submit Turn
  POST /api/v1/interview-panel/:id/turn
  Body: { audioFile }
  → Transcribes via Deepgram
  → Passes transcript + full session state into the LangGraph
    Orchestrator (Section 7)

  STEP 4a — Duration Check (runs BEFORE question generation)
    Orchestrator computes elapsedMinutes = NOW() - sessionStartTime
    IF elapsedMinutes >= 30 (hard ceiling, regardless of what the
      user originally selected):
        → Force-route to Closing, skip any remaining rounds
        → This is a non-negotiable server-side cap, not just a
          client-side timer — enforced identically to the Real-Time
          Conversation session timeout guardrail in
          `TalkFiesta-AI-Engineering.md` Section 3
    ELSE IF elapsedMinutes >= targetDurationMinutes × 0.85 (i.e.
      approaching the user's OWN selected target):
        → Orchestrator begins wrapping up gracefully — skips any
          planned follow-up questions in the current round and
          routes toward Hand-Off/Closing rather than starting a
          fresh round, so the session ends on a natural beat
          instead of cutting off mid-question
    ELSE: proceed normally to Step 4b

  STEP 4b — Random/Wildcard Question Check
    Before generating the next STRUCTURED question, the Orchestrator
    rolls a small probability check (configurable, e.g. ~15% chance
    per round, capped at 2 wildcards per session via wildcardsUsed)
    IF triggered:
        → Pulls one question from WILDCARD_QUESTION_BANK filtered by
          suitable_agent_types matching the current agent and
          min_level <= session level
        → The current agent asks this instead of (or occasionally in
          addition to) the next structured domain question
        → Increments wildcardsUsed in session state
    This is what delivers the "AI can ask random interview questions"
    behavior — genuine unpredictability layered on top of the
    structured, level/domain-calibrated core questions, not a
    replacement for them

  STEP 4c — Normal Orchestrator Decision (as originally designed)
    a) Does the current agent react first? (usually yes — brief
       acknowledgment)
    b) Is this round complete, or does the current agent ask a
       follow-up? (Technical Agent may follow up 1-2x on a thin
       answer before moving on)
    c) Should the round hand off to the next agent? — ONLY relevant
       in FULL_PANEL mode; in SINGLE_AGENT mode, "hand-off" instead
       means moving to a new sub-topic within the same agent's
       extended round, since there's no other agent to hand off to
  → Updates session state (topicsAsked, transcript, currentRound,
    currentAgent, wildcardsUsed)
  → Generates the next question (or hand-off line, or closing)
  → Returns: reaction text (if any) + next question + TTS audio
    + updated round/agent info + remaining time (for UI display)

STEP 5 — Repeat Steps 2-4
  FULL_PANEL: loop continues through Round 1 (HR) → Round 2
    (Technical, with occasional Manager cross-talk injected by the
    Orchestrator) → Round 3 (Manager) → Candidate Q&A
  SINGLE_AGENT: loop continues with the one selected agent asking a
    longer sequence of questions within its own domain (e.g. a
    Technical-only session goes deeper on technical questions than
    the Technical round would get within a Full Panel session) →
    Candidate Q&A
  Either mode ends early via the Step 4a duration check if time
  runs out before the natural round structure completes

STEP 6 — Candidate Q&A Turn
  Orchestrator prompts: "Do you have any questions for us?"
  User's question is recorded/transcribed
  The active agent (or HR by default in Full Panel mode) gives an
  in-character answer — this turn is NOT scored, purely for
  realism/practice value
  (Skipped entirely if the 30-minute hard ceiling is reached before
   this point — Closing takes priority over Q&A when time is tight)

STEP 7 — Closing
  Active agent delivers a closing line
  Session marked: status = ENDED
  Full transcript finalized, including actualDurationMinutes and
  whether the session ended naturally, via the user's own target,
  or via the hard 30-minute ceiling (stored for later analytics —
  see Section 12)

STEP 8 — Trigger Post-Session Report
  Enqueues job to the SAME job queue used by other modules
  → Runs the Post-Session Multi-Agent Feedback Report pipeline
    (Section 8) — this is a PARALLEL multi-agent step, distinct
    from the sequential live orchestration that just happened
  → In SINGLE_AGENT mode, only the selected agent's Verdict Agent
    runs (no need to generate HR/Technical/Manager verdicts for
    agents that were never part of the session) — the Panel Summary
    Agent still runs to produce the final formatted report, just
    merging one verdict instead of three
  → Client polls for report readiness (same polling pattern as
    every other module)
```

---

## 7. LangGraph Panel Orchestration Design

This is the stateful graph that drives Flow A, Steps 1-7. Unlike the parallel feedback graphs in Speaking/Writing, this graph has **loops and conditional routing** — it's a genuine state machine, not a fan-out/fan-in.

```
                    ┌─────────────────────┐
                    │   START — Session       │
                    │   initialized              │
                    └──────────┬───────────┘
                               ▼
                    ┌─────────────────────┐
                    │   Orchestrator Node      │◀─────────────┐
                    │  Reads: session state,     │              │
                    │  current round, current       │              │
                    │  agent, topics asked,           │              │
                    │  transcript so far                │              │
                    │  Decides: which node to route       │              │
                    │  to next (conditional edge)            │              │
                    └──────────┬───────────┘              │
                               ▼                            │
                    ┌─────────────────────┐                 │
                    │   Duration Guard Node       │                 │
                    │   (Step 4a — Section 6)         │                 │
                    │  elapsed >= 30min? → force            │                 │
                    │  route to Closing                       │                 │
                    │  elapsed >= 85% of target? → wrap         │                 │
                    │  up gracefully, skip to Hand-Off/Closing    │                 │
                    │  else → proceed normally                        │                 │
                    └──────────┬───────────┘                 │
                               ▼ (time OK)                    │
                    ┌─────────────────────┐                 │
                    │   Wildcard Check Node        │                 │
                    │   (Step 4b — Section 6)         │                 │
                    │  Small probability roll →              │                 │
                    │  pull from WILDCARD_QUESTION_BANK         │                 │
                    │  instead of structured question,            │                 │
                    │  capped at 2/session                            │                 │
                    └──────────┬───────────┘                 │
         ┌───────────────────┬─┴─┬───────────────────┐       │
         ▼                   ▼   ▼                   ▼       │
┌──────────────┐  ┌──────────────┐  ┌──────────────┐        │
│ HR Agent Node  │  │ Technical Agent│  │ Manager Agent  │        │
│                 │  │ Node            │  │ Node            │        │
│ Active: Round 1  │  │ Active: Round 2  │  │ Active: Round 3  │        │
│ + Q&A closing      │  │ Reads domain +     │  │ Reads level for    │        │
│ Generates behavioral │  │ level → queries      │  │ big-picture question │        │
│ question grounded in   │  │ DOMAIN_QUESTION_BANK   │  │ style (entry:            │        │
│ scenario category         │  │ for this (domain,        │  │ initiative, senior:         │        │
│ (or SINGLE_AGENT's only)     │  │ level, TECHNICAL) —         │  │ strategic thinking)            │        │
│                              │  │ or the Wildcard Bank            │  │                                   │        │
│                                │  │ if Wildcard Check fired            │  │                                     │        │
└────────┬─────────┘  └────────┬─────────┘  └────────┬─────────┘        │
         │                     │                     │                  │
         └─────────────────────┼─────────────────────┘                  │
                               ▼                                        │
                    ┌─────────────────────┐                             │
                    │   Round Complete?          │                             │
                    │   (conditional check)          │──── NO ─────────────────┘
                    │   Has this agent asked           │    (loop back to
                    │   enough / has user answered        │     Orchestrator for
                    │   sufficiently for this round           │     next turn in
                    │   to move on?)                              │     same round)
                    └──────────┬───────────┘
                              YES
                               ▼
                    ┌─────────────────────┐
                    │   Hand-Off Node             │
                    │   FULL_PANEL: generates the       │
                    │   transition line ("I'll pass        │
                    │   it over to..."), advances              │
                    │   currentAgent                              │
                    │   SINGLE_AGENT: no persona change,            │
                    │   just moves to a new sub-topic                 │
                    │   within the same agent's round                   │
                    └──────────┬───────────┘
                               │
                    (loops back to Orchestrator until
                     all rounds + Q&A + closing done,
                     OR Duration Guard forces early exit)
                               ▼
                    ┌─────────────────────┐
                    │   END — Session ended,     │
                    │   status = ENDED,              │
                    │   endReason recorded               │
                    │   (NATURAL|USER_TARGET_REACHED|      │
                    │    HARD_CEILING_REACHED),               │
                    │   post-session job enqueued                │
                    └─────────────────────┘
```

### 7.1 Why the Orchestrator Node Is Separate From the Persona Agent Nodes

The Orchestrator makes **routing decisions** (which agent's turn is it, is the round done, time to hand off) — it does not generate interview content itself. The three persona nodes generate content **only** when it's their turn. This separation means:

- Adding a 4th agent (e.g., a future "Peer Interviewer") is a pure graph addition — one new node, one new routing case — without touching the other three agents' logic
- The Orchestrator's routing logic can be tested and reasoned about independently of what any individual agent actually says

### 7.2 Cross-Talk Design (Manager Jumping In During Round 2)

The occasional Manager cross-talk mentioned in `TalkFiesta.md` Section 9 ("Building on what Sarah asked...") is modeled as a **low-probability conditional edge** from the Round Complete check — after most Technical Agent turns, the Orchestrator has a small chance to route to a brief Manager Agent interjection node before returning control to the Technical Agent. This is deliberately kept infrequent (not every turn) to feel like a natural, occasional interjection rather than a scripted pattern.

### 7.3 Single Agent Mode Routing

When `interviewMode = SINGLE_AGENT`, the graph structure doesn't change — the same nodes exist — but the Orchestrator's routing simplifies:

- Only one of the three persona nodes is ever reachable for the whole session (the other two are never routed to)
- The "Round Complete?" check still fires (to move between sub-topics), but the Hand-Off Node's behavior changes from "switch persona" to "same persona, new sub-topic" — no transition line like "I'll pass it over to..." is needed, just a natural topic-change cue from the same interviewer
- This effectively gives the user a longer, deeper session with one interviewer type — useful for someone specifically wanting to drill Technical questions without spending time on HR/Manager rounds, or vice versa

### 7.4 Shared Session State Schema

```python
PanelSessionState = {
    "session_id": str,
    "domain": str,
    "level": str,
    "role": str | None,
    "company_style": str | None,
    "interview_mode": str,          # FULL_PANEL | SINGLE_AGENT
    "selected_agent_type": str | None,  # set only if SINGLE_AGENT
    "target_duration_minutes": int,     # user-selected, <= 30
    "session_start_time": datetime,
    "current_round": int,          # 1, 2, 3, or "qa", or "closing"
    "current_agent": str,          # HR | TECHNICAL | MANAGER
    "topics_asked": list[str],     # prevents repeat questions
    "transcript": list[dict],      # [{speaker, text, timestamp}, ...]
    "questions_asked_this_round": int,
    "round_start_time": datetime,
    "wildcards_used": int,         # capped at 2 per session
    "end_reason": str | None,      # NATURAL | USER_TARGET_REACHED |
                                    # HARD_CEILING_REACHED — set on exit
}
```

This state object is what gets passed through every node in the graph and persisted to the `InterviewPanelSession` row between turns (since each turn is its own HTTP request — the graph doesn't stay "alive" in memory between calls, it's rehydrated from stored state each time).

---

## 8. Post-Session Multi-Agent Feedback Report Pipeline

This is a **separate, parallel-pattern** pipeline from the live orchestration graph — it runs once, after the session ends, on the complete transcript.

```
                    ┌─────────────────────┐
                    │   Input: full transcript │
                    │   + domain/level/role       │
                    │   config                        │
                    └──────────┬───────────┘
                               ▼
                    ┌─────────────────────┐
                    │   Orchestrator Node       │
                    └──────────┬───────────┘
         ┌───────────────────┬─┴─┬───────────────────┐
         ▼                   ▼   ▼                   ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│ HR Verdict     │  │ Technical      │  │ Manager        │
│ Agent           │  │ Verdict Agent   │  │ Verdict Agent   │
│ Scores: culture  │  │ Scores: domain    │  │ Scores: strategic │
│ fit, communication │  │ knowledge accuracy,│  │ thinking, leadership│
│ style, behavioral    │  │ depth of expertise    │  │ potential (weighted  │
│ answer quality          │  │ shown, grounded          │  │ more heavily for       │
│                            │  │ against expected_          │  │ Senior level)             │
│                              │  │ answer_notes from             │  │                             │
│                                │  │ DOMAIN_QUESTION_BANK               │  │                             │
└────────┬─────────┘  └────────┬─────────┘  └────────┬─────────┘
         │                     │                     │
         └─────────────────────┼─────────────────────┘
                               ▼
                    ┌─────────────────────┐
                    │   Panel Summary Agent      │
                    │   (Supervisor)                 │
                    │  - Merges all 3 verdicts           │
                    │  - Computes overall verdict:            │
                    │    Strong Hire/Hire/Maybe/No Hire            │
                    │  - Score breakdown: Domain Knowledge,             │
                    │    Communication, Confidence, Culture Fit             │
                    │  - Identifies best answer + weakest answer                │
                    │    with suggested better response                            │
                    │  - Writes "what a real interviewer at this level               │
                    │    would expect" calibration note                                 │
                    └──────────┬───────────┘
                               ▼
                    ┌─────────────────────┐
                    │   Schema Validation         │
                    │   → retry up to 3x               │
                    └──────────┬───────────┘
                               ▼
                    ┌─────────────────────┐
                    │   Saved to InterviewPanel-  │
                    │   Session.overall_verdict +     │
                    │   PanelAgentFeedback rows          │
                    └─────────────────────┘
```

**Why this reuses the parallel-agent pattern (like Speaking/Writing feedback) rather than the sequential pattern (like the live session):** By the time this runs, the conversation is _over_ — there's no more turn-taking to manage. Each verdict agent just needs to read the same static transcript and produce its independent judgment, which is exactly the case where parallel execution is correct and faster than sequential.

**Single Agent Mode adjustment:** The Orchestrator Node in this pipeline checks `interview_mode` before fanning out — if `SINGLE_AGENT`, it routes to only the one relevant Verdict Agent (e.g., only the Technical Verdict Agent runs for a Technical-only session) rather than invoking all three. The Panel Summary Agent still runs afterward to produce the final formatted report and overall verdict, but merges one verdict instead of three — this keeps cost proportional to what actually happened in the session rather than always paying for three verdict calls regardless of mode.

---

## 9. Future Evolution — Continuous Live Session with Dynamic Persona Switching

Sketched here as a Phase 2+ direction, not designed to full implementation detail (per Section 3's recommendation to ship Approach A first).

**Core idea:** One continuous Gemini Live WebSocket session for the whole panel (same ephemeral-token pattern as Speaking Module Flow B). Instead of separate HTTP turns, the backend LangGraph Orchestrator runs **alongside** the live session and injects text-based "director cues" as system context updates mid-session — e.g., after Round 1 completes, the Orchestrator sends a cue telling Gemini "You are now the Technical Interviewer for a [domain] [level] role; the candidate's previous answers were: [summary]." Gemini then continues the _same_ audio connection but shifts persona and question focus based on the injected cue, eliminating the dead-air gap between HR and Technical rounds that Approach A's discrete HTTP turns introduce.

**Why this is meaningfully harder than Speaking Module Flow B:** Flow B's real-time conversation has ONE persona for the whole session, set once at connection time. This evolution requires **changing** persona and context _mid-session_, which means carefully managing what Gemini "remembers" as the persona shifts (should the Technical Agent persona reference what HR discussed, or does that break the illusion of a "different person" now speaking?) — a genuinely open design question worth prototyping separately before committing to it, rather than solving speculatively here.

---

## 10. Component Breakdown

| Component                        | Responsibility                                                                       |
| -------------------------------- | ------------------------------------------------------------------------------------ |
| **Panel Setup UI**               | Domain/level/role/company style selection                                            |
| **Panel Session UI**             | Question audio playback, recording, agent avatar/identity display                    |
| **Panel Report UI**              | Multi-agent verdict display, score breakdown, transcript with labeled speakers       |
| **Panel Setup API**              | Initializes session + state, returns first question                                  |
| **Panel Turn API**               | Core loop endpoint — transcribes answer, runs Orchestrator, returns next question    |
| **LangGraph Panel Orchestrator** | Stateful graph managing rounds, hand-offs, cross-talk (Section 7)                    |
| **Domain Question Bank**         | Static, human-reviewed content grounding the Technical Agent (Section 5)             |
| **Post-Session Report Pipeline** | Parallel multi-agent verdict generation, runs once per completed session (Section 8) |
| **TTS Service**                  | Converts each generated question/reaction to speech audio                            |

---

## 11. API Design

| Endpoint                             | Method | Purpose                                                                                                                                                                                                                                            |
| ------------------------------------ | ------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `/api/v1/interview-panel/start`      | POST   | Create session — body includes `domain`, `level`, `role`, `companyStyle`, `interviewMode` (FULL_PANEL/SINGLE_AGENT), `selectedAgentType` (if SINGLE_AGENT), `targetDurationMinutes` (≤ 30). Initializes orchestrator state, returns first question |
| `/api/v1/interview-panel/:id/turn`   | POST   | Submit recorded answer, get next question/reaction/hand-off — response includes remaining time and whether a wildcard question was used                                                                                                            |
| `/api/v1/interview-panel/:id/end`    | POST   | Explicitly end session early (user can quit mid-panel)                                                                                                                                                                                             |
| `/api/v1/interview-panel/:id/report` | GET    | Poll/retrieve the post-session multi-agent report                                                                                                                                                                                                  |
| `/api/v1/interview-panel/domains`    | GET    | List available domains/levels for the setup screen                                                                                                                                                                                                 |
| `/api/v1/interview-panel/history`    | GET    | List a user's past panel sessions (their own mini-portfolio) — filterable by interview mode/agent type                                                                                                                                             |

---

## 12. Database Schema

Extends the tables introduced in `TalkFiesta.md` Section 9:

```
INTERVIEW_PANEL_SESSION
  id, user_id, domain, level, role, company_style
  interview_mode          ENUM (FULL_PANEL | SINGLE_AGENT)      ← NEW
  selected_agent_type      ENUM (HR|TECHNICAL|MANAGER, nullable,   ← NEW
                            set only if SINGLE_AGENT)
  target_duration_minutes   INT (user-selected, <= 30)             ← NEW
  actual_duration_minutes    INT (computed at session end)           ← NEW
  end_reason                  ENUM (NATURAL|USER_TARGET_REACHED|      ← NEW
                               HARD_CEILING_REACHED)
  wildcards_used                INT (0-2, for analytics on how           ← NEW
                                 often the feature actually fires)
  status              ENUM (ACTIVE | ENDED | ABANDONED)
  overall_verdict      ENUM (STRONG_HIRE|HIRE|MAYBE|NO_HIRE, nullable
                        until report completes)
  session_state         JSON (the PanelSessionState object, Section 7.4
                         — persisted/rehydrated between turns)
  started_at, ended_at

PANEL_ROUND
  id, session_id (FK), agent_type (HR|TECHNICAL|MANAGER),
  round_number, questions_asked (JSON array)

PANEL_RESPONSE
  id, round_id (FK), question_text, user_answer_transcript,
  agent_reaction_text, audio_url, submitted_at,
  is_wildcard            BOOLEAN (was this question pulled from       ← NEW
                          WILDCARD_QUESTION_BANK rather than the
                          structured DOMAIN_QUESTION_BANK)

PANEL_AGENT_FEEDBACK   ← NEW TABLE (post-session report, Section 8)
  id
  session_id (FK → InterviewPanelSession)
  agent_type            ENUM (HR|TECHNICAL|MANAGER|SUMMARY)
  verdict_notes          TEXT
  score_contribution       JSON (this agent's specific scores)
  best_answer_reference     (FK → PanelResponse, nullable)
  weakest_answer_reference   (FK → PanelResponse, nullable)
  created_at

DOMAIN_QUESTION_BANK  — see Section 5.4 for full fields
WILDCARD_QUESTION_BANK  — see Section 5.3 for full fields
```

**Why `target_duration_minutes` and `actual_duration_minutes` are stored separately:** This lets analytics later answer questions like "do users who pick 30 minutes actually tend to hit the hard ceiling, or wrap up naturally early?" — useful signal for whether the default duration options offered at setup are well-calibrated to how long sessions actually take in practice.

---

## 13. Sequence Diagram

### Flow A — Turn-Based Panel Session (abbreviated, showing one round transition)

```
User        Client UI       API              LangGraph Orchestrator      DB
 │              │              │                     │                    │
 │  Start panel   │              │                     │                    │
 │─────────────▶│              │                     │                    │
 │              │  POST /start    │                     │                    │
 │              │─────────────▶│  Initialize session state│                    │
 │              │              │─────────────────────▶│                    │
 │              │              │                     │  Save session row     │
 │              │              │                     │───────────────────▶│
 │              │◀─────────────│  HR opening question    │                    │
 │  Hear question  │              │                     │                    │
 │◀─────────────│              │                     │                    │
 │  Record answer   │              │                     │                    │
 │─────────────▶│  POST /turn        │                     │                    │
 │              │─────────────▶│  Transcribe + route to     │                    │
 │              │              │  HR Agent Node                │                    │
 │              │              │─────────────────────▶│                    │
 │              │              │                     │  HR reaction +          │
 │              │              │                     │  next question OR         │
 │              │              │                     │  "round complete" →         │
 │              │              │                     │  Hand-Off Node                │
 │              │              │◀─────────────────────│                    │
 │              │◀─────────────│  Reaction + hand-off line   │                    │
 │              │              │  + Technical Agent's first     │  Update session_state │
 │              │              │  question                         │  (currentAgent=       │
 │              │              │                                     │  TECHNICAL,             │
 │              │              │                                     │  round=2)                 │
 │              │              │                     │───────────────────▶│
 │  Hear hand-off +  │              │                     │                    │
 │  new question        │              │                     │                    │
 │◀─────────────│              │                     │                    │
 │  ... loop continues through all rounds ...                                    │
 │  Session ends       │              │                     │                    │
 │              │              │  Enqueue post-session       │                    │
 │              │              │  report job (Section 8)        │                    │
 │              │              │────────────────────────────────────────────▶│
 │              │  Poll report      │                     │                    │
 │              │─────────────▶│──────────────────────────────────────────▶│
 │              │◀───────────── COMPLETE + multi-agent report ──────────────│
 │  See verdict        │              │                     │                    │
 │◀─────────────│              │                     │                    │
```

---

## 14. Infrastructure & Scalability

| Concern                         | Approach                                                                                                                                                                                                                                                                                                                   |
| ------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Session state persistence**   | Since each turn is a discrete HTTP request (not a long-lived connection), `session_state` must be fully persisted to the DB after every turn and rehydrated at the start of the next — the LangGraph Orchestrator is effectively stateless between requests, with the DB as its memory                                     |
| **Turn latency**                | Each turn involves: transcription + Orchestrator routing + question generation + TTS — target under 3-4 seconds total; this is the module's most latency-sensitive path since users are actively waiting mid-conversation, unlike Speaking/Writing's async "analyze later" pattern                                         |
| **Duration enforcement**        | The 30-minute hard ceiling (Section 6, Step 4a) must be enforced **server-side**, not just as a client-side countdown UI — a client could theoretically ignore its own timer, so the Duration Guard Node checking `elapsed >= 30min` on every single turn is the actual source of truth, not a decorative frontend feature |
| **Domain Question Bank size**   | Small, static table (grows slowly, only when new domains/levels are added) — no special scaling concern                                                                                                                                                                                                                    |
| **Wildcard Question Bank size** | Even smaller and more static than the Domain bank — generated once, rarely needs regeneration since curveball questions don't go stale the way domain-specific technical content might                                                                                                                                     |
| **Post-session report**         | Reuses the same job queue as every other module's async feedback generation                                                                                                                                                                                                                                                |
| **Abandoned sessions**          | Sessions left inactive beyond a timeout window should auto-transition to `ABANDONED` status (not `ENDED`) — distinguishing "user quit" from "user finished" matters for both analytics and whether a report should even be generated                                                                                       |

---

## 15. Failure Modes & Error Handling

| Failure                                                                                                     | Handling                                                                                                                                                                                                                                                         |
| ----------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Orchestrator fails to decide next step (routing logic error)                                                | Falls back to a safe default (advance to next scripted round) rather than getting stuck — the graph should never have a state with no valid outgoing edge                                                                                                        |
| Technical Agent's generated question doesn't match `DomainQuestionBank` grounding (drifts off-topic)        | A lightweight sanity-check step (similar to the Speaking Exercise Content Generation's Quality Checker) validates the generated question is reasonably grounded before it's sent to TTS/the user                                                                 |
| A single turn's processing takes long enough that the 30-minute ceiling is crossed mid-turn                 | The Duration Guard check (Section 6, Step 4a) runs at the START of the next turn, so an in-flight turn is always allowed to complete naturally — the user is never cut off mid-question or mid-answer, only prevented from starting a NEW round after time is up |
| `WILDCARD_QUESTION_BANK` has no matching question for the current `suitable_agent_types`/`min_level` filter | Wildcard Check Node simply skips this round's wildcard roll and proceeds to a normal structured question — this is a soft feature, never a blocking dependency                                                                                                   |
| TTS generation fails for a question                                                                         | Falls back to displaying the question as text only, session continues rather than blocking                                                                                                                                                                       |
| User disconnects mid-session                                                                                | Session auto-transitions to `ABANDONED` after a timeout; no post-session report is generated for abandoned sessions (nothing meaningful to score)                                                                                                                |
| Post-session report's parallel verdict agents disagree significantly                                        | Panel Summary Agent (Supervisor) is the designated tie-breaker — same escalation-to-Gemini-3-Pro pattern used in Writing Module's Aggregator when agent reports conflict                                                                                         |

---

## 16. Cost & Performance Considerations

- **Cost per session:** Roughly 8-12 live turn-generation calls (Gemini 3.5 Flash) + TTS per turn + Deepgram transcription per turn + up to 4 post-session verdict calls (HR/Technical/Manager/Summary in FULL_PANEL mode) — meaningfully more expensive than a single Speaking Module submission, since it's effectively multiple conversational exchanges plus a full multi-agent report
- **Single Agent Mode is meaningfully cheaper:** Only 1 verdict call instead of 3 post-session, and typically fewer total turns since there's no hand-off overhead between personas — worth surfacing to users as a lighter-weight option, not just a "focused practice" framing
- **The 30-minute hard ceiling is as much a cost guardrail as a UX one:** Without it, a session could theoretically run indefinitely if a user kept answering thoughtfully forever — the ceiling caps worst-case per-session cost predictably, independent of user behavior
- **Why this justifies rate limiting more aggressively than other modules:** Given the higher per-session cost, daily/weekly caps on Interview Panel sessions specifically (separate from general Speaking Module limits) are worth considering as their own guardrail tier
- **Latency target:** Per-turn response under 3-4 seconds (Section 14); session length now user-controlled (10-30 min) rather than fixed, with the Duration Guard ensuring actual time spent never exceeds what was promised — either the user's own target or the 30-minute absolute ceiling

---

## 17. How This Connects to Guardrails

| Guardrail                                                                                                        | Where It Plugs Into This Design                                                                                                                                                                                                                                     |
| ---------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Session timeouts (AI Engineering doc, Section 3 — originally scoped to Speaking Module's Real-Time Conversation) | Directly reused here: the Duration Guard Node's 30-minute hard ceiling (Section 6, Step 4a) is this exact same guardrail principle applied to the Interview Panel — session length caps prevent runaway sessions and cost regardless of which module they protect   |
| Multi-agent step/loop limits (AI Engineering doc, Section 4)                                                     | The Orchestrator Node (Section 7) must enforce a hard max on total turns/rounds — without this, a stuck "round complete?" check could loop indefinitely; the Duration Guard is a time-based backstop to this same concern                                           |
| Handoff validation (AI Engineering doc, Section 4)                                                               | Every hand-off between persona agents validates the updated `session_state` schema before the next node reads it                                                                                                                                                    |
| Grounding (AI Engineering doc, Section 12)                                                                       | The `DomainQuestionBank` and `WildcardQuestionBank` are both this principle applied to interview questions — prevents agents from hallucinating unrealistic questions, whether structured or random                                                                 |
| Bias & fairness (AI Engineering doc, Section 2)                                                                  | Directly named in `TalkFiesta.md` Section 9's original design as a periodic audit requirement — panel verdicts must never be influenced by accent/dialect, only answer content                                                                                      |
| Content moderation (AI Engineering doc, Section 1)                                                               | Applies to user answers before they're processed by any persona agent                                                                                                                                                                                               |
| Rate limiting (AI Engineering doc, Section 5)                                                                    | Given this module's higher cost per session (Section 16), warrants a dedicated, possibly stricter limit than other Speaking Module exercise types — with Single Agent Mode sessions reasonably counted less heavily than Full Panel sessions given their lower cost |
| Human review as a guardrail (AI Engineering doc, Section 9)                                                      | The Domain Expert Review Gate (Section 5.2) — arguably the highest-stakes content review in the entire app, since a bad technical question in a niche domain damages trust immediately and visibly                                                                  |
| LangSmith tracing (AI Engineering doc, Section 6)                                                                | Wraps every node in both the live Orchestrator graph (Section 7) and the post-session report graph (Section 8) — especially valuable here given the sequential graph's complexity relative to the simpler parallel graphs elsewhere                                 |

---

**Project:** TalkFiesta
**Document:** Multi-Agent Interview Panel — System Design
**Companion to:** `TalkFiesta.md` (Section 9), `TalkFiesta-AI-Engineering.md`, `TalkFiesta-Speaking-Module-System-Design.md`, `TalkFiesta-Vocabulary-Module-System-Design.md`, `TalkFiesta-Writing-Module-System-Design.md`
**Status:** Ready for implementation planning (Approach A / MVP scope)

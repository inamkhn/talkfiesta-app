# 🎉 TalkFiesta

**AI-Powered English Learning App — Speaking, Vocabulary & Writing**

> "Where language learning becomes a celebration."

---

## 1. What is TalkFiesta?

TalkFiesta is a personal AI-powered web app to improve three core English skills:

- 🎤 **Speaking** — including public speaking, conversation fluency, and confidence
- 📚 **Vocabulary** — learning and retaining new words through context and practice
- ✍️ **Writing** — essays, emails, structured writing with AI correction

Each skill is trained through a **21-day structured plan**, powered by AI feedback (via Google Gemini 3.5 Flash / Gemini 3 Pro, plus Gemini 3.1 Flash Live for real-time voice), and progress analytics — so you always know exactly what to practice and how you're improving.

---

## 2. Core Idea

| Pillar | Goal | Format |
|---|---|---|
| 🎤 Speaking | Fluency, pronunciation, confidence, public speaking | Daily recorded exercises + AI feedback |
| 📚 Vocabulary | Learn & retain new words | 10 words/day + spaced repetition + exercises |
| ✍️ Writing | Grammar, structure, clarity | Daily prompts + AI-graded feedback |

All three run in parallel — you can do one, two, or all three per day, tracked separately with their own 21-day progress bar.

---

## 3. Speaking Module (Including Public Speaking)

### Exercise Types
- **Conversational Speaking** — daily topics (family, opinions, storytelling)
- **Public Speaking Practice** — structured short speeches (1–3 min) on a given topic, practiced like a mini TED talk
- **Mock Interviews** — job interview style Q&A with AI interviewer
- **Impromptu Speaking** — random topic, 30-second prep, then speak (builds quick thinking, common in Toastmasters-style training)

### How It Works
1. User selects exercise type (Conversation / Public Speaking / Interview / Impromptu)
2. Gets a topic + instructions + target duration
3. Records themselves (mic button, waveform visual, timer)
4. Audio is transcribed (Speech-to-Text)
5. AI analyzes and returns:
   - **Fluency Score** — pace, pauses, filler words ("um", "uh", "like")
   - **Grammar Score** — sentence structure, tense errors
   - **Vocabulary Score** — word variety and appropriateness
   - **Delivery/Confidence Score** *(for public speaking)* — pacing, clarity, structure (intro-body-conclusion)
   - Full transcript with highlighted errors
   - Specific, actionable tips

### Public Speaking Specific Features
- Speech structure checklist (Hook → Main Points → Conclusion)
- Filler word tracker (visual count of "um," "uh," "like," "you know")
- Pace meter (words per minute — too fast / too slow / just right)
- "Speech of the Day" prompts on real public speaking topics (persuasive, informative, storytelling)

### 🔴 Real-Time AI Conversation (Live Voice Chat)

A live, back-and-forth spoken conversation with an AI partner on a chosen topic — closer to talking with a real person than the "record → submit → wait for feedback" flow used elsewhere in the app.

**How It Works**
1. User picks a **topic** (or a category → random topic): daily life, business, travel, debate/opinion, interview simulation, custom topic (user types anything)
2. User picks a **difficulty/persona** — e.g., Friendly Tutor (patient, simple language), Native Peer (natural speed, casual), Examiner (formal, IELTS/TOEFL style), Interviewer (professional, job-style questions)
3. User taps **"Start Conversation"** → mic opens automatically
4. AI greets the user and asks an opening question about the topic
5. User speaks naturally — no need to hit record/stop each turn
6. AI **listens, responds by voice in real time**, and keeps the conversation going — follow-up questions, reactions, gentle redirects if user goes off-topic
7. Conversation continues for a set duration (e.g., 3–5 minutes) or a set number of turns
8. User can end anytime with **"End Conversation"**

**During the Conversation (Live UI)**
- Live waveform / voice-activity indicator (shows when AI is "listening" vs "speaking")
- Rolling live transcript (both sides) appearing as subtitles
- Small on-screen prompt hints if the user pauses too long ("Try describing a specific example…")
- Timer showing elapsed time

**After the Conversation — Feedback Report**
- Full transcript with both speakers labeled (You / AI)
- Same scoring categories as other speaking exercises: Fluency, Grammar, Vocabulary, Pronunciation, Confidence
- Turn-by-turn grammar corrections (inline on the transcript)
- Conversation-specific metrics: response time (how quickly you replied), turn count, average response length, topic relevance
- Highlight of best sentence used + one sentence to improve
- "Continue this topic tomorrow" or "Try a new topic" option

**Technical Notes**
- Built on the **Gemini Live API**, specifically **Gemini 3.1 Flash Live** — an audio-to-audio native model that processes speech directly and generates spoken responses without a separate STT → LLM → TTS chain, giving lower latency and more natural pacing/tone (supports 90+ languages)
- Connection is a persistent **bidirectional WebSocket session** — audio streams in and out continuously within one call
- Built-in **Voice Activity Detection (VAD)** — automatically detects when the user starts/stops speaking, so turn-taking doesn't need to be built manually
- Built-in **barge-in support** — user can interrupt the AI mid-response, just like a real conversation
- **Automatic transcription** of both sides is provided by the API — feeds directly into the post-conversation feedback report, no separate transcription step needed
- **LangGraph** orchestrates everything *around* the live session: topic/persona setup before the call, and the transcript → scoring → database pipeline after the call ends (the live audio stream itself talks directly to the Gemini Live SDK, not through LangChain)
- AI persona/system instructions (Friendly Tutor, Native Peer, Examiner, Interviewer) are configured via system instructions at session start
- Function calling can be used mid-conversation if needed (e.g., flagging topic drift, logging a moment for later review)

---

## 4. Vocabulary Module

### Structure
- 10 new words per day → 210 words over 21 days
- Each word includes: definition, pronunciation (audio), part of speech, 2–3 example sentences, synonyms/antonyms

### Practice Exercises (per day)
1. **Fill in the Blanks** — use the word correctly in a sentence
2. **Match Definitions** — drag and drop matching
3. **Use in Context** — write your own sentence, AI checks it
4. **Pronunciation Practice** — record yourself saying the word, get feedback

### Retention System
- **Spaced repetition** — words reappear for review on Day 2, 4, 8, 15 after learning
- Mastery levels: New → Learning → Reviewing → Mastered
- Personal vocabulary bank you can browse anytime

---

## 5. Writing Module

### Structure
- 1 writing prompt per day (21 total)
- Prompt types rotate: Descriptive → Narrative → Argumentative/Opinion
- Target: 50–200 words, optional time limit

### AI Feedback Includes
- **Grammar** — spelling, punctuation, tense, agreement errors (highlighted inline)
- **Structure** — paragraph organization, flow, transitions
- **Vocabulary** — word choice suggestions, repetition detection
- **Coherence** — clarity and logical flow of ideas
- Overall score (0–100) + specific improvement tips
- Option to revise and resubmit (up to 3 times)

### Writing Portfolio
- All past submissions saved and viewable
- Score history and improvement trend over time

---

## 6. Progress Tracking & Analytics

### Dashboard Overview
- 🔥 Current streak (days)
- ⏱ Total practice time
- 📚 Words learned count
- 📊 Overall completion % across all 3 plans

### Per-Module Analytics
- **Speaking:** score trend graph, most common errors, average WPM, filler word trend
- **Vocabulary:** words mastered, category breakdown, review schedule
- **Writing:** score progression, error type breakdown, writing portfolio

### Gamification
- Streak calendar (heatmap style)
- Achievement badges (7-Day Streak, First Perfect Score, Plan Complete, etc.)
- Milestone celebrations (confetti animation on big wins)

---

## 7. The 21-Day → 5-Cycle System

Instead of a one-time 21-day challenge, TalkFiesta uses a **progressive 5-cycle system** so the app stays useful for months, not weeks:

| Cycle | Level | Focus |
|---|---|---|
| Cycle 1 | Foundation | Basic daily communication |
| Cycle 2 | Intermediate | Opinions, storytelling, workplace topics |
| Cycle 3 | Advanced | Abstract topics, critical thinking |
| Cycle 4 | Expert | Complex arguments, nuanced vocabulary |
| Cycle 5 | Master | Native-level fluency, public speaking mastery |

Each cycle = 21 days × 3 modules, with increasing difficulty. Completing all 5 cycles = full mastery journey (~8–11 months of content).

---

## 8. AI Architecture: Gemini + LangChain + LangGraph

TalkFiesta uses **Google Gemini** as its core AI model, with **LangChain** and **LangGraph** as the orchestration layer around it.

| Component | Role | Where It's Used |
|---|---|---|
| **Gemini 3.5 Flash** (text) | Core reasoning model for feedback generation | Grammar scoring, vocabulary suggestions, writing analysis — fast, cost-efficient, GA as of May 2026 |
| **Gemini 3 Pro** (text) | Heavier reasoning fallback | Multi-agent merge tasks (e.g. Panel Summary Agent), complex scoring edge cases |
| **Gemini 3.1 Flash Live** | Audio-to-audio real-time voice model | Real-Time AI Conversation feature (direct WebSocket, not via LangChain) |
| **LangChain** | Prompt templates + structured output parsing | Forces consistent JSON output for scores (fluency, grammar, vocabulary, etc.) so the frontend can render them reliably |
| **LangGraph** | Multi-step stateful workflows + multi-agent orchestration | Level Assessment quiz logic · Writing feedback pipeline (grammar → structure → vocab → merge) · Conversation session lifecycle (setup → live call → post-analysis) · Interview Panel agent supervision (Section 9) |

**Why this split:**
- The **Live API is a raw bidirectional WebSocket audio stream** — it connects directly to the client/server via the Gemini SDK, not through LangChain, since LangChain is built around text-based request/response calls
- **LangGraph sits around** the live session — handling topic/persona setup before the call starts, and running the transcript → scoring → database save pipeline after the call ends
- All the **scripted, non-real-time exercises** (speaking day exercises, vocabulary checks, writing feedback) go through a standard LangChain → Gemini text call, since these don't need live audio streaming

---

## 9. Multi-Agent Interview Panel (Domain & Level Adaptive)

An advanced evolution of Mock Interview mode — instead of one AI interviewer, a **3-agent panel** simulates a real panel interview, adapting its questions to the user's chosen domain and experience level. Built as a LangGraph supervisor + specialist-agents pattern.

### Setup — What the User Selects

| Selection | Options |
|---|---|
| **Domain** | Software/Tech · Business/Finance · Healthcare · Sales/Marketing · Customer Service · Academic/Research · General/Any |
| **Level** | Entry-Level (0–2 yrs) · Mid-Level (2–6 yrs) · Senior/Leadership (6+ yrs) |
| **Role (optional)** | Free text — e.g. "Backend Developer," "Financial Analyst," "ICU Nurse" — sharpens question specificity within the domain |
| **Company Style (optional)** | Startup (fast-paced, scrappy) vs Corporate (structured, formal) — changes tone, not content |

This selection becomes a shared **session config** passed into every agent's system prompt — one 3-agent architecture reused across every domain/level combination instead of hardcoding separate panels.

### The Panel — 3 Agents

**🧑‍💼 HR Agent**
- Fixed role across all domains — behavioral questions, culture fit, motivation, STAR-method answers
- Domain changes the *scenarios* used (e.g. "conflict with a teammate" → for healthcare becomes "conflict with a colleague during patient care")
- Level changes question maturity:
  - Entry: "Tell me about a time you learned something quickly"
  - Mid: "Tell me about a time you disagreed with your manager"
  - Senior: "Tell me about a time you made an unpopular decision that affected your team"

**🛠️ Technical/Role Agent** *(changes most per domain)*
- Software/Tech → system design, debugging scenarios, project deep-dives
- Business/Finance → case studies, market sizing, investment evaluation
- Healthcare → clinical judgment, protocol/ethics, patient prioritization
- Sales/Marketing → live objection-handling roleplay, "sell me this pen," campaign strategy
- Customer Service → de-escalation scenarios
- Academic/Research → methodology defense, study design
- Level changes depth/ambiguity, not just topic — Entry gets concrete single-answer questions, Mid gets applied situational questions, Senior gets open-ended trade-off questions with no single right answer

**👔 Manager Agent**
- Fixed role across domains — big-picture thinking, ownership, leadership, "why should we hire you"
- Entry: initiative, coachability, growth mindset
- Mid: ownership of outcomes, cross-team collaboration
- Senior: strategic thinking, team leadership, handling ambiguity, mentoring others

### Session Flow (with Cross-Talk)

```
1. INTRO — HR Agent opens the session
2. ROUND 1 — Behavioral (HR Agent leads, 2-3 questions)
3. HAND-OFF — "I'll pass it over to [Technical Agent] now."
4. ROUND 2 — Domain/Role Questions (Technical Agent leads, 2-4 questions,
   difficulty calibrated to level; Manager Agent occasionally jumps in
   with a follow-up)
5. HAND-OFF — "Let's bring in [Manager Agent] for a few final questions."
6. ROUND 3 — Big Picture (Manager Agent leads, 1-2 questions)
7. CANDIDATE Q&A — "Do you have any questions for us?"
8. CLOSING — HR Agent wraps up
```

Session length scales with level — Entry runs ~8–10 min, Senior runs ~15–20 min with deeper follow-ups.

### Multi-Agent Orchestration (LangGraph Pattern)

| Node | Role |
|---|---|
| **Panel Orchestrator (Supervisor)** | Decides turn order, tracks topics covered, decides when to hand off, prevents repeat questions, manages timing/round count |
| **HR Agent Node** | Behavioral questions + reactions — active in Round 1 & Q&A |
| **Technical Agent Node** | Domain-specific questions — active in Round 2, receives `domain` + `level` from session config |
| **Manager Agent Node** | Big-picture questions — active in Round 3 |

Shared session state passed between all nodes: full transcript so far, domain/level/role config, current round number, topics already asked, time elapsed/remaining. The Orchestrator is the only node making routing decisions — persona agents just generate content on their turn, keeping logic clean and making it easy to add a 4th agent later (e.g. a "Peer Interviewer") without touching the other three.

### Post-Session Feedback (Multi-Agent Report)

Each agent contributes its own mini-verdict, then a **Panel Summary Agent** merges everything:
- **Individual agent takes:** HR (culture fit, communication style), Technical (domain knowledge accuracy, depth), Manager (strategic thinking, leadership potential if senior)
- **Merged panel report:**
  - Overall verdict: Strong Hire / Hire / Maybe / No Hire
  - Score breakdown: Domain Knowledge · Communication · Confidence · Culture Fit
  - Best answer highlighted (which question, why it was strong)
  - Weakest answer highlighted + suggested better response
  - Full transcript with each agent's questions labeled
  - "What a real interviewer at this level would expect" — calibration note explaining why the level mattered

### Data Model Additions

| Table | Purpose |
|---|---|
| `InterviewPanelSession` | domain, level, role, company_style, status, overall_verdict, created_at |
| `PanelRound` | session_id, agent_type (HR/Technical/Manager), round_number, questions_asked (JSON) |
| `PanelResponse` | round_id, question, user_answer_transcript, agent_reaction, score |
| `DomainQuestionBank` | domain, level, question_pool — grounds the Technical Agent so it stays realistic and on-topic rather than hallucinating generic or wrong-sounding questions, especially for niche domains like healthcare |

### Why This Design Scales Well
- **New domain** → just add a prompt config + optional seed question bank for the Technical Agent; HR and Manager agents need no changes
- **New level** → adjust difficulty/tone instructions in the shared config; all 3 agents read from it
- **New agent** (e.g. "Peer Interviewer") → add one more LangGraph node; orchestrator handles the rest

This is where multi-agent design earns its complexity: one mega-prompt trying to be HR + Technical + Manager simultaneously produces noticeably more generic questions than three focused agents each doing one job well.

---

## 10. Tech Stack (Suggested)

| Layer | Technology |
|---|---|
| Frontend | Next.js 14+ (App Router), TypeScript, Tailwind CSS, shadcn/ui |
| State | Zustand + React Query |
| Backend | Next.js API Routes, Prisma ORM |
| Database | PostgreSQL (Supabase / Vercel Postgres) |
| Auth | NextAuth.js (Email + Google OAuth) |
| AI Model (text/feedback) | **Gemini 3.5 Flash** (GA — primary, fast + cost-efficient for high daily volume: grammar/vocab/writing scoring) · **Gemini 3 Pro** (fallback for harder reasoning, e.g. Panel Summary Agent merging multi-agent interview feedback) |
| Real-Time Voice Conversation | **Gemini 3.1 Flash Live** (audio-to-audio native, released March 2026 — handles STT, response & TTS in one streaming session; 90+ languages; built-in VAD & barge-in; no separate pipeline needed) |
| Speech-to-Text (scripted exercises) | Deepgram / Web Speech API (batch — for non-live recorded exercises: speaking days, pronunciation checks) |
| Text-to-Speech (scripted content) | ElevenLabs / OpenAI TTS (word pronunciation playback, non-live content) |
| AI Orchestration | **LangChain** (prompt templates, structured output parsing) + **LangGraph** (multi-step flows & multi-agent orchestration: level assessment, writing feedback pipeline, conversation session state, Interview Panel agents) |
| Storage | Supabase Storage / AWS S3 (audio files) |
| Hosting | Vercel |

---

## 11. MVP Scope (What to Build First)

✅ **Must-Have for Launch**
- Sign up / Login (Email + Google)
- Level assessment quiz (determines starting CEFR level)
- Goal selection (Fluency / Business / Exam / Travel)
- Speaking Module — Cycle 1 (21 days, conversation + basic public speaking)
- Vocabulary Module — Cycle 1 (210 words)
- Writing Module — Cycle 1 (21 prompts)
- AI feedback for all 3 modules
- Dashboard with streak, progress rings, today's tasks
- Basic achievements
- Progress/analytics page

⏸️ **Phase 2 (Post-MVP)**
- 🔴 Real-time AI conversation (live voice chat via Gemini 3.1 Flash Live)
- 🎭 Multi-Agent Interview Panel (HR + Technical + Manager agents)
- Mock interview mode
- Impromptu speaking mode
- Cycles 2–5 content
- Social sharing of achievements
- Email progress reports

❌ **Out of Scope for Now**
- Live human tutoring
- Mobile native apps
- Group/community features
- Certification programs

---

## 12. Design Inspiration

| App | What to Borrow |
|---|---|
| **Duolingo** | Linear day-by-day path, streak mechanics, playful rounded UI, celebratory animations |
| **ELSA Speak** | Color-coded pronunciation/error feedback, AI-personalized difficulty, detailed score breakdown |
| **SmallTalk2.me** | Full transcript + highlighted errors report, shareable session results |
| **Babbel** | Clean, professional lesson cards, real-world scenario framing |
| **Busuu** | Writing feedback layout, portfolio view of past work |

**Brand Feel:** Energetic but clean — green (trust/growth) + orange (energy/celebration), rounded UI, confetti on milestones, minimal clutter.

---

## 13. Three-Phase Build Plan

| Phase | Focus | Key Screens |
|---|---|---|
| **Phase 1** | Onboarding, Auth & Dashboard | Landing · Sign Up · Login · Level Test · Goal Selection · Dashboard · Profile |
| **Phase 2** | Core Learning Modules | Speaking recorder & feedback · Vocabulary exercises · Writing editor & feedback |
| **Phase 3** | Progress & Analytics | Progress overview · Charts · Achievements · Streak calendar · Reports |

---

## 14. Success Metrics

- Daily/Weekly Active Users
- Average practice time per session
- 21-day plan completion rate
- Vocabulary retention rate (words still "mastered" after 30 days)
- Average score improvement (Day 1 vs Day 21)
- User satisfaction / NPS

---

**Project:** TalkFiesta
**Type:** Personal AI-powered English learning web app
**Core Skills:** Speaking (incl. public speaking) · Vocabulary · Writing
**Status:** Concept finalized — ready for Phase 1 development

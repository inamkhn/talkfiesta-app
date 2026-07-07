# 🎉 TalkFiesta

TalkFiesta is a personal AI-powered English learning platform focused on interactive, personalized practice across **Speaking**, **Vocabulary**, and **Writing**. It leverages advanced LLM orchestration (LangGraph + Gemini) to provide high-quality, targeted feedback mimicking a real language tutor.

## Core Features & Progression

- **Onboarding & Assessment:** Users start with a level assessment quiz to determine their CEFR baseline, followed by personalized goal selection (Fluency, Business, Exam, or Travel).
- **The 21-Day / 5-Cycle System:** Instead of a one-time challenge, the app runs on a progressive 5-cycle system (Foundation to Master). Each cycle consists of 21 days of practice across all three modules.
- **Progress Tracking & Gamification:** A comprehensive dashboard tracks streaks, total practice time, and vocabulary retention. Features include score trend graphs, achievement badges, and milestone celebrations.

## Modules

### 1. ✍️ Writing Module
Provides daily writing prompts with a sophisticated **Multi-Agent LangGraph Pipeline** to evaluate user submissions. 
- **Feedback Graph:** Analyzes text concurrently across four dimensions: **Grammar**, **Structure**, **Vocabulary**, and **Coherence**. A **Supervisor Agent** merges these reports and produces a final score (0-100) and narrative feedback.
- **Revision Flow:** Users can revise submissions up to 3 times. A dedicated **Comparison Graph** analyzes the differences between revisions to highlight fixed vs. remaining issues.

### 2. 🗣️ Speaking Module
Focuses on conversational fluency and public speaking confidence. Features impromptu speaking tasks and detailed feedback on pronunciation, fluency, grammar, and delivery.
- **🔴 Real-Time AI Conversation:** A live, back-and-forth voice chat powered by **Gemini 3.1 Flash Live** (via WebSocket) mimicking real conversation with various personas (Tutor, Native Peer, Examiner).
- **🎭 Multi-Agent Interview Panel:** A LangGraph orchestrated 3-agent panel (HR, Technical, Manager) that simulates realistic, domain-specific job interviews dynamically scaled to the user's experience level.

### 3. 📚 Vocabulary Module
Provides personalized vocabulary practice tailored to the user's CEFR level. 
- **Spaced Repetition:** Reintroduces words for review to ensure long-term retention.
- **Interactive Exercises:** Includes fill-in-the-blank, matching, and pronunciation practice.

## Project Structure

- **`backend/`**: The FastAPI backend server. Contains API routes, CRUD operations, PostgreSQL models (SQLAlchemy), Celery background workers, and AI orchestration logic.
- **`frontend/`**: The Next.js frontend (React + Tailwind CSS). Provides the user interface, interactive editors, and feedback visualizations.
- **`docs/`**: Comprehensive system design documents detailing architecture, AI engineering principles, and specific module designs.

## Tech Stack

### Backend
- **Framework:** FastAPI (Python)
- **Database:** PostgreSQL (with `pgvector`) + SQLAlchemy ORM
- **AI/LLM:** Google Gemini (via `gemini_client`), LangGraph (Multi-Agent Orchestration)
- **Async Workers:** Celery + Redis

### Frontend
- **Framework:** Next.js 14+ (App Router), React, TypeScript
- **Styling:** Tailwind CSS, shadcn/ui

## Getting Started (Backend)

1. **Install Dependencies:**
   ```bash
   cd backend
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Environment Variables:**
   Create a `.env` file in the `backend/` directory with configurations including `REDIS_URL` and `GEMINI_API_KEY`.

3. **Run the API Server & Celery:**
   ```bash
   uvicorn app.main:app --reload
   celery -A app.workers.celery_app worker --loglevel=info
   ```

## Documentation

For deep technical dives into the architecture and AI design, refer to the documents in the `/docs` folder:
- `TalkFiesta.md` (Core product overview)
- `TalkFiesta-AI-Engineering.md` (AI principles, LangGraph patterns, rate limiting)
- `TalkFiesta-Writing-Module-System-Design.md`
- `TalkFiesta-Speaking-Module-System-Design.md`
- `TalkFiesta-Vocabulary-Module-System-Design.md`

# TalkFiesta — Dashboard & Learning Plan API Specification (V4)

**Status:** Proposed implementation contract (not confirmation of deployed V4 endpoints)  
**Version:** 1.0 — 2026-11-03  
**Stack:** Next.js / Auth.js BFF → FastAPI → SQLAlchemy 2 / PostgreSQL  
**Database baseline:** `TalkFiesta-Simplified-Database-Schema-v4.md` (14-table target)  
**Scope:** Read-only learner dashboard and learning-plan retrieval after onboarding/CEFR placement. Progress writes happen in validated practice services, **not in dashboard endpoints**.

---

## 1. Purpose and product requirements

A learner who completed onboarding should be able to:

1. Open the dashboard and see their **active 21-day cycle**, provisional CEFR placement, learning goal, streak, and today's recommended activities.
2. See the **next uncompleted activity per module**. `today` means the **next curriculum activity**, not a lesson unlocked by the current calendar date.
3. View each module's **21-day timeline**, including independent progress for Speaking, Vocabulary and Writing.
4. Resume activities or see **AI feedback pending** without losing completion credit.
5. See enough state to render a consistent dashboard after refreshing, switching devices, or returning after missed days.

### Business invariants

- Each user can have **at most one `ACTIVE` learning plan**.
- Each active plan can have **one `module_progress` row per module** (`SPEAKING`, `VOCABULARY`, `WRITING`).
- `module_progress.current_day` is **the next day to perform**, in range 1–21. After Day 21 is completed, keep the number at 21 and set `status=COMPLETED`.
- Published content is immutable and selected by **pinned `content_release`, module, cycle, day, CEFR level and goal variant**.
- A valid, accepted practice submission may be marked complete while its AI feedback remains `PENDING` or `PROCESSING`.
- Streaks and practice time are derived from `activity_completions` and the saved user's IANA timezone, not arbitrary client counts.
- Learners must never see private answer keys or rubric-only fields from `content_items.body`.
- The active plan and module progress are authoritative; the frontend never increments progress directly.

---

## 2. API conventions

**Base path:** `/api/v1`  
**Transport:** HTTPS / JSON  
**Authentication:** Auth.js/BFF browser session, exchanged for valid FastAPI application authorization; all endpoints are authenticated.  
**Ownership:** All reads are implicitly scoped to `current_user.id`. Do not accept `user_id` in query parameters.  
**IDs:** UUID strings.  
**Module enum:** `SPEAKING | VOCABULARY | WRITING`.  
**Time:** timestamps in UTC ISO 8601 (`Z`), and `local_practice_date` in `YYYY-MM-DD`; all calendar calculations use `users.timezone`.  
**Response schema:** Public Pydantic `response_model` with explicit exclusions for private content.  
**Caching:** user-private, short-lived caching only (`Cache-Control: private, no-store` initially); do not use a shared public CDN cache for learner dashboards.  
**Versioning:** Maintain stable v1 response shapes; add fields compatibly.

### Canonical error response

```json
{
  "error": {
    "code": "ONBOARDING_REQUIRED",
    "message": "Complete your English assessment to start learning.",
    "details": {},
    "request_id": "req_01HX_example"
  }
}
```

Suggested HTTP codes: `401` unauthenticated, `403` account disabled / insufficient permission, `404` requested resource absent or not owned, `409` invalid learner state or curriculum gap, `422` invalid path/query, `429` rate limit, `500` unexpected error. Use user-safe messages; never expose SQL, prompt internals or storage keys.

---

## 3. Endpoint catalogue

| Method | Endpoint | Primary use | Success |
|---|---|---|---|
| `GET` | `/api/v1/learning-plans/current` | Active plan, goals, cycle, enrollments | `200` |
| `GET` | `/api/v1/learning-plans/current/today` | Next activity in each enrolled module | `200` |
| `GET` | `/api/v1/learning-plans/current/modules/{module}/timeline` | 21-day progression for one module | `200` |
| `GET` | `/api/v1/dashboard` | One aggregated home-screen payload | `200` |

**Not included as a write endpoint:** `/dashboard/complete`, `/learning-plans/advance`, `/progress/increment`. Only authenticated and validated practice submission services may credit an activity.

### 3.1 `GET /api/v1/learning-plans/current`

**Purpose:** Return the current plan and module enrollment state. Useful on login and on the Learning Plan screen.

**Request:** No body. Optional header `Authorization: Bearer <token>` when FastAPI is called directly by a trusted client/BFF.

**200 example:**

```json
{
  "plan": {
    "id": "11111111-1111-4111-8111-111111111111",
    "cycle": 1,
    "status": "ACTIVE",
    "placement_cefr": "A2",
    "placement_provisional": true,
    "goals": ["BUSINESS"],
    "focus_areas": ["SPEAKING", "WRITING"],
    "daily_target_minutes": 15,
    "created_at": "2026-11-01T09:00:00Z"
  },
  "modules": [
    {
      "module": "SPEAKING",
      "progress_id": "22222222-2222-4222-8222-222222222221",
      "status": "ACTIVE",
      "current_day": 2,
      "completed_days": 1,
      "total_days": 21,
      "target_cefr": "A2",
      "prioritized": true
    },
    {
      "module": "VOCABULARY",
      "progress_id": "22222222-2222-4222-8222-222222222222",
      "status": "ACTIVE",
      "current_day": 1,
      "completed_days": 0,
      "total_days": 21,
      "target_cefr": "A2",
      "prioritized": false
    },
    {
      "module": "WRITING",
      "progress_id": "22222222-2222-4222-8222-222222222223",
      "status": "ACTIVE",
      "current_day": 1,
      "completed_days": 0,
      "total_days": 21,
      "target_cefr": "A2",
      "prioritized": true
    }
  ]
}
```

**Rules:**
- `completed_days` is computed from credited `activity_completions`, not `current_day - 1` (useful for data consistency checks and potential optional activities).
- Include only modules actually enrolled in the plan. Example contains three.
- If onboarding is not completed: `409 ONBOARDING_REQUIRED`; if user completed onboarding but no plan exists: `404 ACTIVE_PLAN_NOT_FOUND` and log a reconciliation signal.
- If the last cycle is fully completed and no current plan exists, return `404 ACTIVE_PLAN_NOT_FOUND`; the client can offer the next-cycle enrollment flow later.

### 3.2 `GET /api/v1/learning-plans/current/today`

**Purpose:** Show exactly what the learner should work on next, selected from the enrollment's pinned content release.

**200 example:**

```json
{
  "plan_id": "11111111-1111-4111-8111-111111111111",
  "cycle": 1,
  "daily_target_minutes": 15,
  "timezone": "Asia/Riyadh",
  "activities": [
    {
      "module": "SPEAKING",
      "day": 2,
      "content_item_id": "33333333-3333-4333-8333-333333333331",
      "title": "Describe your workday",
      "description": "Speak about your daily responsibilities.",
      "content_kind": "SPEAKING_LESSON",
      "estimated_minutes": 6,
      "activity_status": "NOT_STARTED",
      "evaluation_status": null,
      "route": "/speaking/day/2"
    },
    {
      "module": "VOCABULARY",
      "day": 1,
      "content_item_id": "33333333-3333-4333-8333-333333333332",
      "title": "10 workplace words",
      "description": "Build useful professional vocabulary.",
      "content_kind": "VOCABULARY_LESSON",
      "estimated_minutes": 4,
      "activity_status": "NOT_STARTED",
      "evaluation_status": null,
      "route": "/vocabulary/day/1"
    },
    {
      "module": "WRITING",
      "day": 1,
      "content_item_id": "33333333-3333-4333-8333-333333333333",
      "title": "Write a professional introduction",
      "description": "Introduce yourself in a short paragraph.",
      "content_kind": "WRITING_LESSON",
      "estimated_minutes": 5,
      "activity_status": "NOT_STARTED",
      "evaluation_status": null,
      "route": "/writing/day/1"
    }
  ]
}
```

**Rules:**
- Activity query: `(release_key, cycle, module, day, cefr_level, goal_variant, slot='CORE', status='PUBLISHED')` matches the pinned enrollment.
- The server selects one required `CORE` activity per module/day for V4. Optional `EXTRA` content can be separately listed but never confused with required completion.
- If a module status is `COMPLETED`, return an activity summary `{ "module": "SPEAKING", "day": 21, "activity_status": "COMPLETED", "content_item_id": null }` or omit it consistently; this contract recommends including a completed module summary to avoid the frontend thinking it has vanished.
- If content for an active module/day is missing, return `409 CURRICULUM_CONTENT_UNAVAILABLE` rather than silently selecting a different version or generating runtime content.
- Use a **public content projection** and strip answer keys, evaluator guidance and hidden scoring rubrics from `content_items.body`.
- A learner who finishes a valid speaking activity has progressed to their next day even if AI feedback for the previous submission is pending. The pending job appears under Dashboard `pending_feedback`.

### 3.3 `GET /api/v1/learning-plans/current/modules/{module}/timeline`

**Path:** `{module}` is `speaking`, `vocabulary`, or `writing` (case-insensitive input mapped to canonical uppercase enum); return `422` for an unknown module, `404 MODULE_NOT_ENROLLED` for a valid but unselected module.

**200 example (truncated to first 3 days for readability; production sends all 21):**

```json
{
  "module": "SPEAKING",
  "progress_id": "22222222-2222-4222-8222-222222222221",
  "cycle": 1,
  "current_day": 2,
  "status": "ACTIVE",
  "completed_days": 1,
  "total_days": 21,
  "days": [
    {"day": 1, "state": "COMPLETED", "completed_at": "2026-11-03T10:20:00Z", "title": "Introduce yourself"},
    {"day": 2, "state": "AVAILABLE", "completed_at": null, "title": "Describe your workday"},
    {"day": 3, "state": "LOCKED", "completed_at": null, "title": "Talk about your hobbies"}
  ]
}
```

**Rules:**
- States: `COMPLETED`, `AVAILABLE`, `LOCKED`. Optionally add `NOT_PUBLISHED` only to admin views, not regular learner timelines.
- All 21 day entries must be returned in production. `COMPLETED` is derived from `activity_completions` for the pinned enrollment/activity.
- Day 21 remains at `current_day=21` with `module_progress.status=COMPLETED` after credit. All 21 returned day states are `COMPLETED`.
- No learner write actions from timeline endpoint.

### 3.4 `GET /api/v1/dashboard`

**Purpose:** Single aggregated endpoint optimized for the learner home screen. It calls domain query services internally (not HTTP calls back into FastAPI).

**200 example:**

```json
{
  "learner": {
    "display_name": "Sam",
    "timezone": "Asia/Riyadh",
    "provisional_cefr": "A2"
  },
  "learning_plan": {
    "id": "11111111-1111-4111-8111-111111111111",
    "cycle": 1,
    "daily_target_minutes": 15,
    "completed_required_activities": 1,
    "total_required_activities": 63,
    "overall_completion_percent": 1.6
  },
  "modules": [
    {"module": "SPEAKING", "completed_days": 1, "total_days": 21, "current_day": 2},
    {"module": "VOCABULARY", "completed_days": 0, "total_days": 21, "current_day": 1},
    {"module": "WRITING", "completed_days": 0, "total_days": 21, "current_day": 1}
  ],
  "streak": {
    "current_days": 1,
    "longest_days": 1,
    "last_active_local_date": "2026-11-03"
  },
  "practice": {
    "total_seconds": 300,
    "today_seconds": 300,
    "mastered_words": 5
  },
  "today_preview": [
    {"module": "SPEAKING", "day": 2, "title": "Describe your workday", "content_item_id": "33333333-3333-4333-8333-333333333331"},
    {"module": "VOCABULARY", "day": 1, "title": "10 workplace words", "content_item_id": "33333333-3333-4333-8333-333333333332"},
    {"module": "WRITING", "day": 1, "title": "Write a professional introduction", "content_item_id": "33333333-3333-4333-8333-333333333333"}
  ],
  "pending_feedback": [
    {
      "submission_id": "44444444-4444-4444-8444-444444444444",
      "module": "SPEAKING",
      "evaluation_status": "PROCESSING",
      "submitted_at": "2026-11-03T10:20:00Z"
    }
  ],
  "recent_achievements": [
    {"achievement_key": "FIRST_SPEAKING_DAY", "earned_at": "2026-11-03T10:20:00Z"}
  ]
}
```

> **Examples are illustrative and internally independent**; they're not data from a real user or a fixed test fixture. In particular, real streak counts must be computed from activity dates, not copied from this example. For automated contract tests, use deliberately consistent seeded fixtures.

**Derivation details:**
- `overall_completion_percent = completed required day credits / (21 * number of required enrolled modules) * 100`, rounded to one decimal. With 1 credit and 3 modules: `1 / 63 * 100 = 1.6%`. Optional activities do not inflate completion.
- `current_days` streak: count consecutive local calendar dates with at least one credited completion; if no activity today but activity yesterday, retain the live current streak until the next local day; otherwise 0. Apply exactly one documented policy across all clients.
- `mastered_words` = count of `user_vocabulary.status='MASTERED'` for this learner.
- `today_seconds` = sum of credited `duration_seconds` whose `local_practice_date` matches current date in `users.timezone`; `total_seconds` sums all accepted credits.
- `pending_feedback` = accepted `practice_submissions` with `evaluation_status` in `PENDING, PROCESSING` (limit to a small number; include a `pending_feedback_count` if needed).
- `recent_achievements` comes from `user_achievements`, with display labels/icons mapped through server-side achievement configuration (no separate achievement definitions table in V4).
- Never return raw S3 keys, private recordings, model prompts or full user transcripts in the dashboard.

---

## 4. Request/response schema types (Pydantic)

```python
from enum import StrEnum
from datetime import datetime, date
from uuid import UUID
from pydantic import BaseModel, Field

class Module(StrEnum):
    SPEAKING = "SPEAKING"
    VOCABULARY = "VOCABULARY"
    WRITING = "WRITING"

class ModuleSummary(BaseModel):
    module: Module
    progress_id: UUID
    status: str
    current_day: int = Field(ge=1, le=21)
    completed_days: int = Field(ge=0, le=21)
    total_days: int = 21
    target_cefr: str
    prioritized: bool

class PlanSummary(BaseModel):
    id: UUID
    cycle: int = Field(ge=1, le=5)
    status: str
    placement_cefr: str
    placement_provisional: bool
    goals: list[str]
    focus_areas: list[Module]
    daily_target_minutes: int = Field(gt=0, le=180)
    created_at: datetime

class CurrentPlanResponse(BaseModel):
    plan: PlanSummary
    modules: list[ModuleSummary]

class TimelineDay(BaseModel):
    day: int = Field(ge=1, le=21)
    state: str
    completed_at: datetime | None = None
    title: str | None = None

class ModuleTimelineResponse(BaseModel):
    module: Module
    progress_id: UUID
    cycle: int
    current_day: int
    status: str
    completed_days: int
    total_days: int = 21
    days: list[TimelineDay]

# Define Today's Activity and Dashboard response as separate DTOs;
# avoid serializing raw SQLAlchemy rows or content_items.body.
```

Use `response_model=...` on each FastAPI route, `from_attributes=True` only for safe direct ORM projections, and apply strict public DTO mapping when `content_items.body` contains private answers or rubric fields.

---

## 5. FastAPI router and service contracts

Suggested folder organization:

```text
app/modules/
├── learning_plans/
│   ├── router.py
│   ├── schemas.py
│   ├── service.py
│   ├── repository.py
│   └── selectors.py           # pinned curriculum lesson resolution
├── dashboard/
│   ├── router.py
│   ├── schemas.py
│   └── query_service.py       # read-only aggregation
├── progress/
│   ├── completion_service.py  # writes only from validated practices
│   ├── streaks.py
│   └── repository.py
└── curriculum/
    ├── selectors.py
    └── public_projection.py
```

```python
# Service interface sketches (not full implementations)
class LearningPlanQueryService:
    async def get_current(self, *, user_id): ...
    async def get_next_activities(self, *, user_id): ...
    async def get_timeline(self, *, user_id, module): ...

class DashboardQueryService:
    async def get_overview(self, *, user_id): ...

class ProgressCompletionService:
    async def credit_accepted_submission(self, *, user_id, submission_id): ...
```

Example route:

```python
from fastapi import APIRouter, Depends
from app.api.deps import get_current_user

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

@router.get("")
async def get_dashboard(user=Depends(get_current_user)):
    return await dashboard_query_service.get_overview(user_id=user.id)
```

Production implementation should inject the service through a dependency instead of referencing an undeclared module global. **The snippet illustrates the intended API boundary**, not a runnable standalone route.

---

## 6. Database reads and indexing

| Query | Table(s) | Critical filtering / index |
|---|---|---|
| Active plan | `learning_plans` | Partial unique `(user_id) WHERE status='ACTIVE'` |
| Module enrollment | `module_progress` | Unique `(learning_plan_id, module)` |
| Required lesson | `content_items` | `(release_key, module, cycle, day, cefr_level, goal_variant, slot)` filtered to published core |
| Completed days | `activity_completions` | `(module_progress_id, content_item_id)` unique; `(user_id, local_practice_date)` |
| Pending feedback | `practice_submissions` | `(user_id, evaluation_status, submitted_at)` |
| Vocabulary mastery | `user_vocabulary` | `(user_id, status)` |
| Recent badges | `user_achievements` | `(user_id, earned_at DESC)` |

For a 21-day curriculum, the timeline is a small bounded query; no timeline pagination is required. Prefer a few joined/batched queries over one SQL query per timeline day (`N+1`).

---

## 7. Edge cases and expected responses

| Scenario | Behavior |
|---|---|
| User hasn't completed onboarding | `409 ONBOARDING_REQUIRED`, return authoritative next step in safe `details` |
| Onboarding completed but no active plan exists | `404 ACTIVE_PLAN_NOT_FOUND`, emit reconciliation alert |
| Module not enrolled | `404 MODULE_NOT_ENROLLED` |
| Unknown module string | `422 VALIDATION_ERROR` |
| Published lesson missing for pinned release | `409 CURRICULUM_CONTENT_UNAVAILABLE`, do not silently switch release |
| AI feedback still processing after speaking completion | Dashboard shows next Speaking day plus pending feedback reference |
| User completed Day 21 in one module | Module status `COMPLETED`, current_day remains 21 |
| Multiple activities completed on one date | One streak day, but sum activity durations |
| User changes timezone | Existing credited `local_practice_date` stays immutable; explicitly define rebase policy if needed later |
| Unexpected duplicate credits | Unique constraint prevents duplicate `(module_progress_id, content_item_id)` |

---

## 8. Acceptance / integration tests

- [ ] `GET /dashboard` for unauthenticated user returns `401`.
- [ ] Learner A can never view learner B's progress or content submissions.
- [ ] `current_day=2` for Speaking and `current_day=1` for Writing resolves different assigned lessons correctly.
- [ ] Returned content is from the **pinned published release**, not the newest draft.
- [ ] `timeline` returns exactly 21 entries and correct completed/current/locked states.
- [ ] A completed Day 21 enrollment remains at day 21 with `COMPLETED` status.
- [ ] Accepted Speaking submission advances module progress before AI evaluation finishes.
- [ ] Duplicate submission/credit cannot increment completed days twice.
- [ ] Streak counts at most one calendar day per local date.
- [ ] Dashboard response contains no answer keys, private object keys, or model prompts.
- [ ] Query count is bounded (not 21 per module); indexes support streak and pending-feedback reads.
- [ ] Missing content release yields explicit `409`, with no silent backfill.

---

## 9. Implementation sequence

1. Define public `Plan`, `Activity`, `Timeline`, and `Dashboard` Pydantic responses.
2. Implement `LearningPlanQueryService` with ownership-scoped repositories.
3. Implement published lesson lookup using the pinned V4 `content_items` release.
4. Implement `DashboardQueryService` and the streak aggregator derived from `activity_completions`.
5. Add `GET` routes, unit tests and integration fixtures for mixed-module progress.
6. Connect the frontend with TanStack Query; invalidate dashboard/current activities after accepted practice submission.
7. Add tracing for API/database performance; do not send raw learner content to telemetry.

---

## 10. Related contracts

- `TalkFiesta-Simplified-Database-Schema-v4.md` — authoritative **proposed** table layout.
- `TalkFiesta-Auth-to-Assessment-API-Flow-V4.md` — preceding onboarding and placement workflow.
- `TalkFiesta-AI-Assessment-API-Flow-V4.md` — asynchronous assessment processing conventions.
- `TalkFiesta-Speaking-APIs-V4.md` — the actual first practice-submission lifecycle that earns activity completion.

**Status note:** V4 is an architectural target. These endpoints and JSON formats are proposed implementation contracts, not claims that the earlier V3 ZIP already implements them.

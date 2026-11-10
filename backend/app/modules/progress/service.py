"""Read-only service layer for `/api/v1/progress` endpoints."""

from __future__ import annotations

import base64
import json
import logging
from datetime import UTC, date, datetime
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    ConflictError,
    NotFoundError,
    ServiceUnavailableError,
    ValidationAppError,
)
from app.modules.practice.models import PracticeSubmission
from app.modules.progress.repository import ProgressRepository
from app.modules.progress.schemas import (
    AchievementFilterStatus,
    AchievementsResponse,
    ActivePlanOverview,
    ActivityCalendarDayItem,
    ActivityCalendarResponse,
    ActivityHistoryItem,
    ActivityHistoryPagination,
    ActivityHistoryResponse,
    AiFeedbackOverview,
    CefrAssessmentHistoryItem,
    CefrHistoryResponse,
    ModuleDetailResponse,
    ModuleLiteral,
    ModuleOverviewItem,
    ModuleProgressBlock,
    OverviewScope,
    PracticeOverview,
    ProgressOverviewResponse,
    ProgressStreaksResponse,
    RecentModuleSubmissionItem,
    SpeakingModuleMetrics,
    StreakPolicy,
    VocabularyModuleMetrics,
    VocabularyOverview,
    WritingModuleMetrics,
)
from app.modules.progress.streaks import StreakCalculator

logger = logging.getLogger(__name__)
MODULE_ORDER = ("SPEAKING", "VOCABULARY", "WRITING")
DETAILS_URL_PREFIX_BY_MODULE: dict[str, str] = {
    "SPEAKING": "/api/v1/speaking/submissions/",
    "WRITING": "/api/v1/writing/submissions/",
    "VOCABULARY": "/api/v1/vocabulary/practice-sessions/",
}


def encode_history_cursor(completed_at: datetime, completion_id: UUID) -> str:
    payload = json.dumps(
        {"ts": completed_at.isoformat(), "id": str(completion_id)},
        separators=(",", ":"),
    ).encode("utf-8")
    return base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")


def decode_history_cursor(cursor: str) -> tuple[datetime, UUID]:
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        raw = base64.urlsafe_b64decode(padded.encode("ascii"))
        data = json.loads(raw.decode("utf-8"))
        if not isinstance(data, dict):
            raise TypeError("Cursor payload must be an object")
        ts = datetime.fromisoformat(str(data["ts"]))
        if ts.tzinfo is None:
            raise ValueError("Cursor timestamp must be timezone-aware")
        cid = UUID(str(data["id"]))
        return ts, cid
    except Exception as exc:
        raise ValidationAppError(
            "Invalid pagination cursor.",
            code="INVALID_CURSOR",
        ) from exc


def resolve_local_today(tz_name: str | None, now_utc: datetime) -> tuple[str, date]:
    """Return `(resolved_tz_name, local_date)` for `now_utc`."""
    candidate = (tz_name or "UTC").strip() or "UTC"
    try:
        tz = ZoneInfo(candidate)
    except ZoneInfoNotFoundError:
        tz = ZoneInfo("UTC")
        candidate = "UTC"
    return candidate, now_utc.astimezone(tz).date()


def extract_submission_score(submission: PracticeSubmission) -> float | None:
    """Return numeric 0..100 score only when `evaluation_status == 'COMPLETED'`."""
    if submission.evaluation_status != "COMPLETED":
        return None
    if submission.score is not None:
        return round(float(submission.score), 1)
    feedback = submission.feedback
    if isinstance(feedback, dict):
        scores = feedback.get("scores")
        if isinstance(scores, dict):
            overall = scores.get("overall")
            if isinstance(overall, (int, float)) and not isinstance(overall, bool):
                return round(float(overall), 1)
            dims = [
                scores.get(k)
                for k in ("grammar", "vocabulary", "coherence", "task_relevance")
            ]
            if all(
                isinstance(v, (int, float)) and not isinstance(v, bool) for v in dims
            ):
                return round(sum(float(v) for v in dims) / 4.0, 1)
        obj = feedback.get("objective_result")
        if isinstance(obj, dict):
            correct = obj.get("correct")
            total = obj.get("total")
            if (
                isinstance(correct, (int, float))
                and isinstance(total, (int, float))
                and total > 0
            ):
                return round(100.0 * float(correct) / float(total), 1)
    if isinstance(submission.input, dict):
        obj = submission.input.get("objective_result")
        if isinstance(obj, dict):
            correct = obj.get("correct")
            total = obj.get("total")
            if (
                isinstance(correct, (int, float))
                and isinstance(total, (int, float))
                and total > 0
            ):
                return round(100.0 * float(correct) / float(total), 1)
    return None


def extract_rubric_version(
    submission: PracticeSubmission,
    job_rubric_version: str | None,
    default_version: str,
) -> str:
    """Resolve the rubric version used to evaluate a completed submission."""
    if isinstance(submission.feedback, dict):
        rv = submission.feedback.get("rubric_version")
        if isinstance(rv, str) and rv.strip():
            return rv.strip()
    if isinstance(job_rubric_version, str) and job_rubric_version.strip():
        return job_rubric_version.strip()
    return default_version


def extract_speaking_wpm(submission: PracticeSubmission) -> float | None:
    """Extract approximate speaking WPM if grounded duration/transcript evidence exists."""
    if isinstance(submission.feedback, dict):
        audio_metrics = submission.feedback.get("audio_metrics")
        if isinstance(audio_metrics, dict):
            wpm = audio_metrics.get("approx_recording_wpm")
            if isinstance(wpm, (int, float)) and not isinstance(wpm, bool) and wpm >= 0:
                return float(wpm)
    if (
        isinstance(submission.transcript, str)
        and submission.transcript.strip()
        and isinstance(submission.input, dict)
    ):
        raw_dur = submission.input.get("duration_seconds")
        try:
            dur = float(raw_dur) if raw_dur is not None else 0.0
        except (TypeError, ValueError):
            dur = 0.0
        if dur > 0:
            words = len(submission.transcript.split())
            return (words / dur) * 60.0
    return None


def extract_writing_word_count(submission: PracticeSubmission) -> int | None:
    """Extract word count from a writing submission input payload."""
    if not isinstance(submission.input, dict):
        return None
    wc = submission.input.get("word_count")
    if isinstance(wc, int) and not isinstance(wc, bool) and wc >= 0:
        return wc
    text = submission.input.get("text")
    if isinstance(text, str):
        return len(text.split())
    return None



class ProgressQueryService:
    """Owner-scoped analytics and progress read service."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = ProgressRepository(session)
        self.streak_calculator = StreakCalculator()

    async def get_overview(
        self,
        user_id: UUID,
        scope: OverviewScope = "current",
    ) -> ProgressOverviewResponse:
        rows = await self.repository.get_active_plan_rows(user_id)
        if not rows:
            raise NotFoundError("Account not found.")

        first = rows[0]
        if first.onboarding_status != "COMPLETED":
            raise ConflictError(
                "Complete onboarding to start learning.",
                code="ONBOARDING_REQUIRED",
            )

        now_utc = datetime.now(UTC)
        tz_name, local_today = resolve_local_today(first.timezone, now_utc)
        plan = first.LearningPlan

        active_plan_summary: ActivePlanOverview | None = None
        module_items: list[ModuleOverviewItem] = []

        if plan is not None:
            if len({row.LearningPlan.id for row in rows if row.LearningPlan}) != 1:
                logger.error("progress_overview_inconsistent user_id=%s", user_id)
                raise ServiceUnavailableError(
                    "The saved learning plan is incomplete. Please try again later.",
                    code="LEARNING_PLAN_UNAVAILABLE",
                )

            seen_modules: set[str] = set()
            for row in rows:
                progress = row.ModuleProgress
                if progress is None:
                    continue
                if progress.module in seen_modules:
                    logger.error(
                        "progress_overview_duplicate_module user_id=%s plan_id=%s",
                        user_id,
                        plan.id,
                    )
                    raise ServiceUnavailableError(
                        "The saved learning plan is incomplete. Please try again later.",
                        code="LEARNING_PLAN_UNAVAILABLE",
                    )
                seen_modules.add(progress.module)
                completed_days = min(max(int(row.completed_days or 0), 0), 21)
                module_items.append(
                    ModuleOverviewItem(
                        module=progress.module,
                        status=progress.status,
                        current_day=progress.current_day,
                        completed_days=completed_days,
                        total_days=21,
                        completion_percent=round(100.0 * completed_days / 21, 1),
                    )
                )

            module_items.sort(key=lambda item: MODULE_ORDER.index(item.module))
            required_modules = [item.module for item in module_items]
            required_activities = 21 * len(module_items)
            completed_activities = sum(item.completed_days for item in module_items)
            overall_percent = (
                round(100.0 * completed_activities / required_activities, 1)
                if required_activities > 0
                else 0.0
            )
            active_plan_summary = ActivePlanOverview(
                plan_id=plan.id,
                cycle=plan.cycle,
                placement_cefr=plan.placement_cefr,
                status=plan.status,
                required_modules=required_modules,
                required_activities=required_activities,
                completed_activities=completed_activities,
                completion_percent=overall_percent,
            )

        scoped_plan_id = (
            plan.id if (scope == "current" and plan is not None) else None
        )
        total_seconds, active_days = await self.repository.get_practice_totals(
            user_id, plan_id=scoped_plan_id
        )
        credited_dates = await self.repository.get_credited_dates(user_id)
        streak = self.streak_calculator.calculate(credited_dates, local_today)

        vocab_counts = await self.repository.get_vocabulary_counts(user_id, now_utc)
        pending_count, completed_count = await self.repository.get_ai_feedback_counts(
            user_id, plan_id=scoped_plan_id
        )

        return ProgressOverviewResponse(
            as_of=now_utc,
            timezone=tz_name,
            active_plan=active_plan_summary,
            modules=module_items,
            practice=PracticeOverview(
                total_seconds=total_seconds,
                active_days=active_days,
                current_streak_days=streak.current_streak_days,
                longest_streak_days=streak.longest_streak_days,
            ),
            vocabulary=VocabularyOverview(**vocab_counts),
            ai_feedback=AiFeedbackOverview(
                pending_count=pending_count,
                completed_count=completed_count,
            ),
        )

    async def get_module(
        self,
        user_id: UUID,
        module: ModuleLiteral,
        cycle: int | None = None,
    ) -> ModuleDetailResponse:
        user, plan, progress, completed_days = (
            await self.repository.get_plan_and_module_progress(
                user_id, module, cycle=cycle
            )
        )
        if user is None:
            raise NotFoundError("Account not found.")
        if user.onboarding_status != "COMPLETED":
            raise ConflictError(
                "Complete onboarding to start learning.",
                code="ONBOARDING_REQUIRED",
            )
        if plan is None:
            if cycle is None:
                raise NotFoundError(
                    "No active learning plan was found.",
                    code="ACTIVE_PLAN_NOT_FOUND",
                )
            raise NotFoundError(
                "No learning plan was found for the requested cycle.",
                code="PLAN_NOT_FOUND",
            )
        if progress is None:
            raise NotFoundError(
                "This module is not enrolled in the selected learning plan.",
                code="MODULE_NOT_ENROLLED",
            )

        clamped_days = min(max(completed_days, 0), 21)
        progress_block = ModuleProgressBlock(
            status=progress.status,
            current_day=progress.current_day,
            completed_days=clamped_days,
            total_days=21,
            completion_percent=round(100.0 * clamped_days / 21, 1),
        )

        mode_map = {
            "SPEAKING": "RECORDED_SPEAKING",
            "WRITING": "WRITING",
            "VOCABULARY": "VOCAB_QUIZ",
        }
        sub_rows = await self.repository.get_module_submissions(
            user_id, progress.id, mode_map[module]
        )

        recent_submissions: list[RecentModuleSubmissionItem] = []
        for row in sub_rows[:10]:
            sub: PracticeSubmission = row.PracticeSubmission
            day_val = row.content_day
            if day_val is None and isinstance(sub.input, dict):
                raw_day = sub.input.get("day")
                if isinstance(raw_day, int) and 1 <= raw_day <= 21:
                    day_val = raw_day
            recent_submissions.append(
                RecentModuleSubmissionItem(
                    id=sub.id,
                    day=day_val,
                    submitted_at=sub.submitted_at,
                    evaluation_status=sub.evaluation_status,
                    score=extract_submission_score(sub),
                )
            )

        if module == "SPEAKING":
            metrics = self._build_speaking_metrics(sub_rows)
        elif module == "WRITING":
            metrics = self._build_writing_metrics(sub_rows)
        else:
            now_utc = datetime.now(UTC)
            vocab_counts = await self.repository.get_vocabulary_counts(
                user_id, now_utc
            )
            metrics = self._build_vocabulary_metrics(sub_rows, vocab_counts)

        return ModuleDetailResponse(
            module=module,
            cycle=plan.cycle,
            progress=progress_block,
            metrics=metrics,
            recent_submissions=recent_submissions,
        )

    def _build_speaking_metrics(self, sub_rows) -> SpeakingModuleMetrics:
        submissions = [r.PracticeSubmission for r in sub_rows]
        completed_count = len(submissions)
        evaluated_count = sum(
            1 for s in submissions if s.evaluation_status == "COMPLETED"
        )
        pending_count = sum(
            1
            for s in submissions
            if s.evaluation_status in ("PENDING", "PROCESSING")
        )

        scored_pairs: list[tuple[float, str]] = []
        wpms: list[float] = []
        pron_scores: list[float] = []

        for row in sub_rows:
            sub: PracticeSubmission = row.PracticeSubmission
            score = extract_submission_score(sub)
            if score is not None:
                rv = extract_rubric_version(
                    sub, row.job_rubric_version, "speaking-feedback-v1"
                )
                scored_pairs.append((score, rv))
            if sub.evaluation_status == "COMPLETED":
                wpm = extract_speaking_wpm(sub)
                if wpm is not None:
                    wpms.append(wpm)
                if isinstance(sub.feedback, dict):
                    ps = sub.feedback.get("pronunciation_score")
                    if (
                        isinstance(ps, (int, float))
                        and not isinstance(ps, bool)
                        and 0 <= ps <= 100
                    ):
                        pron_scores.append(float(ps))

        rubrics = {rv for _, rv in scored_pairs}
        avg_score: float | None = None
        rubric_version: str | None = None
        warning: str | None = None
        if len(rubrics) == 1 and scored_pairs:
            rubric_version = next(iter(rubrics))
            avg_score = round(
                sum(s for s, _ in scored_pairs) / len(scored_pairs), 1
            )
        elif len(rubrics) > 1:
            warning = (
                "Multiple rubric versions exist across evaluated submissions; "
                "average_overall_score is omitted."
            )

        avg_wpm = round(sum(wpms) / len(wpms), 1) if wpms else None
        avg_pron = (
            round(sum(pron_scores) / len(pron_scores), 1) if pron_scores else None
        )

        return SpeakingModuleMetrics(
            completed_submissions=completed_count,
            evaluated_submissions=evaluated_count,
            pending_feedback=pending_count,
            average_overall_score=avg_score,
            average_words_per_minute=avg_wpm,
            pronunciation_score=avg_pron,
            rubric_version=rubric_version,
            comparability_warning=warning,
        )

    def _build_writing_metrics(self, sub_rows) -> WritingModuleMetrics:
        baseline_rows = [
            r for r in sub_rows if r.PracticeSubmission.revision_number == 1
        ]
        revision_rows = [
            r for r in sub_rows if r.PracticeSubmission.revision_number > 1
        ]

        completed_count = len(baseline_rows)
        evaluated_count = sum(
            1
            for r in baseline_rows
            if r.PracticeSubmission.evaluation_status == "COMPLETED"
        )
        pending_count = sum(
            1
            for r in sub_rows
            if r.PracticeSubmission.evaluation_status in ("PENDING", "PROCESSING")
        )

        scored_pairs: list[tuple[float, str]] = []
        word_counts: list[int] = []
        for row in baseline_rows:
            sub: PracticeSubmission = row.PracticeSubmission
            wc = extract_writing_word_count(sub)
            if wc is not None:
                word_counts.append(wc)
            score = extract_submission_score(sub)
            if score is not None:
                rv = extract_rubric_version(
                    sub, row.job_rubric_version, "writing-rubric-v1"
                )
                scored_pairs.append((score, rv))

        rubrics = {rv for _, rv in scored_pairs}
        avg_score: float | None = None
        rubric_version: str | None = None
        warning: str | None = None
        if len(rubrics) == 1 and scored_pairs:
            rubric_version = next(iter(rubrics))
            avg_score = round(
                sum(s for s, _ in scored_pairs) / len(scored_pairs), 1
            )
        elif len(rubrics) > 1:
            warning = (
                "Multiple rubric versions exist across evaluated submissions; "
                "average_overall_score is omitted."
            )

        avg_wc = (
            round(sum(word_counts) / len(word_counts), 1) if word_counts else None
        )

        return WritingModuleMetrics(
            completed_submissions=completed_count,
            evaluated_submissions=evaluated_count,
            pending_feedback=pending_count,
            average_overall_score=avg_score,
            average_word_count=avg_wc,
            total_revision_submissions=len(revision_rows),
            rubric_version=rubric_version,
            comparability_warning=warning,
        )

    def _build_vocabulary_metrics(
        self, sub_rows, vocab_counts: dict[str, int]
    ) -> VocabularyModuleMetrics:
        submissions = [r.PracticeSubmission for r in sub_rows]
        completed_quizzes = len(submissions)
        quiz_scores = [
            score
            for s in submissions
            if (score := extract_submission_score(s)) is not None
        ]
        avg_quiz_score = (
            round(sum(quiz_scores) / len(quiz_scores), 1) if quiz_scores else None
        )
        learning = vocab_counts["learning"]
        reviewing = vocab_counts["reviewing"]
        mastered = vocab_counts["mastered"]
        return VocabularyModuleMetrics(
            unique_words_encountered=learning + reviewing + mastered,
            learning=learning,
            reviewing=reviewing,
            mastered=mastered,
            reviews_due=vocab_counts["due_now"],
            completed_daily_quizzes=completed_quizzes,
            average_quiz_score=avg_quiz_score,
        )

    async def get_streaks(self, user_id: UUID) -> ProgressStreaksResponse:
        user_state = await self.repository.get_user_state(user_id)
        if user_state is None:
            raise NotFoundError("Account not found.")
        onboarding_status, raw_tz = user_state
        if onboarding_status != "COMPLETED":
            raise ConflictError(
                "Complete onboarding to start learning.",
                code="ONBOARDING_REQUIRED",
            )

        now_utc = datetime.now(UTC)
        tz_name, local_today = resolve_local_today(raw_tz, now_utc)
        credited_dates = await self.repository.get_credited_dates(user_id)
        calc = self.streak_calculator.calculate(credited_dates, local_today)

        return ProgressStreaksResponse(
            timezone=tz_name,
            as_of_local_date=calc.as_of_local_date,
            current_streak_days=calc.current_streak_days,
            longest_streak_days=calc.longest_streak_days,
            last_active_local_date=calc.last_active_local_date,
            active_days_total=calc.active_days_total,
            streak_status=calc.streak_status,
            policy=StreakPolicy(),
        )

    async def get_activity_calendar(
        self,
        user_id: UUID,
        date_from: date,
        date_to: date,
        module: ModuleLiteral | None = None,
    ) -> ActivityCalendarResponse:
        if date_from > date_to:
            raise ValidationAppError(
                "The 'from' date must not be after the 'to' date.",
                code="INVALID_DATE_RANGE",
            )
        if (date_to - date_from).days + 1 > 366:
            raise ValidationAppError(
                "Date range cannot span more than 366 days.",
                code="DATE_RANGE_TOO_LARGE",
            )

        user_state = await self.repository.get_user_state(user_id)
        if user_state is None:
            raise NotFoundError("Account not found.")
        onboarding_status, raw_tz = user_state
        if onboarding_status != "COMPLETED":
            raise ConflictError(
                "Complete onboarding to start learning.",
                code="ONBOARDING_REQUIRED",
            )

        now_utc = datetime.now(UTC)
        tz_name, _ = resolve_local_today(raw_tz, now_utc)
        rows = await self.repository.get_activity_calendar_rows(
            user_id, date_from, date_to, module=module
        )

        by_day: dict[date, dict[str, object]] = {}
        for row in rows:
            d: date = row.practice_date
            mod: str = row.module
            count = int(row.completion_count or 0)
            secs = int(row.practice_seconds or 0)
            bucket = by_day.get(d)
            if bucket is None:
                bucket = {
                    "completion_count": 0,
                    "modules": set(),
                    "practice_seconds": 0,
                }
                by_day[d] = bucket
            bucket["completion_count"] = int(bucket["completion_count"]) + count
            bucket["practice_seconds"] = int(bucket["practice_seconds"]) + secs
            mod_set: set[str] = bucket["modules"]  # type: ignore[assignment]
            mod_set.add(mod)

        days: list[ActivityCalendarDayItem] = []
        total_completions = 0
        total_seconds = 0
        for d in sorted(by_day.keys()):
            bucket = by_day[d]
            c_count = int(bucket["completion_count"])
            p_secs = int(bucket["practice_seconds"])
            mod_set = bucket["modules"]  # type: ignore[assignment]
            ordered_mods = sorted(
                mod_set,
                key=lambda m: MODULE_ORDER.index(m) if m in MODULE_ORDER else 99,
            )
            days.append(
                ActivityCalendarDayItem(
                    date=d,
                    completion_count=c_count,
                    modules=ordered_mods,
                    practice_seconds=p_secs,
                )
            )
            total_completions += c_count
            total_seconds += p_secs

        return ActivityCalendarResponse(
            timezone=tz_name,
            date_from=date_from,
            date_to=date_to,
            module=module,
            active_days=len(days),
            total_completions=total_completions,
            total_seconds=total_seconds,
            days=days,
        )

    async def get_achievements(
        self,
        user_id: UUID,
        status: AchievementFilterStatus = "all",
    ) -> AchievementsResponse:
        from app.modules.progress.achievements import AchievementPolicy

        user_state = await self.repository.get_user_state(user_id)
        if user_state is None:
            raise NotFoundError("Account not found.")
        onboarding_status, raw_tz = user_state
        if onboarding_status != "COMPLETED":
            raise ConflictError(
                "Complete onboarding to start learning.",
                code="ONBOARDING_REQUIRED",
            )

        policy = AchievementPolicy(self.session)
        evidence = await policy.load_evidence(user_id, raw_tz)
        earned_rows = await self.repository.get_user_achievements(user_id)
        return policy.build_response(evidence, earned_rows, status_filter=status)

    async def get_activity_history(
        self,
        user_id: UUID,
        *,
        module: ModuleLiteral | None = None,
        cursor: str | None = None,
        limit: int = 20,
    ) -> ActivityHistoryResponse:
        cursor_ts: datetime | None = None
        cursor_id: UUID | None = None
        if cursor is not None:
            cursor_ts, cursor_id = decode_history_cursor(cursor)

        user_state = await self.repository.get_user_state(user_id)
        if user_state is None:
            raise NotFoundError("Account not found.")
        onboarding_status, _ = user_state
        if onboarding_status != "COMPLETED":
            raise ConflictError(
                "Complete onboarding to start learning.",
                code="ONBOARDING_REQUIRED",
            )

        rows = await self.repository.get_activity_history_rows(
            user_id,
            module=module,
            cursor_completed_at=cursor_ts,
            cursor_id=cursor_id,
            limit=limit,
        )
        has_more = len(rows) > limit
        page_rows = rows[:limit]

        items: list[ActivityHistoryItem] = []
        for row in page_rows:
            ac = row.ActivityCompletion
            sub: PracticeSubmission | None = row.PracticeSubmission
            mod: str = row.module
            source_sub_id = ac.source_submission_id
            eval_status = sub.evaluation_status if sub is not None else None
            score_val = extract_submission_score(sub) if sub is not None else None

            details_url: str | None = None
            if (
                source_sub_id is not None
                and sub is not None
                and mod in DETAILS_URL_PREFIX_BY_MODULE
            ):
                details_url = f"{DETAILS_URL_PREFIX_BY_MODULE[mod]}{source_sub_id}"

            items.append(
                ActivityHistoryItem(
                    completion_id=ac.id,
                    module=mod,
                    cycle=int(row.cycle),
                    day=row.content_day,
                    title=str(row.content_title),
                    completed_at=ac.completed_at,
                    local_practice_date=ac.local_practice_date,
                    practice_seconds=max(int(ac.duration_seconds or 0), 0),
                    source_submission_id=source_sub_id,
                    evaluation_status=eval_status,
                    score=score_val,
                    details_url=details_url,
                )
            )

        next_cursor: str | None = None
        if has_more and items:
            last = items[-1]
            next_cursor = encode_history_cursor(
                last.completed_at, last.completion_id
            )

        return ActivityHistoryResponse(
            items=items,
            pagination=ActivityHistoryPagination(
                next_cursor=next_cursor,
                has_more=has_more,
            ),
        )

    async def get_cefr_history(self, user_id: UUID) -> CefrHistoryResponse:
        user, rows = await self.repository.get_cefr_history_data(user_id)
        if user is None:
            raise NotFoundError("Account not found.")
        if user.onboarding_status != "COMPLETED":
            raise ConflictError(
                "Complete onboarding to start learning.",
                code="ONBOARDING_REQUIRED",
            )

        assessments: list[CefrAssessmentHistoryItem] = []
        for row in rows:
            attempt = row.AssessmentAttempt
            result_dict = (
                attempt.result if isinstance(attempt.result, dict) else {}
            )
            cefr = attempt.placement_cefr or result_dict.get("placement_cefr")
            if not isinstance(cefr, str) or not cefr.strip():
                continue
            conf = attempt.confidence or result_dict.get("confidence")
            rv_raw = (
                result_dict.get("rubric_version")
                or row.job_rubric_version
                or "placement-v1"
            )
            completed_at = (
                attempt.completed_at
                or attempt.submitted_at
                or attempt.started_at
            )
            assessments.append(
                CefrAssessmentHistoryItem(
                    assessment_id=attempt.id,
                    kind=attempt.kind,
                    completed_at=completed_at,
                    placement_cefr=cefr.strip(),
                    confidence=str(conf) if conf is not None else None,
                    rubric_version=str(rv_raw),
                )
            )

        current_cefr = user.current_cefr or (
            assessments[-1].placement_cefr if assessments else None
        )
        return CefrHistoryResponse(
            current_placement_cefr=current_cefr,
            certified=False,
            assessments=assessments,
        )








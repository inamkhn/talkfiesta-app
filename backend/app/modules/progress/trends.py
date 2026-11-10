"""Time-series performance trend query service for `/api/v1/progress/modules/{module}/trends`."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationAppError
from app.modules.practice.models import PracticeSubmission
from app.modules.progress.repository import ProgressRepository
from app.modules.progress.schemas import (
    ModuleLiteral,
    ModuleTrendResponse,
    TrendGranularity,
    TrendPoint,
)
from app.modules.progress.service import (
    extract_rubric_version,
    extract_speaking_wpm,
    extract_submission_score,
    extract_writing_word_count,
)

SPEAKING_METRICS = frozenset(
    {"overall_score", "grammar_score", "vocabulary_score", "approx_wpm"}
)
WRITING_METRICS = frozenset(
    {
        "overall_score",
        "grammar_score",
        "structure_score",
        "vocabulary_score",
        "coherence_score",
        "word_count",
    }
)
VOCABULARY_METRICS = frozenset(
    {"quiz_score", "mastered_count", "review_accuracy"}
)

PERMITTED_MODULE_METRICS: dict[str, frozenset[str]] = {
    "SPEAKING": SPEAKING_METRICS,
    "WRITING": WRITING_METRICS,
    "VOCABULARY": VOCABULARY_METRICS,
}

DEFAULT_CEFR_NOTE = (
    "A short-term trend does not establish a validated CEFR level change."
)


def _resolve_tz(tz_name: str | None) -> tuple[str, ZoneInfo]:
    candidate = (tz_name or "UTC").strip() or "UTC"
    try:
        return candidate, ZoneInfo(candidate)
    except ZoneInfoNotFoundError:
        return "UTC", ZoneInfo("UTC")


def _bucket_start(local_date: date, granularity: TrendGranularity) -> date:
    if granularity == "week":
        return local_date - timedelta(days=local_date.weekday())
    return local_date


def _extract_dimension_score(
    submission: PracticeSubmission, key: str
) -> float | None:
    if submission.evaluation_status != "COMPLETED":
        return None
    if not isinstance(submission.feedback, dict):
        return None
    scores = submission.feedback.get("scores")
    if not isinstance(scores, dict):
        return None
    val = scores.get(key)
    if isinstance(val, (int, float)) and not isinstance(val, bool):
        return float(val)
    return None


def _extract_review_accuracy_point(submission: PracticeSubmission) -> float | None:
    if submission.score is not None:
        return float(submission.score)
    if isinstance(submission.feedback, dict):
        correct = submission.feedback.get("correct")
        if isinstance(correct, bool):
            return 100.0 if correct else 0.0
    return None


class TrendQueryService:
    """Computes date-bucketed performance trends from stored evaluations and mastery records."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = ProgressRepository(session)

    async def get_trend(
        self,
        user_id: UUID,
        module: ModuleLiteral,
        metric: str,
        date_from: date | None = None,
        date_to: date | None = None,
        granularity: TrendGranularity = "week",
        rubric_version: str | None = None,
    ) -> ModuleTrendResponse:
        permitted = PERMITTED_MODULE_METRICS.get(module, frozenset())
        if metric not in permitted:
            raise ValidationAppError(
                f"Metric '{metric}' is not supported for module '{module}'.",
                code="INVALID_TREND_METRIC",
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

        _, tz = _resolve_tz(raw_tz)
        local_today = datetime.now(UTC).astimezone(tz).date()
        resolved_to = date_to if date_to is not None else local_today
        resolved_from = (
            date_from
            if date_from is not None
            else resolved_to - timedelta(days=29)
        )

        if resolved_from > resolved_to:
            raise ValidationAppError(
                "The 'from' date must not be after the 'to' date.",
                code="INVALID_DATE_RANGE",
            )
        if (resolved_to - resolved_from).days + 1 > 366:
            raise ValidationAppError(
                "Date range cannot span more than 366 days.",
                code="INVALID_DATE_RANGE",
            )

        if module == "SPEAKING":
            return await self._speaking_trend(
                user_id,
                metric,
                resolved_from,
                resolved_to,
                granularity,
                rubric_version,
                tz,
            )
        if module == "WRITING":
            return await self._writing_trend(
                user_id,
                metric,
                resolved_from,
                resolved_to,
                granularity,
                rubric_version,
                tz,
            )
        return await self._vocabulary_trend(
            user_id,
            metric,
            resolved_from,
            resolved_to,
            granularity,
            rubric_version,
            tz,
        )

    async def _speaking_trend(
        self,
        user_id: UUID,
        metric: str,
        date_from: date,
        date_to: date,
        granularity: TrendGranularity,
        requested_rubric: str | None,
        tz: ZoneInfo,
    ) -> ModuleTrendResponse:
        rows = await self.repository.get_trend_submissions(
            user_id, "RECORDED_SPEAKING", baseline_only=False
        )
        notes = [DEFAULT_CEFR_NOTE]

        if metric == "approx_wpm":
            notes.append(
                "approx_wpm reflects approximate recording pace and is not a speaking fluency score."
            )
            samples: list[tuple[date, float]] = []
            for row in rows:
                sub: PracticeSubmission = row.PracticeSubmission
                if sub.evaluation_status != "COMPLETED":
                    continue
                ts = sub.submitted_at or sub.created_at
                local_d = ts.astimezone(tz).date()
                if not (date_from <= local_d <= date_to):
                    continue
                wpm = extract_speaking_wpm(sub)
                if wpm is not None:
                    samples.append((local_d, wpm))
            points = self._aggregate_mean_points(samples, granularity)
            return ModuleTrendResponse(
                module="SPEAKING",
                metric=metric,
                granularity=granularity,
                rubric_version=None,
                aggregation="MEAN_OF_GROUNDED_SUBMISSIONS",
                unit="WORDS_PER_MINUTE",
                points=points,
                notes=notes,
            )

        # Rubric-scored speaking metric
        scored_rows: list[tuple[date, float, str]] = []
        for row in rows:
            sub = row.PracticeSubmission
            if sub.evaluation_status != "COMPLETED":
                continue
            ts = sub.submitted_at or sub.created_at
            local_d = ts.astimezone(tz).date()
            if not (date_from <= local_d <= date_to):
                continue
            if metric == "overall_score":
                val = extract_submission_score(sub)
            elif metric == "grammar_score":
                val = _extract_dimension_score(sub, "grammar")
            else:
                val = _extract_dimension_score(sub, "vocabulary")
            if val is None:
                continue
            rv = extract_rubric_version(
                sub, row.job_rubric_version, "speaking-feedback-v1"
            )
            scored_rows.append((local_d, val, rv))

        chosen_rv, filtered_samples, extra_note = self._filter_by_rubric(
            scored_rows, requested_rubric, default_rubric="speaking-feedback-v1"
        )
        if extra_note:
            notes.append(extra_note)

        points = self._aggregate_mean_points(filtered_samples, granularity)
        return ModuleTrendResponse(
            module="SPEAKING",
            metric=metric,
            granularity=granularity,
            rubric_version=chosen_rv,
            aggregation="MEAN_OF_EVALUATED_SUBMISSIONS",
            unit="SCORE_0_100",
            points=points,
            notes=notes,
        )

    async def _writing_trend(
        self,
        user_id: UUID,
        metric: str,
        date_from: date,
        date_to: date,
        granularity: TrendGranularity,
        requested_rubric: str | None,
        tz: ZoneInfo,
    ) -> ModuleTrendResponse:
        # Baseline submissions only (revision_number == 1), deduplicated to first per content_item_id
        rows = await self.repository.get_trend_submissions(
            user_id, "WRITING", baseline_only=True
        )
        notes = [DEFAULT_CEFR_NOTE]
        seen_activities: set[UUID] = set()
        first_rows = []
        for row in rows:
            sub: PracticeSubmission = row.PracticeSubmission
            if sub.content_item_id in seen_activities:
                continue
            seen_activities.add(sub.content_item_id)
            first_rows.append(row)

        if metric == "word_count":
            samples: list[tuple[date, float]] = []
            for row in first_rows:
                sub = row.PracticeSubmission
                ts = sub.submitted_at or sub.created_at
                local_d = ts.astimezone(tz).date()
                if not (date_from <= local_d <= date_to):
                    continue
                wc = extract_writing_word_count(sub)
                if wc is not None:
                    samples.append((local_d, float(wc)))
            points = self._aggregate_mean_points(samples, granularity)
            return ModuleTrendResponse(
                module="WRITING",
                metric=metric,
                granularity=granularity,
                rubric_version=None,
                aggregation="MEAN_OF_FIRST_SUBMISSION_PER_REQUIRED_ACTIVITY",
                unit="WORD_COUNT",
                points=points,
                notes=notes,
            )

        dim_map = {
            "grammar_score": "grammar",
            "structure_score": "structure",
            "vocabulary_score": "vocabulary",
            "coherence_score": "coherence",
        }
        scored_rows: list[tuple[date, float, str]] = []
        for row in first_rows:
            sub = row.PracticeSubmission
            if sub.evaluation_status != "COMPLETED":
                continue
            ts = sub.submitted_at or sub.created_at
            local_d = ts.astimezone(tz).date()
            if not (date_from <= local_d <= date_to):
                continue
            if metric == "overall_score":
                val = extract_submission_score(sub)
            else:
                val = _extract_dimension_score(sub, dim_map[metric])
            if val is None:
                continue
            rv = extract_rubric_version(
                sub, row.job_rubric_version, "writing-rubric-v1"
            )
            scored_rows.append((local_d, val, rv))

        chosen_rv, filtered_samples, extra_note = self._filter_by_rubric(
            scored_rows, requested_rubric, default_rubric="writing-rubric-v1"
        )
        if extra_note:
            notes.append(extra_note)

        points = self._aggregate_mean_points(filtered_samples, granularity)
        return ModuleTrendResponse(
            module="WRITING",
            metric=metric,
            granularity=granularity,
            rubric_version=chosen_rv,
            aggregation="MEAN_OF_FIRST_EVALUATED_SUBMISSION_PER_REQUIRED_ACTIVITY",
            unit="SCORE_0_100",
            points=points,
            notes=notes,
        )

    async def _vocabulary_trend(
        self,
        user_id: UUID,
        metric: str,
        date_from: date,
        date_to: date,
        granularity: TrendGranularity,
        requested_rubric: str | None,
        tz: ZoneInfo,
    ) -> ModuleTrendResponse:
        notes = [DEFAULT_CEFR_NOTE]

        if metric == "mastered_count":
            notes.append(
                "mastered_count reflects cumulative_first_mastered words by stored mastered_at timestamps."
            )
            timestamps = await self.repository.get_mastered_vocabulary_timestamps(
                user_id
            )
            local_dates = [ts.astimezone(tz).date() for ts in timestamps]
            prior_cumulative = sum(1 for d in local_dates if d < date_from)
            in_window = [d for d in local_dates if date_from <= d <= date_to]

            buckets: dict[date, int] = {}
            for d in in_window:
                b_start = _bucket_start(d, granularity)
                buckets[b_start] = buckets.get(b_start, 0) + 1

            points: list[TrendPoint] = []
            running_total = prior_cumulative
            for b_start in sorted(buckets.keys()):
                count_in_bucket = buckets[b_start]
                running_total += count_in_bucket
                points.append(
                    TrendPoint(
                        period_start=b_start,
                        value=float(running_total),
                        sample_size=count_in_bucket,
                    )
                )

            return ModuleTrendResponse(
                module="VOCABULARY",
                metric=metric,
                granularity=granularity,
                rubric_version=None,
                aggregation="CUMULATIVE_FIRST_MASTERED",
                unit="WORD_COUNT",
                points=points,
                notes=notes,
            )

        if metric == "review_accuracy":
            rows = await self.repository.get_trend_submissions(
                user_id, "VOCAB_REVIEW", baseline_only=False
            )
            samples: list[tuple[date, float]] = []
            for row in rows:
                sub: PracticeSubmission = row.PracticeSubmission
                ts = sub.submitted_at or sub.created_at
                local_d = ts.astimezone(tz).date()
                if not (date_from <= local_d <= date_to):
                    continue
                acc = _extract_review_accuracy_point(sub)
                if acc is not None:
                    samples.append((local_d, acc))
            points = self._aggregate_mean_points(samples, granularity)
            return ModuleTrendResponse(
                module="VOCABULARY",
                metric=metric,
                granularity=granularity,
                rubric_version=None,
                aggregation="MEAN_OF_SUBMITTED_VOCAB_REVIEWS",
                unit="PERCENT_0_100",
                points=points,
                notes=notes,
            )

        # metric == "quiz_score"
        rows = await self.repository.get_trend_submissions(
            user_id, "VOCAB_QUIZ", baseline_only=False
        )
        scored_rows: list[tuple[date, float, str]] = []
        for row in rows:
            sub = row.PracticeSubmission
            score = extract_submission_score(sub)
            if score is None:
                continue
            ts = sub.submitted_at or sub.created_at
            local_d = ts.astimezone(tz).date()
            if not (date_from <= local_d <= date_to):
                continue
            rv = extract_rubric_version(
                sub, row.job_rubric_version, "vocab-objective-v1"
            )
            scored_rows.append((local_d, score, rv))

        chosen_rv, filtered_samples, extra_note = self._filter_by_rubric(
            scored_rows, requested_rubric, default_rubric="vocab-objective-v1"
        )
        if extra_note:
            notes.append(extra_note)
        points = self._aggregate_mean_points(filtered_samples, granularity)
        return ModuleTrendResponse(
            module="VOCABULARY",
            metric=metric,
            granularity=granularity,
            rubric_version=chosen_rv,
            aggregation="MEAN_OF_EVALUATED_QUIZ_SUBMISSIONS",
            unit="SCORE_0_100",
            points=points,
            notes=notes,
        )

    @staticmethod
    def _filter_by_rubric(
        scored_rows: list[tuple[date, float, str]],
        requested_rubric: str | None,
        *,
        default_rubric: str,
    ) -> tuple[str | None, list[tuple[date, float]], str | None]:
        if requested_rubric is not None:
            target = requested_rubric.strip()
            matched = [(d, val) for d, val, rv in scored_rows if rv == target]
            if not matched and scored_rows:
                return (
                    target,
                    [],
                    f"No evaluated submissions matched rubric_version '{target}'.",
                )
            return target, matched, None

        if not scored_rows:
            return default_rubric, [], None

        # Default to most recent compatible rubric version
        latest_rubric = scored_rows[-1][2]
        distinct_rubrics = {rv for _, _, rv in scored_rows}
        matched = [
            (d, val) for d, val, rv in scored_rows if rv == latest_rubric
        ]
        note: str | None = None
        if len(distinct_rubrics) > 1:
            note = (
                f"Filtered to rubric_version '{latest_rubric}' to avoid mixing "
                "incompatible rubric versions."
            )
        return latest_rubric, matched, note

    @staticmethod
    def _aggregate_mean_points(
        samples: list[tuple[date, float]],
        granularity: TrendGranularity,
    ) -> list[TrendPoint]:
        buckets: dict[date, list[float]] = {}
        for local_d, val in samples:
            b_start = _bucket_start(local_d, granularity)
            buckets.setdefault(b_start, []).append(val)

        points: list[TrendPoint] = []
        for b_start in sorted(buckets.keys()):
            vals = buckets[b_start]
            points.append(
                TrendPoint(
                    period_start=b_start,
                    value=round(sum(vals) / len(vals), 1),
                    sample_size=len(vals),
                )
            )
        return points


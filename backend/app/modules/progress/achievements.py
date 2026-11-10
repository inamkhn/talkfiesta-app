"""Versioned achievement catalog and idempotent internal award policy (V4)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.gamification.models import UserAchievement
from app.modules.progress.repository import ProgressRepository
from app.modules.progress.schemas import (
    AchievementFilterStatus,
    AchievementItem,
    AchievementProgress,
    AchievementsResponse,
)
from app.modules.progress.service import (
    extract_rubric_version,
    extract_submission_score,
    resolve_local_today,
)
from app.modules.progress.streaks import StreakCalculator

COMPATIBLE_PERFECT_SCORE_RUBRICS = frozenset(
    {
        "speaking-feedback-v1",
        "writing-rubric-v1",
        "writing-v1",
        "vocab-context-v1",
        "vocab-objective-v1",
    }
)


@dataclass(frozen=True)
class AchievementDefinition:
    key: str
    title: str
    description: str
    default_target: int


ACHIEVEMENT_CATALOG: tuple[AchievementDefinition, ...] = (
    AchievementDefinition(
        key="FIRST_SPEAKING_DAY",
        title="First Words",
        description="Complete your first speaking activity.",
        default_target=1,
    ),
    AchievementDefinition(
        key="SEVEN_DAY_STREAK",
        title="Week Warrior",
        description="Practice on seven consecutive local dates.",
        default_target=7,
    ),
    AchievementDefinition(
        key="FIRST_PERFECT_SCORE",
        title="Perfect Practice",
        description="Earn 100 on a compatible final graded exercise.",
        default_target=1,
    ),
    AchievementDefinition(
        key="CYCLE_COMPLETE",
        title="Cycle Finisher",
        description="Complete all required modules in one 21-day cycle.",
        default_target=63,
    ),
    AchievementDefinition(
        key="TEN_WORDS_MASTERED",
        title="Word Builder",
        description="Master 10 vocabulary words.",
        default_target=10,
    ),
)


@dataclass(frozen=True)
class AchievementEvidence:
    speaking_completions: int
    longest_streak_days: int
    perfect_score_count: int
    cycle_completed: bool
    cycle_current_activities: int
    cycle_target_activities: int
    mastered_words: int


class AchievementCatalog:
    """Versioned badge catalog and progress calculation."""

    definitions: tuple[AchievementDefinition, ...] = ACHIEVEMENT_CATALOG

    def compute_progress(
        self, key: str, evidence: AchievementEvidence
    ) -> tuple[int, int, bool]:
        """Return `(current, target, is_eligible)` for badge `key`."""
        if key == "FIRST_SPEAKING_DAY":
            target = 1
            current = min(evidence.speaking_completions, target)
            return current, target, evidence.speaking_completions >= target

        if key == "SEVEN_DAY_STREAK":
            target = 7
            current = min(evidence.longest_streak_days, target)
            return current, target, evidence.longest_streak_days >= target

        if key == "FIRST_PERFECT_SCORE":
            target = 1
            current = min(evidence.perfect_score_count, target)
            return current, target, evidence.perfect_score_count >= target

        if key == "CYCLE_COMPLETE":
            target = evidence.cycle_target_activities or 63
            if evidence.cycle_completed:
                return target, target, True
            current = min(evidence.cycle_current_activities, target)
            return current, target, False

        if key == "TEN_WORDS_MASTERED":
            target = 10
            current = min(evidence.mastered_words, target)
            return current, target, evidence.mastered_words >= target

        return 0, 1, False


class AchievementPolicy:
    """Internal-only, idempotent achievement evaluator and awarder."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = ProgressRepository(session)
        self.catalog = AchievementCatalog()
        self.streak_calculator = StreakCalculator()

    async def load_evidence(
        self, user_id: UUID, tz_name: str = "UTC"
    ) -> AchievementEvidence:
        now_utc = datetime.now(UTC)
        _, local_today = resolve_local_today(tz_name, now_utc)

        credited_dates = await self.repository.get_credited_dates(user_id)
        streak = self.streak_calculator.calculate(credited_dates, local_today)

        speaking_completions = await self.repository.count_module_completions(
            user_id, "SPEAKING"
        )
        vocab_counts = await self.repository.get_vocabulary_counts(user_id, now_utc)

        completed_sub_rows = await self.repository.get_completed_submissions_for_badges(
            user_id
        )
        perfect_count = 0
        for row in completed_sub_rows:
            sub = row.PracticeSubmission
            score = extract_submission_score(sub)
            if score is None or score < 100.0:
                continue
            default_rv = (
                "speaking-feedback-v1"
                if sub.mode == "RECORDED_SPEAKING"
                else (
                    "writing-rubric-v1"
                    if sub.mode == "WRITING"
                    else "vocab-objective-v1"
                )
            )
            rv = extract_rubric_version(sub, row.job_rubric_version, default_rv)
            if rv in COMPATIBLE_PERFECT_SCORE_RUBRICS:
                perfect_count += 1

        (
            cycle_completed,
            cycle_current,
            cycle_target,
        ) = await self.repository.get_cycle_completion_progress(user_id)

        return AchievementEvidence(
            speaking_completions=speaking_completions,
            longest_streak_days=streak.longest_streak_days,
            perfect_score_count=perfect_count,
            cycle_completed=cycle_completed,
            cycle_current_activities=cycle_current,
            cycle_target_activities=cycle_target,
            mastered_words=vocab_counts["mastered"],
        )

    async def evaluate_and_award(
        self,
        user_id: UUID,
        event_id: UUID | str | None = None,
    ) -> list[str]:
        """Idempotently award any newly satisfied badges for `user_id`."""
        user_state = await self.repository.get_user_state(user_id)
        if user_state is None:
            return []
        _, raw_tz = user_state
        evidence = await self.load_evidence(user_id, raw_tz)
        existing = await self.repository.get_user_achievements(user_id)
        existing_keys = {row.achievement_key for row in existing}

        awarded: list[str] = []
        now_utc = datetime.now(UTC)
        for definition in self.catalog.definitions:
            if definition.key in existing_keys:
                continue
            current, target, eligible = self.catalog.compute_progress(
                definition.key, evidence
            )
            if not eligible:
                continue
            context: dict[str, object] = {
                "current": current,
                "target": target,
            }
            if event_id is not None:
                context["event_id"] = str(event_id)

            stmt = (
                pg_insert(UserAchievement)
                .values(
                    user_id=user_id,
                    achievement_key=definition.key,
                    context=context,
                    earned_at=now_utc,
                )
                .on_conflict_do_nothing(
                    index_elements=["user_id", "achievement_key"]
                )
            )
            result = await self.session.execute(stmt)
            if result.rowcount and result.rowcount > 0:
                awarded.append(definition.key)

        return awarded

    def build_response(
        self,
        evidence: AchievementEvidence,
        earned_rows: list[UserAchievement],
        status_filter: AchievementFilterStatus = "all",
    ) -> AchievementsResponse:
        earned_by_key = {row.achievement_key: row for row in earned_rows}
        all_items: list[AchievementItem] = []
        earned_count = 0

        for definition in self.catalog.definitions:
            current, target, _ = self.catalog.compute_progress(
                definition.key, evidence
            )
            earned_row = earned_by_key.get(definition.key)
            if earned_row is not None:
                earned_count += 1
                item = AchievementItem(
                    key=definition.key,
                    title=definition.title,
                    description=definition.description,
                    status="EARNED",
                    earned_at=earned_row.earned_at,
                    progress=AchievementProgress(current=target, target=target),
                )
            else:
                item = AchievementItem(
                    key=definition.key,
                    title=definition.title,
                    description=definition.description,
                    status="LOCKED",
                    earned_at=None,
                    progress=AchievementProgress(current=current, target=target),
                )
            all_items.append(item)

        if status_filter == "earned":
            filtered = [item for item in all_items if item.status == "EARNED"]
        elif status_filter == "locked":
            filtered = [item for item in all_items if item.status == "LOCKED"]
        else:
            filtered = all_items

        return AchievementsResponse(
            earned_count=earned_count,
            available_count=len(self.catalog.definitions),
            achievements=filtered,
        )


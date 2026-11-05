"""Fixed-interval spaced repetition policy for TalkFiesta Vocabulary (V4).

Schedule milestones (when introduced on Day 1):
- Introduction (Day 1) -> Review 1 on Day 2 (+1 day)
- Review 1 (mastery 1 -> 2) -> Review 2 on Day 4 (+2 days)
- Review 2 (mastery 2 -> 3) -> Review 3 on Day 8 (+4 days)
- Review 3 (mastery 3 -> 4) -> Review 4 on Day 15 (+7 days)
- Review 4 (mastery 4 -> 5) -> MASTERED (no further scheduled review)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

REVIEW_INTERVALS_BY_MASTERY: dict[int, int] = {
    1: 1,
    2: 2,
    3: 4,
    4: 7,
}


@dataclass(frozen=True)
class SpacedRepetitionUpdate:
    status: Literal["LEARNING", "REVIEWING", "MASTERED"]
    previous_mastery_level: int
    mastery_level: int
    review_interval_days: int | None
    next_review_at: datetime | None
    last_reviewed_at: datetime
    mastered_at: datetime | None
    times_practiced: int


def initial_word_schedule(now: datetime) -> tuple[str, int, int, datetime]:
    """Return (status, mastery_level, review_interval_days, next_review_at) on first study."""
    interval = REVIEW_INTERVALS_BY_MASTERY[1]
    return "LEARNING", 1, interval, now + timedelta(days=interval)


def apply_review_outcome(
    *,
    current_mastery_level: int,
    times_practiced: int,
    correct: bool,
    now: datetime,
    existing_mastered_at: datetime | None = None,
) -> SpacedRepetitionUpdate:
    """Compute the next spaced-repetition state after a due-word review."""
    prev_level = max(1, min(5, current_mastery_level))
    next_practiced = max(0, times_practiced) + 1

    if correct:
        new_level = min(5, prev_level + 1)
        if new_level >= 5:
            return SpacedRepetitionUpdate(
                status="MASTERED",
                previous_mastery_level=prev_level,
                mastery_level=5,
                review_interval_days=None,
                next_review_at=None,
                last_reviewed_at=now,
                mastered_at=existing_mastered_at or now,
                times_practiced=next_practiced,
            )
        interval = REVIEW_INTERVALS_BY_MASTERY[new_level]
        return SpacedRepetitionUpdate(
            status="REVIEWING",
            previous_mastery_level=prev_level,
            mastery_level=new_level,
            review_interval_days=interval,
            next_review_at=now + timedelta(days=interval),
            last_reviewed_at=now,
            mastered_at=None,
            times_practiced=next_practiced,
        )

    # Incorrect review: step back one level (minimum 1) and retry in 1 day.
    fallback_level = max(1, prev_level - 1)
    retry_interval = REVIEW_INTERVALS_BY_MASTERY[1]
    status: Literal["LEARNING", "REVIEWING"] = (
        "LEARNING" if fallback_level == 1 else "REVIEWING"
    )
    return SpacedRepetitionUpdate(
        status=status,
        previous_mastery_level=prev_level,
        mastery_level=fallback_level,
        review_interval_days=retry_interval,
        next_review_at=now + timedelta(days=retry_interval),
        last_reviewed_at=now,
        mastered_at=None,
        times_practiced=next_practiced,
    )


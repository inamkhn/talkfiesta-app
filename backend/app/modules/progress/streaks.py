"""Deterministic streak calculation from credited local practice dates."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal

StreakStatus = Literal[
    "ACTIVE_TODAY",
    "ACTIVE_FROM_YESTERDAY",
    "BROKEN",
    "NO_ACTIVITY",
]


@dataclass(frozen=True)
class StreakCalculation:
    as_of_local_date: date
    current_streak_days: int
    longest_streak_days: int
    last_active_local_date: date | None
    active_days_total: int
    streak_status: StreakStatus


class StreakCalculator:
    """Pure, deterministic streak calculator over distinct credited local dates."""

    def calculate(
        self, credited_dates: set[date], today: date
    ) -> StreakCalculation:
        valid_dates = sorted(d for d in credited_dates if d <= today)
        if not valid_dates:
            return StreakCalculation(
                as_of_local_date=today,
                current_streak_days=0,
                longest_streak_days=0,
                last_active_local_date=None,
                active_days_total=0,
                streak_status="NO_ACTIVITY",
            )

        date_set = set(valid_dates)
        last_active = valid_dates[-1]
        active_days_total = len(valid_dates)

        # Longest streak across all contiguous date islands
        longest = 0
        current_run = 0
        prev_day: date | None = None
        for d in valid_dates:
            if prev_day is not None and d == prev_day + timedelta(days=1):
                current_run += 1
            else:
                current_run = 1
            longest = max(longest, current_run)
            prev_day = d

        # Current streak anchored at today or yesterday (0 grace days)
        yesterday = today - timedelta(days=1)
        if today in date_set:
            anchor: date | None = today
            status: StreakStatus = "ACTIVE_TODAY"
        elif yesterday in date_set:
            anchor = yesterday
            status = "ACTIVE_FROM_YESTERDAY"
        else:
            anchor = None
            status = "BROKEN"

        current_streak = 0
        if anchor is not None:
            cursor = anchor
            while cursor in date_set:
                current_streak += 1
                cursor -= timedelta(days=1)

        return StreakCalculation(
            as_of_local_date=today,
            current_streak_days=current_streak,
            longest_streak_days=longest,
            last_active_local_date=last_active,
            active_days_total=active_days_total,
            streak_status=status,
        )


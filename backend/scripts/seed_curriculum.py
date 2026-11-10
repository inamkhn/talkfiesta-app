"""Seed published 21-day curriculum lessons and vocabulary words across A1-C2."""

from __future__ import annotations

from app.infrastructure.database import model_registry  # noqa: F401
from app.infrastructure.database.sync_session import SyncSessionLocal
from app.modules.content.seed import seed_curriculum_sync


def main() -> None:
    with SyncSessionLocal() as session:
        inserted = seed_curriculum_sync(session)
    print(f"Seeded 21-day curriculum content (inserted={inserted}).")


if __name__ == "__main__":
    main()


"""Seed published initial placement assessment questions (placement-bank-v1)."""

from __future__ import annotations

from app.infrastructure.database import model_registry  # noqa: F401
from app.infrastructure.database.sync_session import SyncSessionLocal
from app.modules.content.seed import seed_assessment_bank_sync


def main() -> None:
    with SyncSessionLocal() as session:
        inserted = seed_assessment_bank_sync(session)
    print(f"Seeded assessment question bank (inserted={inserted}).")


if __name__ == "__main__":
    main()


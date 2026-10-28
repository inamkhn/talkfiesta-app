"""Declarative base, naming conventions and shared metadata.

There is exactly one ``Base`` for the whole application. Every ORM model
imports it from here, and Alembic discovers the models through
``app.infrastructure.database.model_registry``.

PostgreSQL is authoritative: UUID primary keys, timezone-aware timestamps and
``JSON`` columns as currently shipped. Column-level ``default=`` values are
ORM defaults and do not exist in the database DDL; only ``server_default``
creates a database default.
"""

from __future__ import annotations

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

# Deterministic constraint names keep Alembic autogenerate diffs stable.
# Constraints that need a project-specific name pass it explicitly instead.
NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Shared declarative base for all mapped classes."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)

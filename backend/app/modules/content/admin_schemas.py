"""Bounded pilot requests and explicit admin batch projections."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CreateBatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cefr_level: Literal["B1"] = "B1"
    cycle: Literal[1] = 1
    module: Literal["VOCABULARY"] = "VOCABULARY"
    goal_variant: Literal["GENERAL"] = "GENERAL"
    day_start: int = Field(ge=1, le=21, strict=True)
    day_end: int = Field(ge=1, le=21, strict=True)
    release_key: str = Field(
        default="B1-C1-GENERAL-VOCABULARY-v1",
        max_length=60,
        pattern=r"^B1-C1-GENERAL-VOCABULARY-v[1-9][0-9]*$",
    )
    dry_run: bool = Field(default=False, strict=True)

    @model_validator(mode="after")
    def bounded_days(self):
        if not 0 <= self.day_end - self.day_start < 5:
            raise ValueError("Choose one to five consecutive days in ascending order.")
        return self


class ChildProgress(BaseModel):
    job_id: UUID
    day: int
    status: str
    stage: str
    attempts: int
    error_code: str | None
    lesson_id: UUID | None = None
    item_status: str | None = None
    provider_calls_reserved: int = 0
    remaining_provider_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0


class BatchProgress(BaseModel):
    generation_batch_key: str
    parent_job_id: UUID
    status: str
    release_key: str
    dry_run: bool
    child_job_count: int
    children: list[ChildProgress]


class RetryBatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    child_job_ids: list[UUID] = Field(min_length=1, max_length=5)
    reason: str = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def unique_selection(self):
        if (
            len(set(self.child_job_ids)) != len(self.child_job_ids)
            or not self.reason.strip()
        ):
            raise ValueError("Select distinct jobs and provide a reason.")
        return self

"""Public profile contracts; account security fields cannot be patched."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator


class UserProfile(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    display_name: str | None
    profile: dict[str, JsonValue]
    preferences: dict[str, JsonValue]
    role: str
    onboarding_status: str
    email_verified_at: datetime | None


class UpdateProfileRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_name: str | None = Field(default=None, max_length=100)
    profile: dict[str, JsonValue] = Field(
        default_factory=dict,
        description="Merge these top-level keys into the existing profile. Nested values are replaced.",
    )
    preferences: dict[str, JsonValue] = Field(
        default_factory=dict,
        description="Merge these top-level keys into existing preferences. Nested values are replaced.",
    )

    @field_validator("display_name")
    @classmethod
    def normalize_display_name(cls, value: str | None) -> str | None:
        """An explicit null or blank name clears the optional display name."""
        return value.strip() or None if value is not None else None

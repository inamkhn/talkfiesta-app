"""Assessment audio upload contracts."""

import base64
import binascii
from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CreateAudioUpload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    purpose: Literal["ASSESSMENT"]
    assessment_response_id: UUID
    content_type: Literal[
        "audio/webm", "audio/ogg", "audio/wav", "audio/mpeg", "audio/mp4"
    ]
    size_bytes: int = Field(gt=0, strict=True)
    checksum_sha256: str = Field(min_length=44, max_length=44)

    @field_validator("checksum_sha256")
    @classmethod
    def valid_checksum(cls, value: str) -> str:
        try:
            decoded = base64.b64decode(value, validate=True)
        except binascii.Error as exc:
            raise ValueError(
                "Use the base64-encoded SHA-256 digest of the audio bytes."
            ) from exc
        if len(decoded) != 32 or base64.b64encode(decoded).decode() != value:
            raise ValueError("Use a canonical base64 SHA-256 digest.")
        return value


class AudioUploadCreated(BaseModel):
    upload_id: UUID
    upload_url: str
    method: Literal["PUT"] = "PUT"
    headers: dict[str, str]
    expires_at: datetime


class AudioUploadConfirmed(BaseModel):
    upload_id: UUID
    assessment_response_id: UUID
    status: Literal["VERIFIED"] = "VERIFIED"
    size_bytes: int
    duration_seconds: Decimal

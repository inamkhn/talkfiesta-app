"""Private S3 audio uploads using scoped SigV4 URLs and bounded downloads."""

import base64
import hashlib
from functools import lru_cache

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from app.core.config import settings
from app.core.exceptions import (
    ConflictError,
    ServiceUnavailableError,
    ValidationAppError,
)


def require_storage() -> None:
    if not settings.s3_bucket:
        raise ServiceUnavailableError("Audio storage is not configured.")
    if (
        not 1 <= settings.audio_upload_url_seconds <= 900
        or settings.audio_retention_days < 1
    ):
        raise ServiceUnavailableError("Audio storage settings are invalid.")


@lru_cache
def client():
    require_storage()
    return boto3.client(
        "s3",
        region_name=settings.s3_region,
        config=Config(
            signature_version="s3v4",
            connect_timeout=5,
            read_timeout=15,
            retries={"max_attempts": 2, "mode": "standard"},
        ),
    )


def presign(key: str, content_type: str, size: int, checksum: str) -> str:
    try:
        return client().generate_presigned_url(
            "put_object",
            Params={
                "Bucket": settings.s3_bucket,
                "Key": key,
                "ContentType": content_type,
                "ContentLength": size,
                "ChecksumSHA256": checksum,
                "IfNoneMatch": "*",
            },
            ExpiresIn=settings.audio_upload_url_seconds,
            HttpMethod="PUT",
        )
    except (BotoCoreError, ClientError) as exc:
        raise ServiceUnavailableError(
            "Audio storage is temporarily unavailable."
        ) from exc


def read_audio(key: str, content_type: str, size: int, checksum: str) -> bytes:
    require_storage()
    if not 0 < size <= settings.audio_max_bytes:
        raise ValidationAppError("The audio exceeds the configured size limit.")
    try:
        obj = client().get_object(Bucket=settings.s3_bucket, Key=key)
        stream = obj["Body"]
        try:
            if obj["ContentLength"] != size or obj.get("ContentType") != content_type:
                raise ValidationAppError(
                    "Uploaded size or content type does not match the upload request."
                )
            data = stream.read(size + 1)
        finally:
            stream.close()
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") in ("NoSuchKey", "404"):
            raise ConflictError(
                "Upload the audio file before confirming.", code="UPLOAD_NOT_FOUND"
            ) from exc
        raise ServiceUnavailableError(
            "Audio storage is temporarily unavailable."
        ) from exc
    except BotoCoreError as exc:
        raise ServiceUnavailableError(
            "Audio storage is temporarily unavailable."
        ) from exc
    if (
        len(data) != size
        or base64.b64encode(hashlib.sha256(data).digest()).decode() != checksum
    ):
        raise ValidationAppError("The uploaded audio checksum or length is invalid.")
    return data

"""Bounded audio decoding; never infer usability from the file's MIME label."""

import json
import shutil
import subprocess
import tempfile
from decimal import Decimal
from pathlib import Path

from app.core.config import settings
from app.core.exceptions import ServiceUnavailableError, ValidationAppError

FORMATS = {
    "audio/webm": "matroska",
    "audio/ogg": "ogg",
    "audio/wav": "wav",
    "audio/mpeg": "mp3",
    "audio/mp4": "mov",
}


def require_decoder() -> None:
    if not shutil.which(settings.ffmpeg_path) or not shutil.which(
        settings.ffprobe_path
    ):
        raise ServiceUnavailableError("Audio verification requires FFmpeg and ffprobe.")
    if not 1 <= settings.audio_max_duration_seconds <= 600:
        raise ServiceUnavailableError("Audio duration settings are invalid.")


def inspect_audio(data: bytes, content_type: str) -> Decimal:
    require_decoder()
    with tempfile.TemporaryDirectory(prefix="talkfiesta-audio-") as directory:
        source, decoded = Path(directory) / "upload", Path(directory) / "decoded.pcm"
        source.write_bytes(data)
        input_args = [
            "-protocol_whitelist",
            "file,pipe",
            "-f",
            FORMATS[content_type],
            "-i",
            str(source),
        ]
        options = {"stderr": subprocess.DEVNULL, "timeout": 30}
        try:
            result = subprocess.run(
                [
                    settings.ffprobe_path,
                    "-v",
                    "error",
                    *input_args,
                    "-show_entries",
                    "stream=codec_type,channels",
                    "-of",
                    "json",
                ],
                stdout=subprocess.PIPE,
                check=True,
                **options,
            )
            streams = json.loads(result.stdout).get("streams", [])
            if (
                len(streams) != 1
                or streams[0].get("codec_type") != "audio"
                or not 1 <= streams[0].get("channels", 0) <= 2
            ):
                raise ValidationAppError(
                    "Upload a mono or stereo audio-only recording."
                )
            subprocess.run(
                [
                    settings.ffmpeg_path,
                    "-nostdin",
                    "-v",
                    "error",
                    "-xerror",
                    "-threads",
                    "1",
                    *input_args,
                    "-map",
                    "0:a:0",
                    "-t",
                    str(settings.audio_max_duration_seconds + 1),
                    "-ac",
                    "1",
                    "-ar",
                    "16000",
                    "-f",
                    "s16le",
                    str(decoded),
                ],
                stdout=subprocess.DEVNULL,
                check=True,
                **options,
            )
        except subprocess.TimeoutExpired as exc:
            raise ValidationAppError(
                "Audio decoding exceeded the allowed processing time."
            ) from exc
        except (subprocess.CalledProcessError, json.JSONDecodeError) as exc:
            raise ValidationAppError(
                "The recording is not valid decodable audio of the declared type."
            ) from exc
        except OSError as exc:
            raise ServiceUnavailableError(
                "Audio verification is temporarily unavailable."
            ) from exc
        duration = Decimal(decoded.stat().st_size) / Decimal(32000)
        if not Decimal("0.5") <= duration <= settings.audio_max_duration_seconds:
            raise ValidationAppError(
                f"Audio must be between 0.5 and {settings.audio_max_duration_seconds} seconds."
            )
        return duration.quantize(Decimal("0.01"))

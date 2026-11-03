"""Local configuration checks only: no connections, paid calls, or secret output."""

import platform
import shutil


def main() -> None:
    try:
        from app.core.config import settings
    except Exception:  # noqa: BLE001 - settings validation can include secret inputs
        print("FAIL: configuration could not be loaded; inspect settings locally.")
        raise SystemExit(1) from None
    checks = {
        "PostgreSQL URL configured": settings.database_url.startswith(
            "postgresql+psycopg://"
        ),
        "OpenAI key configured": bool(settings.openai_api_key.strip()),
        "S3 bucket configured": bool(settings.s3_bucket.strip()),
        "FFmpeg available": bool(shutil.which(settings.ffmpeg_path)),
        "ffprobe available": bool(shutil.which(settings.ffprobe_path)),
        "Content release configured": bool(settings.assessment_content_release.strip()),
        "Assessment execution enabled": settings.assessment_execution_enabled,
        "Outbox dispatch enabled": settings.outbox_dispatch_enabled,
        "Tracing redaction enabled": settings.langsmith_redact_learner_text,
        "Linux worker environment": platform.system() == "Linux",
    }
    for label, passed in checks.items():
        print(f"{'OK' if passed else 'MISSING'}: {label}")
    print(
        "Local checks only: connectivity, migrations, published content, AWS access and worker registration remain unverified."
    )
    raise SystemExit(0 if all(checks.values()) else 1)


if __name__ == "__main__":
    main()

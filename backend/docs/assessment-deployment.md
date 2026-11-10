# Assessment deployment runbook

Also schedule the bounded cleanup described in [retention cleanup](assessment-retention.md).
Preview with `uv run python -m app.workers.cleanup_retention --limit 100`, then
schedule the same command with `--apply` once bucket permissions/lifecycle are configured.

Run commands from `backend/`. This runbook supersedes the earlier setup docs'
statements that evaluation, checkpoints, and public progress remain unimplemented.
The implementation exists; live infrastructure readiness has not been verified.

## Configuration

Copy `.env.example` to an untracked `.env` or inject environment secrets. Configure
PostgreSQL, Redis, the private S3 bucket, OpenAI key/models and a strong JWT secret.
Install FFmpeg and ffprobe in the API runtime for upload confirmation. Use Linux
prefork workers in production; Windows solo mode cannot enforce equivalent limits.

AWS credentials must reach boto3 through its normal chain: workload role, profile,
or process environment. Pydantic reading AWS values from `.env` does not export
them into boto3's process environment. Never commit access keys. S3 needs scoped
PutObject/GetObject access, browser PUT CORS, and lifecycle retention. Redis and
PostgreSQL need private access and durable volumes/backups; Compose is local-only.

## Database and content

Install the locked dependencies with `uv sync --locked`. Back up an existing
database before migration. Inspect `uv run alembic current` and `uv run alembic heads`,
then apply `uv run alembic upgrade head` to an existing V4 schema. The migration
chain is additive: it does NOT bootstrap all V4 tables in an empty database.
Provision the base schema before using it; do not blindly stamp an existing database.

Publish and validate the configured immutable assessment release before opening
assessment starts. The bank needs valid grammar/vocabulary MCQs across A1–C2 and
writing/speaking prompts with private rubrics. Plan creation additionally needs
complete curriculum content. A configured release name alone does not prove
published content exists. No fabricated content is supplied by this setup.

## Processes and activation order

Set `ASSESSMENT_EXECUTION_ENABLED=true` in the worker runtime. Run under your
process supervisor with automatic restart:

```sh
uv run celery -A app.infrastructure.messaging.celery_app:celery_app worker --loglevel=INFO --queues=talkfiesta.assessments,talkfiesta.operations
```

Check `uv run celery -A app.infrastructure.messaging.celery_app:celery_app inspect registered`
and verify `talkfiesta.assessment.execute` is registered on the intended worker.
This contacts actual workers; local task registration alone is not proof.

Only then enable `OUTBOX_DISPATCH_ENABLED=true` in the dispatcher runtime, which
also needs `ASSESSMENT_EXECUTION_ENABLED=true`, and start these separate supervised
processes using the same database/broker settings:

```sh
uv run python -m app.workers.dispatch_outbox
uv run python -m app.workers.recover_jobs --loop --interval 20 --limit 100
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Recovery can instead run periodically with `--limit 100` (no `--loop`). Do not
assume Celery Beat schedules it: no Beat schedule is configured. Both dispatch
and recovery loops support termination signals and log sanitized error types.
Monitor quarantined outbox events, terminal failures, process restarts and queue age.

## Verification boundaries

`uv run python -m app.workers.check_assessment_setup` performs local checks and
returns nonzero for missing prerequisites. It never prints credential values or
contacts providers. It does not prove migrations, content, connectivity, remote
registration, permissions, or model access. Run it in each intended runtime with
the appropriate process flags; API-only environments need not enable worker flags.

No deployment, migration, content publishing, remote configuration, or live
assessment has been performed by this change. The next task is a controlled
end-to-end run after the above prerequisites are available.

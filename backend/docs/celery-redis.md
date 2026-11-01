# Celery and Redis configuration

Celery app: `app.infrastructure.messaging.celery_app:celery_app`.
Redis DB 0 remains API throttling; Redis DB 1 is the broker. These logical
databases share resources and persistence, not isolation. PostgreSQL remains
authoritative for job state/results; no Celery Redis result backend is enabled.

## Run locally

From backend/:

```sh
docker compose up -d redis
uv sync
uv run celery -A app.infrastructure.messaging.celery_app:celery_app worker --loglevel=INFO --queues=talkfiesta.operations
```

Use Linux/WSL for real workers. A native Windows development-only command is:

```powershell
uv run celery -A app.infrastructure.messaging.celery_app:celery_app worker --pool=solo --concurrency=1 --loglevel=INFO --queues=talkfiesta.operations
```

The solo pool does not provide prefork process isolation/soft time limits, and
remote-control commands may wait while a task is running. Provider timeouts are
still required when real evaluators are added.

Copy the Celery settings from .env.example. When workers run in a Compose
network, use redis://redis:6379/1 instead of localhost. These commands do not
start the FastAPI server or outbox dispatcher.

## Operational checks

```sh
docker compose exec redis redis-cli ping
uv run celery -A app.infrastructure.messaging.celery_app:celery_app inspect ping --timeout=5
uv run celery -A app.infrastructure.messaging.celery_app:celery_app inspect registered
uv run celery -A app.infrastructure.messaging.celery_app:celery_app call talkfiesta.health.ping
```

The last command publishes a real, non-sensitive health task. Watch the worker
log for success; no result is retained. No live worker or broker was started
by this implementation.

## Reliability and scope

- JSON-only messages; tasks should carry job IDs, never recordings/transcripts.
- Late acknowledgement, requeue on worker-process loss, prefetch one, and bounded
  task execution. Soft/hard/visibility defaults are 240/300/900 seconds, validated
  in that order. Broker reconnects retry; individual publish retries are bounded.
- Re-delivery can happen. This configuration does not provide exactly-once
  execution or billing. Durable job claims, recovery and bounded business retries
  still need implementation. Poison tasks must not be requeued indefinitely.
- Compose Redis uses AOF every second, a named volume and noeviction. This reduces
  accidental queue loss, but does not remove the need for PostgreSQL recovery;
  a crash can lose recent AOF writes. Local port is bound to loopback only.
- `talkfiesta.operations` and `talkfiesta.assessments` queues are explicitly
  declared. Only the health task is registered today. Do not publish assessment
  tasks or enable an assessment consumer until its actual handler is implemented:
  Celery discards unregistered task messages. No dummy assessment task is present.
- No Beat schedule is enabled. Outbox dispatch and evaluation task registration
  are the next implementation steps, along with lease/stage persistence.
- Production Redis should use private networking and authentication/TLS as
  appropriate; configure the broker URL through environment/secrets.

References: [Celery configuration](https://docs.celeryq.dev/en/stable/userguide/configuration.html)
and [Redis transport](https://docs.celeryq.dev/en/stable/getting-started/backends-and-brokers/redis.html).

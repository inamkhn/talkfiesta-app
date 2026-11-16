"""Commit reservations before provider I/O; a crash never refunds its call slot."""

from app.infrastructure.ai.langchain_models import invoke_structured_model
from app.infrastructure.database.sync_session import SyncSessionLocal
from app.modules.content.budget import reserve_metrics
from app.modules.jobs.content_runner import require_claim


def model_for_claim(claim):
    def invoke(schema, *, system_prompt, user_prompt, runnable_config=None):
        with SyncSessionLocal.begin() as db:
            job, _ = require_claim(db, claim)
            cap = reserve_metrics(job, schema, system_prompt, user_prompt)

        def record_usage(usage):
            with SyncSessionLocal.begin() as db:
                job, _ = require_claim(db, claim)
                metrics = dict(job.metrics or {})
                for key in ("input_tokens", "output_tokens", "total_tokens"):
                    value = usage.get(key)
                    if type(value) is int and value >= 0:
                        metrics[key] = metrics.get(key, 0) + value
                metrics["provider_responses_recorded"] = (
                    metrics.get("provider_responses_recorded", 0) + 1
                )
                job.metrics = metrics

        return invoke_structured_model(
            schema,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            runnable_config=runnable_config,
            max_output_tokens=cap,
            usage_callback=record_usage,
            allow_local_fallback=False,
        )

    return invoke

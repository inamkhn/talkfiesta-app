"""Conservative per-unit limits shared by graph retries and worker retries."""

import json

POLICY = {"max_calls": 6, "max_input_bytes": 60000, "max_output_tokens": 6000}


class ContentBudgetExceeded(ValueError):
    pass


def remaining_calls(job) -> int:
    policy = (job.job_context or {}).get("generation_budget", POLICY)
    return max(
        0, policy["max_calls"] - (job.metrics or {}).get("provider_calls_reserved", 0)
    )


def reserve_metrics(job, schema, system_prompt: str, user_prompt: str) -> int:
    policy = (job.job_context or {}).get("generation_budget", POLICY)
    size = len(
        (system_prompt + user_prompt + json.dumps(schema.model_json_schema())).encode(
            "utf-8"
        )
    )
    if size > policy["max_input_bytes"] or remaining_calls(job) == 0:
        raise ContentBudgetExceeded("Content generation budget exhausted.")
    job.metrics = {
        **(job.metrics or {}),
        "provider_calls_reserved": (job.metrics or {}).get("provider_calls_reserved", 0)
        + 1,
        "provider_input_bytes_reserved": (job.metrics or {}).get(
            "provider_input_bytes_reserved", 0
        )
        + size,
    }
    return policy["max_output_tokens"]

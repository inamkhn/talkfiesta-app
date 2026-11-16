"""Versioned prompt bundle loader for Content Factory generation and review."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from app.modules.content.contracts import ContentModule

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"


@lru_cache(maxsize=32)
def _read_prompt(relative_path: str) -> str:
    path = PROMPTS_DIR / relative_path
    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {path}")
    return path.read_text(encoding="utf-8").strip()


def load_generator_prompt(
    module: ContentModule,
    *,
    prompt_bundle_version: str = "content-factory-v1",
) -> tuple[str, str]:
    """Return `(prompt_version_id, combined_system_prompt)` for the requested module."""
    if prompt_bundle_version != "content-factory-v1":
        raise ValueError(f"Unsupported prompt_bundle_version: {prompt_bundle_version}")
    mod_dir = module.lower()
    parts = [
        _read_prompt("common/system_rules.md"),
        _read_prompt("common/cefr_rules.md"),
        _read_prompt("common/output_rules.md"),
        _read_prompt(f"{mod_dir}/generate_v1.md"),
    ]
    return f"{mod_dir}-generate-v1", "\n\n".join(parts)


def load_reviewer_prompt(
    module: ContentModule,
    *,
    prompt_bundle_version: str = "content-factory-v1",
) -> tuple[str, str]:
    """Return `(prompt_version_id, combined_reviewer_prompt)` for the requested module."""
    if prompt_bundle_version != "content-factory-v1":
        raise ValueError(f"Unsupported prompt_bundle_version: {prompt_bundle_version}")
    mod_dir = module.lower()
    parts = [
        _read_prompt("common/cefr_rules.md"),
        _read_prompt(f"{mod_dir}/review_v1.md"),
    ]
    return f"{mod_dir}-review-v1", "\n\n".join(parts)


"""Prompt configuration loader from YAML files."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel

_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "config" / "prompts"


class PromptConfig(BaseModel):
    """Configuration for an LLM prompt."""

    system: str
    user_template: str
    model: str
    temperature: float
    max_tokens: int
    threshold: Optional[int] = None


def load_prompt(path: str | Path) -> PromptConfig:
    """Load a prompt configuration from a YAML file."""
    path = Path(path)
    with path.open() as f:
        data = yaml.safe_load(f)
    return PromptConfig(**data)


def load_evaluation_prompt() -> PromptConfig:
    """Load the newsworthiness evaluation prompt config."""
    return load_prompt(_PROMPTS_DIR / "evaluation.yaml")


def load_generation_prompt() -> PromptConfig:
    """Load the LinkedIn draft generation prompt config."""
    return load_prompt(_PROMPTS_DIR / "generation.yaml")

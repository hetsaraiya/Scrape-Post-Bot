"""Content evaluator with LLM-based newsworthiness scoring."""

from __future__ import annotations

import json
import logging
import re

import litellm
from pydantic import BaseModel

from app.models.content_item import ContentItem
from app.pipeline.prompts import PromptConfig

logger = logging.getLogger(__name__)


def extract_json(text: str) -> dict:
    """Extract JSON from LLM response, handling markdown fences and embedded JSON."""
    # Try direct parse first
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        pass

    # Try stripping markdown fences
    match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # Try finding first {...} block
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Could not extract JSON from response: {text[:200]}")


class EvaluationResult(BaseModel):
    """Result of content newsworthiness evaluation."""

    score: float
    reason: str
    is_newsworthy: bool


class ContentEvaluator:
    """Evaluates content items for newsworthiness via LLM."""

    def __init__(self, prompt_config: PromptConfig) -> None:
        self._config = prompt_config

    async def evaluate(self, item: ContentItem) -> EvaluationResult:
        """Score a content item for newsworthiness using LLM."""
        try:
            user_message = self._config.user_template.format(
                title=item.title,
                source_id=item.source_id,
                url=item.url,
                content=item.content[:3000],
            )

            response = await litellm.acompletion(
                model=self._config.model,
                messages=[
                    {"role": "system", "content": self._config.system},
                    {"role": "user", "content": user_message},
                ],
                temperature=self._config.temperature,
                max_tokens=self._config.max_tokens,
                timeout=30,
            )

            parsed = extract_json(response.choices[0].message.content)
            score = float(parsed.get("score", 0))
            reason = str(parsed.get("reason", ""))

            return EvaluationResult(
                score=score,
                reason=reason,
                is_newsworthy=score >= (self._config.threshold or 6),
            )

        except Exception as exc:
            logger.warning("Evaluation failed for %s: %s", item.id, exc)
            return EvaluationResult(
                score=0,
                reason=f"Evaluation failed: {exc}",
                is_newsworthy=False,
            )

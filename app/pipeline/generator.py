"""Draft generator producing LinkedIn posts via LLM."""

from __future__ import annotations

import logging

import litellm

from app.models.content_item import ContentItem
from app.models.draft import Draft
from app.pipeline.evaluator import EvaluationResult
from app.pipeline.prompts import PromptConfig

logger = logging.getLogger(__name__)


class GenerationError(Exception):
    """Raised when draft generation fails."""


class DraftGenerator:
    """Generates LinkedIn draft posts from evaluated content items."""

    def __init__(self, prompt_config: PromptConfig) -> None:
        self._config = prompt_config

    async def generate(self, item: ContentItem, evaluation: EvaluationResult) -> Draft:
        """Generate a LinkedIn post draft from a content item and its evaluation."""
        try:
            user_message = self._config.user_template.format(
                title=item.title,
                source_id=item.source_id,
                url=item.url,
                content=item.content[:3000],
                evaluation_score=evaluation.score,
                evaluation_reason=evaluation.reason,
            )

            response = await litellm.acompletion(
                model=self._config.model,
                messages=[
                    {"role": "system", "content": self._config.system},
                    {"role": "user", "content": user_message},
                ],
                temperature=self._config.temperature,
                max_tokens=self._config.max_tokens,
                timeout=60,
            )

            post_text = response.choices[0].message.content.strip()

            return Draft(
                content_item_id=item.id,
                source_id=item.source_id,
                title=item.title,
                body=post_text,
                original_url=item.url,
                evaluation_score=evaluation.score,
                evaluation_reason=evaluation.reason,
            )

        except Exception as exc:
            logger.error(f"Generation failed for {item.id}: {exc}")
            raise GenerationError(f"Failed to generate draft for {item.id}: {exc}") from exc

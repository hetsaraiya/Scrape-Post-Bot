"""Pipeline worker consuming content queue through the full processing pipeline."""

from __future__ import annotations

import asyncio
import logging

import redis.asyncio as aioredis

from app.models.content_item import ContentItem
from app.pipeline.dedup import DedupService
from app.pipeline.evaluator import ContentEvaluator
from app.pipeline.generator import DraftGenerator, GenerationError
from app.pipeline.prompts import load_evaluation_prompt, load_generation_prompt
from app.services.content_queue import ContentQueue
from app.services.draft_store import DraftStore

logger = logging.getLogger(__name__)

_worker_task: asyncio.Task | None = None


async def pipeline_worker(redis: aioredis.Redis) -> None:
    """Main pipeline loop: pop -> dedup -> evaluate -> generate -> store."""
    queue = ContentQueue(redis)
    dedup = DedupService(redis)
    draft_store = DraftStore(redis)

    logger.info("Pipeline worker started")

    while True:
        try:
            item = await queue.pop()
            if item is None:
                await asyncio.sleep(5)
                continue

            # Reload prompts each iteration for hot-reload support
            eval_config = load_evaluation_prompt()
            gen_config = load_generation_prompt()
            evaluator = ContentEvaluator(eval_config)
            generator = DraftGenerator(gen_config)

            # Dedup check
            if await dedup.is_duplicate(item):
                logger.debug("Skipping duplicate: %s", item.title)
                continue

            # Evaluate newsworthiness
            evaluation = await evaluator.evaluate(item)
            if not evaluation.is_newsworthy:
                logger.info(
                    "Not newsworthy (score=%.1f): %s",
                    evaluation.score,
                    item.title,
                )
                await dedup.mark_processed(item)
                continue

            # Generate draft
            try:
                draft = await generator.generate(item, evaluation)
            except GenerationError as exc:
                logger.warning("Generation failed for %s: %s", item.id, exc)
                await dedup.mark_processed(item)
                continue

            # Store and mark processed
            await draft_store.store(draft)
            await dedup.mark_processed(item)
            logger.info("Draft created: %s for %s", draft.id, item.title)

        except Exception:
            logger.exception("Pipeline worker error")
            await asyncio.sleep(1)


async def start_pipeline_worker(redis: aioredis.Redis) -> None:
    """Start the pipeline worker as a background task."""
    global _worker_task
    _worker_task = asyncio.create_task(pipeline_worker(redis))
    logger.info("Pipeline worker task created")


async def stop_pipeline_worker() -> None:
    """Stop the pipeline worker task."""
    global _worker_task
    if _worker_task is not None:
        _worker_task.cancel()
        try:
            await _worker_task
        except asyncio.CancelledError:
            pass
        _worker_task = None
        logger.info("Pipeline worker stopped")

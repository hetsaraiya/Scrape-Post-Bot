"""Pipeline worker consuming content queue through the full processing pipeline."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

import redis.asyncio as aioredis

from app.models.content_item import ContentItem
from app.pipeline.dedup import DedupService
from app.pipeline.evaluator import ContentEvaluator
from app.pipeline.generator import DraftGenerator, GenerationError
from app.pipeline.prompts import load_evaluation_prompt, load_generation_prompt
from app.services.content_queue import ContentQueue
from app.services.draft_store import DraftStore
from app.services.metrics import MetricsService

logger = logging.getLogger(__name__)

_worker_task: asyncio.Task | None = None


async def pipeline_worker(redis: aioredis.Redis) -> None:
    """Main pipeline loop: pop -> dedup -> evaluate -> generate -> store."""
    queue = ContentQueue(redis)
    dedup = DedupService(redis)
    draft_store = DraftStore(redis)
    metrics = MetricsService(redis)

    logger.info("Pipeline worker started")

    while True:
        try:
            # Update heartbeat
            await redis.hset("pipeline:status", mapping={
                "state": "running",
                "last_heartbeat": datetime.now(timezone.utc).isoformat(),
            })

            item = await queue.pop()
            if item is None:
                await asyncio.sleep(5)
                continue

            await metrics.increment("items_processed")

            # Reload prompts each iteration for hot-reload support
            eval_config = load_evaluation_prompt()
            gen_config = load_generation_prompt()
            evaluator = ContentEvaluator(eval_config)
            generator = DraftGenerator(gen_config)

            # Dedup check
            if await dedup.is_duplicate(item):
                logger.debug(f"Skipping duplicate: {item.title}")
                await metrics.increment("dedup_hits")
                continue

            # Evaluate newsworthiness
            evaluation = await evaluator.evaluate(item)
            if not evaluation.is_newsworthy:
                logger.info(f"Not newsworthy (score={evaluation.score:.1f}): {item.title}")
                await metrics.increment("eval_failed")
                await dedup.mark_processed(item)
                continue

            await metrics.increment("eval_passed")

            # Generate draft
            try:
                draft = await generator.generate(item, evaluation)
            except GenerationError as exc:
                logger.warning(f"Generation failed for {item.id}: {exc}")
                await metrics.increment("gen_errors")
                await dedup.mark_processed(item)
                continue

            await metrics.increment("gen_success")

            # Store and mark processed
            await draft_store.store(draft)
            await dedup.mark_processed(item)
            logger.info(f"Draft created: {draft.id} for {item.title}")

        except Exception:
            logger.exception("Pipeline worker error")
            await redis.hset("pipeline:status", "state", "error")
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

    # Update status in Redis
    from app.core.redis import get_redis as _get_redis

    try:
        r = _get_redis()
        await r.hset("pipeline:status", "state", "stopped")
    except RuntimeError:
        pass

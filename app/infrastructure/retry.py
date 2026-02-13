"""Retry decorators with exponential backoff for HTTP operations."""

from __future__ import annotations

import logging

import httpx
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)


def _is_retryable_error(exception: BaseException) -> bool:
    """Determine if an exception should trigger a retry.

    Does not retry 4xx client errors -- only 5xx server errors.
    """
    if isinstance(exception, httpx.HTTPStatusError):
        return exception.response.status_code >= 500
    return True


# General HTTP retry: 3 attempts, exponential backoff 4s-60s
retry_http = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=60),
    retry=retry_if_exception(_is_retryable_error)
    & retry_if_exception_type(
        (httpx.NetworkError, httpx.TimeoutException, httpx.HTTPStatusError)
    ),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)

# Feed retry: 5 attempts, longer backoff (feeds can be flaky)
retry_feed = retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=2, min=4, max=120),
    retry=retry_if_exception(_is_retryable_error)
    & retry_if_exception_type(
        (httpx.NetworkError, httpx.TimeoutException, httpx.HTTPStatusError)
    ),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)

# Network-only retry: only retry on network/timeout errors, not HTTP status errors
retry_network_only = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=60),
    retry=retry_if_exception_type(
        (httpx.NetworkError, httpx.TimeoutException)
    ),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)

"""Correlation ID middleware for request tracing."""

import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging import correlation_id_var, get_logger

logger = get_logger(__name__)


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Attach a correlation ID to each request."""

    def __init__(self, app, header_name: str = "X-Correlation-ID") -> None:  # noqa: ANN001
        super().__init__(app)
        self.header_name = header_name

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        cid = request.headers.get(self.header_name) or str(uuid.uuid4())
        token = correlation_id_var.set(cid)
        try:
            logger.info(f"Request started: {request.method} {request.url.path}")
            response = await call_next(request)
            response.headers[self.header_name] = cid
            logger.info(f"Request finished: {request.method} {request.url.path} status={response.status_code}")
            return response
        finally:
            correlation_id_var.reset(token)

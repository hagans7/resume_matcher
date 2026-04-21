"""CorrelationMiddleware — injects X-Correlation-ID into every request.

If client sends X-Correlation-ID header, it is preserved.
Otherwise a new UUID4 is generated.
The correlation_id is attached to request.state and returned in response headers.
Structlog contextvars are bound so every log line in the request includes it.
"""

import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

CORRELATION_ID_HEADER = "X-Correlation-ID"


class CorrelationMiddleware(BaseHTTPMiddleware):

    async def dispatch(self, request: Request, call_next) -> Response:
        correlation_id = (
            request.headers.get(CORRELATION_ID_HEADER) or str(uuid.uuid4())
        )

        # Attach to request state for route handlers
        request.state.correlation_id = correlation_id

        # Bind to structlog context — every log line in this request gets this field
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(correlation_id=correlation_id)

        response = await call_next(request)

        # Return correlation ID in response so client can trace
        response.headers[CORRELATION_ID_HEADER] = correlation_id

        return response

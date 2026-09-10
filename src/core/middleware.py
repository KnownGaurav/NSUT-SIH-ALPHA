import time
import logging
from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("railway_eta.http")


class OperationalLoggingMiddleware(BaseHTTPMiddleware):
    """
    Production-grade HTTP request logging & execution timing middleware.
    Attaches X-Process-Time-Ms and handles unhandled exceptions with structured JSON.
    """
    async def dispatch(self, request: Request, call_next):
        start_time = time.perf_counter()
        client_ip = request.client.host if request.client else "unknown"
        method = request.method
        path = request.url.path

        try:
            response = await call_next(request)
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            response.headers["X-Process-Time-Ms"] = str(duration_ms)

            # Suppress noisy periodic poll logs from bloating output
            if not (path.endswith("/position") or path.endswith("/status")):
                logger.info(f"{method} {path} - {response.status_code} ({duration_ms}ms) [{client_ip}]")
            return response
        except Exception as exc:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            logger.error(f"Unhandled exception on {method} {path} after {duration_ms}ms: {exc}", exc_info=True)
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "error": "InternalServerError",
                    "detail": "An internal operational error occurred while processing railway telemetry.",
                    "path": path,
                    "timestamp": time.time()
                }
            )

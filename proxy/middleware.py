# proxy/middleware.py
import uuid
import time
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from proxy.logging_config import audit_log, REQUEST_ID_CTX


class RequestResponseLoggerMiddleware(BaseHTTPMiddleware):

    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.max_body_log_chars = 100  # Truncate large bodies
        self.sensitive_headers = {"authorization", "cookie"}

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        start_time = time.time()

        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        token = REQUEST_ID_CTX.set(request_id)  # Set context variable

        try:
            self._log_inbound(request, request_id)
            response = await call_next(request)
            process_time_ms = (time.time() - start_time) * 1000
            self._log_outbound(response, request_id, process_time_ms)

            return response

        except Exception as e:
            audit_log(
                stage="middleware_error",
                outcome="error",
                reason=f"Unhandled exception: {type(e).__name__}",
            )
            raise e

        finally:
            REQUEST_ID_CTX.reset(token)

    def _log_inbound(self, request: Request, request_id: str):
        # Filter sensitive headers
        logged_headers = {
            k: "[REDACTED]" if k.lower() in self.sensitive_headers else v
            for k, v in request.headers.items()
        }

        audit_log(
            request_id=request_id,
            stage="inbound",
            method=request.method,
            path=request.url.path,
            headers=logged_headers,
        )

    def _log_outbound(
        self, response: Response, request_id: str, process_time_ms: float
    ):
        content_length = response.headers.get("content-length", 0)

        audit_log(
            request_id=request_id,
            stage="outbound",
            status_code=response.status_code,
            body_size=int(content_length),
            latency_ms=round(process_time_ms, 2),
        )

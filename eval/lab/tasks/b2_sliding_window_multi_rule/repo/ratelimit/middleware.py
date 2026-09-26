"""Wrap request handlers with per-client rate limiting."""
from __future__ import annotations

from typing import Any, Callable, Dict, Optional, Tuple

from .limiter import RateLimiter

Request = Dict[str, Any]
Response = Tuple[int, Dict[str, str], Any]
Handler = Callable[[Request], Response]


class RateLimitMiddleware:
    """Reject requests with 429 once a client exceeds its rate limit.

    Requests are plain dicts and the client is identified by ``key_func``
    (the ``"client_ip"`` entry by default). Handlers return
    ``(status, headers, body)`` tuples.
    """

    def __init__(
        self,
        handler: Handler,
        limiter: RateLimiter,
        key_func: Optional[Callable[[Request], str]] = None,
    ) -> None:
        self.handler = handler
        self.limiter = limiter
        self.key_func = key_func or (lambda request: request["client_ip"])

    def __call__(self, request: Request) -> Response:
        key = self.key_func(request)
        if not self.limiter.allow(key):
            return self._too_many_requests(key)
        status, headers, body = self.handler(request)
        headers = dict(headers)
        headers["X-RateLimit-Remaining"] = str(self.limiter.remaining(key))
        return status, headers, body

    def _too_many_requests(self, key: str) -> Response:
        headers = {"Content-Type": "text/plain", "X-RateLimit-Remaining": "0"}
        return 429, headers, "Too Many Requests"

"""
Endpoint Rate Limiting & Brute-Force Protection (Phase 1 Remediation).
Provides sliding-window request throttling per client IP and endpoint bucket.
"""
import os
import time
import threading
from collections import defaultdict, deque
from typing import Callable, Deque, Dict
from fastapi import HTTPException, Request, status


class SlidingWindowRateLimiter:
    """Thread-safe in-memory sliding-window rate limiter per (bucket, client_ip)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._hits: Dict[str, Deque[float]] = defaultdict(deque)

    def reset(self) -> None:
        """Clear all recorded hits (useful between unit tests)."""
        with self._lock:
            self._hits.clear()

    def is_enabled(self) -> bool:
        """
        Active by default in development and production.
        In automated pytest runs (TESTING=1), disabled unless ENABLE_RATE_LIMIT_IN_TESTS=1
        so bulk functional test suites can run at full speed from TestClient IP.
        """
        if os.getenv("ENABLE_RATE_LIMIT_IN_TESTS", "").lower() in ("true", "1"):
            return True
        if os.getenv("TESTING", "").lower() in ("true", "1"):
            return False
        return True

    def check(self, bucket: str, client_ip: str, max_requests: int, window_seconds: int = 60) -> None:
        """Raise HTTP 429 if client_ip exceeds max_requests within window_seconds for bucket."""
        if not self.is_enabled():
            return

        now = time.monotonic()
        cutoff = now - window_seconds
        key = f"{bucket}:{client_ip}"

        with self._lock:
            q = self._hits[key]
            while q and q[0] <= cutoff:
                q.popleft()
            if len(q) >= max_requests:
                retry_after = max(1, int(window_seconds - (now - q[0])))
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Rate limit exceeded ({max_requests} requests per {window_seconds}s). Please try again in {retry_after} seconds.",
                    headers={"Retry-After": str(retry_after)},
                )
            q.append(now)


rate_limiter = SlidingWindowRateLimiter()


def rate_limit(bucket: str, max_requests: int, window_seconds: int = 60) -> Callable:
    """FastAPI dependency factory for endpoint rate limiting."""

    def _dependency(request: Request) -> None:
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            client_ip = forwarded.split(",")[0].strip()
        elif request.client and request.client.host:
            client_ip = request.client.host
        else:
            client_ip = "unknown"
        rate_limiter.check(bucket, client_ip, max_requests=max_requests, window_seconds=window_seconds)

    return _dependency

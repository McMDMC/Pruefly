"""Access code (fail closed), rate limiting, image validation."""
from __future__ import annotations

import hmac
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

from .config import Settings

_MAGIC = (
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"GIF87a", "image/gif"),
    (b"GIF89a", "image/gif"),
)


def sniff_image(data: bytes) -> str | None:
    """Media type from magic bytes, never from what the client claims."""
    for magic, mt in _MAGIC:
        if data.startswith(magic):
            return mt
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def check_access(settings: Settings, request: Request) -> None:
    if not settings.access_code:
        if settings.is_dev:
            return
        # Fail closed: a deployment without a code must not be open to the internet.
        raise HTTPException(503, "Server nicht konfiguriert (Zugangscode fehlt).")
    given = request.headers.get("x-access-code", "")
    if not hmac.compare_digest(given.encode(), settings.access_code.encode()):
        raise HTTPException(401, "Zugangscode falsch oder fehlt.")


class RateLimiter:
    """Sliding window per key, in-memory (per instance; fine for a closed pilot)."""

    def __init__(self, per_hour: int):
        self.per_hour = per_hour
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def hit(self, key: str) -> None:
        now = time.monotonic()
        q = self._hits[key]
        while q and now - q[0] > 3600:
            q.popleft()
        if len(q) >= self.per_hour:
            raise HTTPException(429, "Zu viele Anfragen – bitte später erneut versuchen.")
        q.append(now)


def client_key(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for", "")
    return (fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else "?")) or "?"

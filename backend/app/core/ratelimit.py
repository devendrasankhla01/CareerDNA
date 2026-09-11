"""Minimal in-memory rate limiter (single-instance hackathon deployment).

Production would use a distributed store; this is documented in docs/.
"""
from __future__ import annotations

import time
from collections import defaultdict, deque

_buckets: dict[str, deque[float]] = defaultdict(deque)


def check_rate_limit(key: str, limit: int, window_seconds: int) -> bool:
    """Return True when the key is still allowed, False when limited."""
    now = time.monotonic()
    dq = _buckets[key]
    while dq and now - dq[0] > window_seconds:
        dq.popleft()
    if len(dq) >= limit:
        return False
    dq.append(now)
    return True

"""Small in-memory sliding-window rate limiter for the public demo.

Per-client and global limits on /ask. In-memory is enough for a single-instance demo;
use a shared store (e.g. Redis) if you ever run several instances.
"""

from __future__ import annotations

import threading
import time
from collections import deque


class RateLimiter:
    def __init__(self, per_client: int, global_limit: int, window_s: float = 60.0):
        self.per_client = per_client
        self.global_limit = global_limit
        self.window = window_s
        self._hits: dict[str, deque[float]] = {}
        self._all: deque[float] = deque()
        self._lock = threading.Lock()

    def _trim(self, q: deque[float], now: float) -> None:
        while q and now - q[0] > self.window:
            q.popleft()

    def allow(self, client: str) -> bool:
        now = time.monotonic()
        with self._lock:
            self._trim(self._all, now)
            q = self._hits.setdefault(client, deque())
            self._trim(q, now)
            if (self.global_limit and len(self._all) >= self.global_limit) or (
                self.per_client and len(q) >= self.per_client
            ):
                return False
            q.append(now)
            self._all.append(now)
            if len(self._hits) > 10_000:  # drop idle clients
                self._hits = {k: v for k, v in self._hits.items() if v}
            return True

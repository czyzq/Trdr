"""Global per-provider rate limiting.

One token bucket per upstream data provider, shared by every caller in the
process. Replaces the per-call semaphores that provided no real limiting.
"""

import asyncio
import time
from typing import Dict, Optional


class TokenBucket:
    """Async token bucket. `acquire()` waits until a token is available."""

    def __init__(self, capacity: float, refill_per_sec: float):
        self.capacity = float(capacity)
        self.refill_per_sec = float(refill_per_sec)
        # start below capacity so cold start can't do capacity + a full refill
        # inside the provider's first rate window (5/min means FIVE, not ten)
        self._tokens = min(1.0, float(capacity))
        self._updated = time.monotonic()
        self._locks: dict = {}  # one lock per event loop (module-global gates)

    def _refill(self) -> None:
        now = time.monotonic()
        self._tokens = min(self.capacity, self._tokens + (now - self._updated) * self.refill_per_sec)
        self._updated = now

    def _get_lock(self) -> asyncio.Lock:
        # asyncio.Lock binds to a loop; gates are process-global and legacy
        # sync wrappers may spin up a second loop - key the lock per loop
        loop = asyncio.get_running_loop()
        lock = self._locks.get(id(loop))
        if lock is None:
            lock = asyncio.Lock()
            self._locks[id(loop)] = lock
        return lock

    def try_acquire(self, n: float = 1.0) -> bool:
        self._refill()
        if self._tokens >= n:
            self._tokens -= n
            return True
        return False

    async def acquire(self, n: float = 1.0) -> None:
        while True:
            async with self._get_lock():
                self._refill()
                if self._tokens >= n:
                    self._tokens -= n
                    return
                wait = (n - self._tokens) / self.refill_per_sec if self.refill_per_sec > 0 else 1.0
            await asyncio.sleep(min(wait, 5.0))


class ProviderGate:
    """Token bucket + failure-based cooldown for one provider.

    After `max_failures` consecutive failures the provider is skipped for
    `cooldown_sec` so we stop burning tokens (and latency) on a dead upstream.
    """

    def __init__(self, name: str, capacity: float, refill_per_sec: float,
                 max_failures: int = 5, cooldown_sec: float = 300.0):
        self.name = name
        self.bucket = TokenBucket(capacity, refill_per_sec)
        self.max_failures = max_failures
        self.cooldown_sec = cooldown_sec
        self._consecutive_failures = 0
        self._skip_until = 0.0

    def available(self) -> bool:
        return time.monotonic() >= self._skip_until

    async def acquire(self) -> bool:
        """Wait for a token. Returns False (without waiting) while cooling down."""
        if not self.available():
            return False
        await self.bucket.acquire()
        return True

    def record_success(self) -> None:
        self._consecutive_failures = 0

    def record_failure(self) -> None:
        self._consecutive_failures += 1
        if self._consecutive_failures >= self.max_failures:
            self._skip_until = time.monotonic() + self.cooldown_sec
            self._consecutive_failures = 0
            print(f"[RATE-LIMITER] Provider '{self.name}' cooling down for {self.cooldown_sec:.0f}s")


# Free-tier limits. alpha_vantage: 5 calls/min hard limit.
_GATES: Dict[str, ProviderGate] = {}
_GATE_SPECS = {
    "alpha_vantage": dict(capacity=5, refill_per_sec=5 / 60),
    "yahoo": dict(capacity=30, refill_per_sec=30 / 60),
    "binance": dict(capacity=60, refill_per_sec=60 / 60),
}


def get_gate(provider: str) -> ProviderGate:
    gate = _GATES.get(provider)
    if gate is None:
        spec = _GATE_SPECS.get(provider, dict(capacity=10, refill_per_sec=10 / 60))
        gate = ProviderGate(provider, **spec)
        _GATES[provider] = gate
    return gate

"""Tests for the shared per-provider rate limiter."""

import asyncio
import time

import pytest

from services.rate_limiter import ProviderGate, TokenBucket, get_gate


def test_try_acquire_depletes_and_refills():
    # buckets start with at most 1 token so a cold start cannot burst
    # capacity + refill inside the provider's first rate window
    slow = TokenBucket(capacity=5, refill_per_sec=0.001)
    assert slow.try_acquire()
    assert not slow.try_acquire()
    fast = TokenBucket(capacity=2, refill_per_sec=1000.0)
    assert fast.try_acquire()
    time.sleep(0.01)  # 1000/s refill: ~10 tokens accrue
    assert fast.try_acquire()


@pytest.mark.asyncio
async def test_acquire_waits_for_refill():
    bucket = TokenBucket(capacity=1, refill_per_sec=20.0)  # refill in 50ms
    await bucket.acquire()
    start = time.monotonic()
    await bucket.acquire()
    assert time.monotonic() - start >= 0.03


@pytest.mark.asyncio
async def test_gate_cooldown_after_failures():
    gate = ProviderGate("test", capacity=100, refill_per_sec=100, max_failures=3, cooldown_sec=60)
    assert await gate.acquire()
    for _ in range(3):
        gate.record_failure()
    assert not gate.available()
    assert not await gate.acquire()  # returns immediately, no token spent


@pytest.mark.asyncio
async def test_gate_success_resets_failure_count():
    gate = ProviderGate("test2", capacity=100, refill_per_sec=100, max_failures=3, cooldown_sec=60)
    gate.record_failure()
    gate.record_failure()
    gate.record_success()
    gate.record_failure()
    gate.record_failure()
    assert gate.available()  # never hit 3 consecutive


def test_get_gate_is_shared_singleton():
    assert get_gate("alpha_vantage") is get_gate("alpha_vantage")
    assert get_gate("alpha_vantage").bucket.capacity == 5

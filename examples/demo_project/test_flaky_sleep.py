# =============================================================================
# examples/demo_project/test_flaky_sleep.py
# =============================================================================
#
# PURPOSE OF THIS FILE:
#   Demonstrates tests that are flaky due to TIMING ASSUMPTIONS.
#
# WHY DO TESTS FAIL DUE TO TIMING?
#   Some tests assume an operation completes within a specific time window.
#   On a fast machine or under light load, the timing holds. On a slow machine,
#   in a Docker container, or under heavy CPU load (like parallel CI runners),
#   the same test can time out and fail.
#
#   This is one of the most common causes of CI flakiness in the industry.
#
# REAL-WORLD EXAMPLES OF THIS BUG PATTERN:
#   - `time.sleep(0.1)` followed by an assertion that assumes the sleep is done
#   - `asyncio.wait_for(task, timeout=1.0)` that's too tight for slow CI
#   - Tests that poll a queue or socket with a fixed retry budget
#   - Tests that assert a cache has expired after N seconds
#
# HOW TO FIX THIS:
#   Fix #1 (Generous timeouts): Use much larger timeouts than you think you need.
#           If the operation takes 10ms locally, allow 2000ms in the test.
#   Fix #2 (Polling): Instead of sleeping a fixed amount, poll until the
#           condition is true (with a timeout):
#               deadline = time.monotonic() + 2.0
#               while time.monotonic() < deadline:
#                   if condition_met(): break
#                   time.sleep(0.01)
#           else:
#               raise TimeoutError("Condition not met in time")
#   Fix #3 (Mock time): Use `unittest.mock.patch('time.sleep')` to make
#           sleep() a no-op, removing the timing dependency entirely.
#   Fix #4 (Synchronization): Use threading.Event, asyncio.Event, or a Queue
#           to SIGNAL completion instead of guessing the duration.
#
# Run this demo with:
#   flaky-detect --cmd "pytest examples/demo_project/test_flaky_sleep.py -v" --runs 15
#
# =============================================================================

import time
import threading
from typing import List


# =============================================================================
# The code being tested (the "production code")
# =============================================================================

class BackgroundProcessor:
    """
    Simulates a task that runs in a background thread and produces a result.

    In real code this could be: async I/O, a worker thread, a future, etc.
    The key point is that the result is NOT immediately available —
    the caller must wait for the background work to complete.
    """

    def __init__(self, work_duration_seconds: float = 0.05):
        """
        Args:
            work_duration_seconds: How long the background work takes.
                                   Simulates variable execution time.
        """
        self.result: List[str] = []
        self._done = threading.Event()
        self._work_duration = work_duration_seconds

    def start(self) -> None:
        """Start the background task in a new thread."""
        # `threading.Thread(target=fn)` creates a new thread that will call `fn`.
        # `.start()` begins execution.
        # The main thread continues immediately — the background work runs in parallel.
        thread = threading.Thread(target=self._do_work, daemon=True)
        thread.start()

    def _do_work(self) -> None:
        """Background work: simulates processing that takes some time."""
        # `time.sleep()` pauses this THREAD for the given number of seconds.
        # The main thread is NOT affected — it keeps running.
        time.sleep(self._work_duration)

        # Populate the result (the "output" of the background work).
        self.result.append("item_1")
        self.result.append("item_2")

        # Signal that work is complete.
        # `self._done.set()` wakes up anything waiting on `self._done.wait()`.
        self._done.set()

    def wait(self, timeout: float = None) -> bool:
        """
        Wait for background work to complete.

        Args:
            timeout: Maximum seconds to wait. None means wait forever.

        Returns:
            True if work completed before timeout, False if timed out.
        """
        return self._done.wait(timeout=timeout)


class SimpleCache:
    """
    A simple time-based cache: entries expire after `ttl` seconds.

    In real code: Redis TTL, HTTP cache headers, session expiry, etc.
    """

    def __init__(self, ttl_seconds: float = 0.1):
        self._ttl = ttl_seconds
        self._store = {}          # dict mapping key → (value, expiry_timestamp)

    def set(self, key: str, value) -> None:
        """Store a value with an expiry timestamp."""
        expiry = time.monotonic() + self._ttl
        self._store[key] = (value, expiry)

    def get(self, key: str):
        """
        Retrieve a value. Returns None if not found or expired.
        """
        if key not in self._store:
            return None

        value, expiry = self._store[key]

        # Has the entry expired?
        if time.monotonic() > expiry:
            # Delete the expired entry and return None.
            del self._store[key]
            return None

        return value


# =============================================================================
# Flaky tests — timing assumptions that don't always hold
# =============================================================================

class TestTimingFlakiness:
    """
    These tests contain INTENTIONAL timing bugs to demonstrate flakiness.
    On a fast machine they pass. Under load or in CI, they fail.
    """

    def test_background_result_ready_too_quickly(self):
        """
        FLAW: Sleeps for a fixed amount and assumes background work is done.
        If the system is slow, the background thread may not finish in time.

        This passes when the system is fast, fails when it's slow.
        Flake rate: low on fast machines, high on slow CI runners.
        """
        processor = BackgroundProcessor(work_duration_seconds=0.05)
        processor.start()

        # BUG: We assume 30ms is enough. If the system is slow, it's not.
        time.sleep(0.03)

        # This assertion may run before the background thread finishes!
        assert len(processor.result) == 2, (
            f"Expected 2 results, got {len(processor.result)}. "
            "Background thread may not have finished."
        )

    def test_cache_entry_expired_too_soon(self):
        """
        FLAW: Sleeps briefly assuming a cache entry has NOT yet expired.
        If the test runs slowly (e.g., GC pause, process scheduled out),
        the cache may expire before we check it.

        Flake rate: very low but non-zero (intermittent on slow machines/CI).
        """
        cache = SimpleCache(ttl_seconds=0.05)  # 50ms TTL
        cache.set("key", "value")

        # BUG: We assume only 10ms will pass. But if the process gets
        # descheduled by the OS, much more time may have elapsed.
        time.sleep(0.01)

        result = cache.get("key")
        assert result == "value", (
            f"Cache entry unexpectedly expired. Got: {result!r}"
        )

    def test_cache_entry_expired_on_schedule(self):
        """
        FLAW: Assumes the cache expires after EXACTLY the TTL.
        In practice, sleep() doesn't guarantee exact timing.
        The actual time slept may be slightly less than requested on some OSes.

        Flake rate: low but occurs on some Python implementations/platforms.
        """
        cache = SimpleCache(ttl_seconds=0.05)
        cache.set("key", "value")

        # BUG: We sleep for EXACTLY the TTL. The cache may not have expired yet
        # because time.sleep() can return slightly early on some platforms.
        time.sleep(0.05)

        result = cache.get("key")
        assert result is None, (
            f"Expected cache to be expired, but got {result!r}"
        )


# =============================================================================
# Correct versions of the same tests
# =============================================================================

class TestProperlyWrittenTimingTests:
    """
    These tests cover the same code but handle timing correctly.
    They should ALWAYS pass.
    """

    def test_background_result_ready_with_proper_wait(self):
        """
        CORRECT: Uses the signaling mechanism instead of a fixed sleep.

        `processor.wait(timeout=5.0)` blocks until the background thread
        signals completion OR 5 seconds pass — whichever comes first.
        We then check the return value to see which case happened.
        """
        processor = BackgroundProcessor(work_duration_seconds=0.05)
        processor.start()

        # Wait up to 5 seconds for the background work to complete.
        completed = processor.wait(timeout=5.0)

        assert completed, "Background task did not complete within 5 seconds"
        assert len(processor.result) == 2

    def test_cache_entry_valid_immediately_after_set(self):
        """
        CORRECT: Check the cache immediately after setting — no sleep needed.
        The entry should DEFINITELY not be expired yet.
        """
        cache = SimpleCache(ttl_seconds=1.0)  # 1 second TTL is plenty
        cache.set("greeting", "hello")

        # No sleep — we just check immediately.
        assert cache.get("greeting") == "hello"

    def test_cache_entry_expires_with_generous_wait(self):
        """
        CORRECT: Wait much longer than the TTL to ensure expiry has occurred.
        We use 10× the TTL as our sleep to buffer any system timing variance.
        """
        ttl = 0.05  # 50ms TTL
        cache = SimpleCache(ttl_seconds=ttl)
        cache.set("key", "value")

        # Wait for 10× the TTL — 500ms — to be safe even on the slowest machine.
        time.sleep(ttl * 10)

        result = cache.get("key")
        assert result is None, (
            f"Expected cache to be expired after {ttl * 10:.3f}s, but got {result!r}"
        )

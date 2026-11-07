"""Offline standard-library tests; no network, model or credential access."""
import sys
import threading
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "assets"))
from bounded_batch import BatchFailed, stage_batch


class RuntimeTests(unittest.TestCase):
    def test_workers_run_concurrently_with_bounded_inflight(self):
        barrier = threading.Barrier(3)
        lock = threading.Lock()
        active, peak = 0, 0
        def decide(i):
            nonlocal active, peak
            with lock:
                active += 1
                peak = max(peak, active)
            try:
                barrier.wait(timeout=3)
                return i
            finally:
                with lock:
                    active -= 1
        self.assertEqual(stage_batch(range(9), decide, max_workers=3,
                                    persist=lambda *_: None), list(range(9)))
        self.assertEqual(peak, 3)

    def test_serial_parallel_and_stable_order(self):
        items = list(range(12))
        for workers in (1, 2, 5):
            saved = {}
            out = stage_batch(items, lambda x: x*x, max_workers=workers,
                              persist=lambda i, v: saved.__setitem__(i, v))
            self.assertEqual(out, [x*x for x in items])
            self.assertEqual(saved, dict(enumerate(out)))

    def test_snapshot_isolation(self):
        shared = {"data": []}
        def decide(item):
            item["data"].append(1)
            return len(item["data"])
        out = stage_batch([shared, shared], decide, max_workers=2, persist=lambda *_: None)
        self.assertEqual(out, [1, 1])
        self.assertEqual(shared, {"data": []})

    def test_rolling_refills_while_slowest_running(self):
        third_started = threading.Event()
        def decide(i):
            if i == 0:
                if not third_started.wait(3):
                    raise AssertionError("wave scheduler waited for slowest")
            if i == 2:
                third_started.set()
            return i
        self.assertEqual(stage_batch(range(5), decide, max_workers=2,
                                    persist=lambda *_: None), list(range(5)))

    def test_global_failure_drains_and_does_not_refill(self):
        failure_seen = threading.Event()
        called, saved = [], {}
        lock = threading.Lock()
        def decide(i):
            with lock:
                called.append(i)
            if i == 0:
                raise RuntimeError("synthetic global failure")
            if not failure_seen.wait(3):
                raise AssertionError("coordinator did not observe failure")
            return i
        # Set failure_seen when coordinator sees the failed future.
        original_wait = sys.modules["bounded_batch"].wait
        def instrumented_wait(*args, **kwargs):
            done, pending = original_wait(*args, **kwargs)
            if any(f.exception() is not None for f in done):
                failure_seen.set()
            return done, pending
        from unittest.mock import patch
        with patch("bounded_batch.wait", instrumented_wait):
            with self.assertRaises(BatchFailed):
                stage_batch(range(20), decide, max_workers=2,
                            persist=lambda i, v: saved.__setitem__(i, v))
        self.assertEqual(sorted(called), [0, 1])
        self.assertEqual(saved, {1: 1})

    def test_persistence_error_cannot_report_completed_batch(self):
        def deny(*_):
            raise PermissionError("synthetic disk failure")
        with self.assertRaises(BatchFailed) as result:
            stage_batch([1], lambda x: x, max_workers=1, persist=deny)
        self.assertIsInstance(result.exception.failures[0][1], PermissionError)

    def test_reuse_saved_decisions_without_repeating_work(self):
        saved, calls = {}, []
        def attempt(i):
            if i in saved:
                return saved[i]
            calls.append(i)
            if i == 2:
                raise RuntimeError("synthetic interrupt")
            return i*10
        with self.assertRaises(BatchFailed):
            stage_batch(range(4), attempt, max_workers=1,
                        persist=lambda i, v: saved.__setitem__(i, v))
        self.assertEqual(saved, {0: 0, 1: 10})
        def resumed(i):
            if i in saved:
                return saved[i]
            calls.append(i)
            return i*10
        out = stage_batch(range(4), resumed, max_workers=2,
                          persist=lambda i, v: saved.__setitem__(i, v))
        self.assertEqual(out, [0, 10, 20, 30])
        self.assertEqual(calls.count(0), 1)
        self.assertEqual(calls.count(1), 1)

    def test_input_and_callback_copies(self):
        def persist(_, value):
            value.append("callback change")
        self.assertEqual(stage_batch([1], lambda _: [], max_workers=1,
                                     persist=persist), [[]])
        for invalid in (0, -1, True, 1.5):
            with self.assertRaises(ValueError):
                stage_batch([], lambda x: x, max_workers=invalid, persist=persist)
        self.assertEqual(stage_batch([], lambda x: x, max_workers=1,
                                     persist=persist), [])


if __name__ == "__main__":
    unittest.main()

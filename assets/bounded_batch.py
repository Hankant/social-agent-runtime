"""Framework-neutral staging only. No API, retries, durable store or state commit.

decide gets an isolated copy. persist(index, result) runs on the coordinator and
must durably save a validated independent decision (not mutate the environment).
Successful callbacks may have run even if the batch raises. A caller can reuse
those decisions after validating their identity against the original snapshot.
Every worker must have bounded I/O timeouts: threads cannot be forcibly killed.
"""
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from copy import deepcopy


class BatchFailed(RuntimeError):
    def __init__(self, failures):
        self.failures = tuple(failures)  # (input index, original exception)
        super().__init__(f"{len(failures)} task/persistence failure(s); no batch returned")


def stage_batch(items, decide, *, max_workers, persist):
    """Bounded rolling submission; stable result order; stop refilling on error.

    The caller freezes the complete environment BEFORE constructing items and
    applies returned decisions in one separate atomic commit. Model-approved
    personal failures must be converted to explicit outcomes by its adapter;
    other exceptions abort the batch. The persistence callback must be idempotent.
    """
    if type(max_workers) is not int or max_workers < 1:
        raise ValueError("max_workers must be a positive integer")
    snapshots = [deepcopy(item) for item in items]
    results, failures = {}, []
    next_index = 0
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        pending = {}

        def submit(index):
            pending[pool.submit(decide, snapshots[index])] = index

        while next_index < min(max_workers, len(snapshots)):
            submit(next_index)
            next_index += 1
        try:
            while pending:
                done, _ = wait(pending, return_when=FIRST_COMPLETED)
                for future in sorted(done, key=lambda f: pending[f]):
                    index = pending.pop(future)
                    try:
                        result = future.result()
                        persist(index, deepcopy(result))
                        results[index] = result
                    except Exception as exc:
                        failures.append((index, exc))
                if not failures:
                    while len(pending) < max_workers and next_index < len(snapshots):
                        submit(next_index)
                        next_index += 1
        except BaseException:
            # Do not let remaining requests disappear without handing successes
            # to persistence. The executor waits for running workers on exit.
            for future in pending:
                future.cancel()
            for future, index in pending.items():
                if not future.cancelled():
                    try:
                        persist(index, deepcopy(future.result()))
                    except Exception as exc:
                        failures.append((index, exc))
            raise
    if failures:
        raise BatchFailed(failures)
    return [results[i] for i in range(len(snapshots))]

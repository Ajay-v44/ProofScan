import asyncio
from collections.abc import Callable
from threading import BoundedSemaphore

from fastapi import HTTPException


class WorkBudget:
    """Admit limited blocking work without growing the executor queue."""

    def __init__(self, slots: int):
        self.slots = BoundedSemaphore(slots)

    async def run[**P, T](self, work: Callable[P, T], /, *args: P.args, **kwargs: P.kwargs) -> T:
        if not self.slots.acquire(blocking=False):
            raise HTTPException(
                503, "ProofScan is busy. Try again shortly.", headers={"Retry-After": "1"}
            )

        def run_and_release() -> T:
            try:
                return work(*args, **kwargs)
            finally:
                self.slots.release()

        try:
            job = asyncio.get_running_loop().run_in_executor(None, run_and_release)
        except RuntimeError:
            self.slots.release()
            raise
        # The thread still owns its slot if the awaiting request is cancelled.
        return await asyncio.shield(job)

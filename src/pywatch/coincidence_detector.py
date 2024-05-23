import asyncio
import time
from typing import Self

import serial  # type: ignore

from .async_detector import Detector  # type: ignore


class CoincidenceDetector:
    """Detector which only registers a hit if another detector triggers an event"""

    def __init__(self, port: str, trigger: str, threshold: int = 10) -> None:
        self._detector = Detector(port)
        self._trigger = Detector(trigger)
        self._lock = asyncio.Lock()
        self._events: list[dict[str, int | float]] = []
        self._index = -1
        self.threshold = threshold

    async def open(self) -> Self:
        await self._trigger.open()
        await self._detector.open()

        return self

    async def close(self) -> None:
        await asyncio.gather(self._trigger.close(), self._detector.close())

    @property
    def is_open(self) -> bool:
        return self._detector.is_open

    def register_hit(self) -> None:
        self._events.append(self._detector[0])
        self._index = len(self._events) - 1

    async def measurement(self) -> dict:
        first_hit = False

        async def loop(detector: Detector) -> None:
            nonlocal first_hit
            while True:
                try:
                    await detector.measurement()
                except asyncio.CancelledError:
                    break
                # print(detector.port, " ", detector[0], file=file)

                if first_hit and self._trigger.event > 0 and self._detector.event > 0:
                    delta = self._trigger.comp_time - self._detector.comp_time
                    # print(detector.port, " ", delta, " ms", file=file)
                    if abs(delta) <= self.threshold:
                        # print("HIT", file=file)
                        self.register_hit()
                        return
                first_hit = True
                # print(f"[{detector.port}] {detector[0]}")

        tasks = [asyncio.create_task(loop(d)) for d in [self._trigger, self._detector]]
        _, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)

        for task in pending:
            task.cancel()

        return self._detector[0]

    def __len__(self) -> int:
        return len(self._events)

    def __getitem__(self, index: int) -> dict[str, int | float]:
        return self._events[index - 1]

    async def __aenter__(self):
        if self.is_open:
            await self.close()
        await self.open()

        return self

    async def __aexit__(self, type_, value, traceback):
        await self.close()

    @property
    def event(self) -> int:
        return self._index + 1

    @property
    def rate(self) -> float:
        time_ = time.time() * 1000 - self._detector.start_time
        return self._events.__len__() / time_ * 1000

import asyncio
from copy import deepcopy
from multiprocessing import Pipe, Process
from multiprocessing.connection import Connection
from typing import Any, Callable, List, Optional, Union

import serial

from .detector import Detector
from .event_data_collection import EventData, EventDataCollection


# Type of callback function of DetectorPool.run() function
Callback = Union[Callable[[EventData, Any], Any], Callable[[EventData], Any]]


class DetectorPool:
    """Pool of multiple Detectors, which saves coincidence events, if multiple hits are registered in
    the threshold time."""

    def __init__(self, *ports: str, threshold: int = 15) -> None:
        self.threshold = threshold
        self._detectors = [Detector(port, False) for port in ports]
        self._index = -1

        #  TODO change the way data is registered
        self._event_data: EventData = EventData()  # make this obsolete

        # stores all the events
        self._data = EventDataCollection()

        self._first_coincidence_hit_time = 0

    async def open(self) -> "DetectorPool":
        """Opens asynchronously all ports for data collection"""
        self._index = -1
        self._data.clear()
        self._first_coincidence_hit_time = 0
        await asyncio.gather(*[port.open() for port in self._detectors])

        return self

    async def close(self) -> None:
        await asyncio.gather(*[port.close() for port in self._detectors])

    @property
    def is_open(self) -> bool:
        return self._detectors[0].is_open

    @property
    def detector_count(self):
        return len(self._detectors)

    @property
    def get_ports(self) -> List[str]:
        """Get a list of ports from the used detectors. The index at which a port
        is returned corresponds to the index in the event list."""
        return [dt.port for dt in self._detectors]

    @property
    def event(self) -> int:
        return self._index + 1

    @property
    def data(self) -> EventDataCollection:
        return self._data

    @staticmethod
    def _get_number_of_detector_hits(event: EventData) -> int:
        """Get the number of detectors that were hit during a coincidence event."""
        return len(event.keys())

    def run(self, events: int, callback: Optional[Callback] = None, *args: Any, ) -> (int, Optional[Exception]):
        """Run the detectors, until the specified number of coincidence events are registered
        Runs the callback function after every event, if one was specified. The Callback function takes
        the event data as first argument, while *args are the other arguments
        Opens and closes the Ports before and after the measurements.

        :parameters:
        :events: number of events to register before returning the results
        :callback: function that is run after every event
        :return: tuple of int and an optional Exception. The int is the number of events registered before an Exception was thrown
        """

        result = (0, None)

        async def run_():
            nonlocal result
            try:
                if self.is_open:
                    await self.close()
                await self.open()
                result = await self.async_run(events, callback, *args)
                await self.close()
            except Exception as e:
                result = result[0], e

        asyncio.run(run_())
        return result

    async def async_run(self, hits: int, callback: Optional[Callback] = None, *args: Any, ) -> (int, Optional[Exception]):
        """Same as self.run(), but as an asynchronous function."""
        finished = False
        counted_hits = 0
        lock = asyncio.Lock()

        if callback is not None:
            c1, c2 = Pipe()

            def callback_executor(connection: Connection) -> None:
                """Function that is meant to execute the callback function after every hit in a different parallel
                process to not block reading from ports."""

                for _ in range(hits):
                    hits_in_threshold = connection.recv()
                    if hits_in_threshold == "ERROR":
                        break
                    if callback is not None:
                        callback(hits_in_threshold, *args)

            callback_process = Process(target=callback_executor, args=(c1,))
            callback_process.start()

        async def run_detector(dt: Detector, dt_index: int) -> (int, Optional[Exception]):
            """reads hits asynchronously for the specified detector. if the hit time is not inside
            the threshold anymore, save the current event and begin a new one with the current hit time
            as first coincidence time."""

            nonlocal finished, counted_hits, lock
            exc = None

            while True:
                try:
                    await dt.measurement()
                except (asyncio.CancelledError, Exception, serial.SerialException) as e:
                    finished = True
                    exc = e
                    c2.send("ERROR")

                    break

                if dt[-1].comp_time - self._first_coincidence_hit_time <= self.threshold:
                    if dt_index in self._event_data.keys():
                        continue
                    self._event_data[dt_index] = dt[-1]
                else:
                    # print(self._event)
                    if len(self._event_data.keys()) > 1:
                        # TODO save data in collection
                        if callback is not None:
                            c2.send(self._event_data)
                        self._data.add_event(deepcopy(self._event_data))
                        async with lock:
                            counted_hits += 1

                        # print(f"hit {counted_hits} / {hits}")
                    if counted_hits == hits:
                        finished = True
                        # print("pool finished")
                        break

                    self._first_coincidence_hit_time = dt[-1].comp_time
                    self._event_data.clear()
                    self._event_data[dt_index] = dt[-1]

            return counted_hits, exc

        async def run_() -> (int, Optional[Exception]):
            tasks = [
                asyncio.create_task(
                    run_detector(self._detectors[i], i), name=self._detectors[i].port
                )
                for i in range(len(self._detectors))
            ]
            completed, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)

            for task in pending:
                task.cancel()

            return completed.pop().result()

        result = await run_()
        if callback is not None:
            callback_process.join()  # type: ignore
        return result

    def __len__(self) -> int:
        return len(self._data)

    async def __aenter__(self):
        if self.is_open:
            await self.close()
        await self.open()

        return self

    async def __aexit__(self, type_, value, traceback):
        await self.close()

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

    def run(self, event_count: int, callback=None, *args) -> (int, Optional[Exception]):
        if callback is None:
            return self.__run_process(event_count, None)

        c1, c2 = Pipe()

        def _process():
            c2.send(self.__run_process(event_count, c2))

        p = Process(target=_process, args=[])
        p.start()

        while True:
            data = c1.recv()
            if data is None:
                break

            callback(data, *args)

        data = c1.recv()
        print("data", data)
        self._data = data
        result = c1.recv()

        # this is bad
        # TODO find bug when sending premature results
        if result is None:
            c1.recv()
            result = c1.recv()

        p.join()

        return result

    async def async_run(self, event_count: int, callback = None, *args) -> (int, Optional[Exception]):
        if callback is None:
            return self.__run_process(event_count, None)

        c1, c2 = Pipe()

        def _process():
            c2.send(self.__run_process(event_count, c2))

        p = Process(target=_process, args=[])
        p.start()

        while True:
            data = c1.recv()
            if data is None:
                break

            await callback(data, *args)

        data = c1.recv()
        self._data = data
        result = c1.recv()

        p.join()

        return result

    def __run_process(self, event_count: int, connection: Optional[Connection] = None) -> (int, Optional[Exception]):
        """Process of gathering EventData, running on its own event loop. If a connection is given,
        EventData is sent through the connection after every event"""

        result = (0, None)

        async def func():
            nonlocal result

            async with self:
                result = await self.__async_run_process(event_count, connection)

        asyncio.run(func())

        return result

    async def __async_run_process(self, hits: int, connection: Optional[Connection] = None) -> (
            int, Optional[Exception]):
        finished = False
        counted_hits = 0
        lock = asyncio.Lock()

        async def run_detector(dt: Detector, dt_index: int) -> (int, Optional[Exception]):
            """reads hits asynchronously for the specified detector. if the hit time is not inside
            the threshold anymore, save the current event and begin a new one with the current hit time
            as first coincidence time."""

            nonlocal finished, counted_hits, lock
            exc = None

            while not finished:
                try:
                    await dt.measurement()
                except (asyncio.CancelledError, Exception, serial.SerialException) as e:
                    finished = True
                    exc = e
                    if connection is not None:
                        connection.send(None)  # Signal that the next time the EventDataCollection will be sent
                        connection.send(self._data)

                    break

                if dt[-1].comp_time - self._first_coincidence_hit_time <= self.threshold:
                    if dt_index in self._event_data.keys():
                        continue
                    self._event_data[dt_index] = dt[-1]
                else:
                    # print(self._event)
                    if len(self._event_data.keys()) > 1:
                        # TODO save data in collection
                        if connection is not None:
                            connection.send(self._event_data)
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
                    run_detector(self._detectors[i], i)  # , name=self._detectors[i].port
                )
                for i in range(len(self._detectors))
            ]
            completed, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)

            for task in pending:
                task.cancel()

            if connection is not None:
                connection.send(None)
                connection.send(self.data)

            return completed.pop().result()

        result = await run_()
        if connection is not None:
            connection.send(result)

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

import asyncio
from multiprocessing import Pipe, Process
from multiprocessing.connection import Connection
from typing import Any, Callable, Optional, Self
from icecream import ic

from .detector import Detector
from .event_data_collection import EventDataCollection


# Type of data stored from a hit
HitData = dict[str, int | float]

# Type of data stored with an event
EventData = list[HitData | None]

# Type of callback function of DetectorPool.run() function
Callback = Callable[[EventData, Any], Any] | Callable[[EventData], Any]


class DetectorPool:
    """Pool of multiple Detectors, which saves coincidence events, if multiple hits are registered in
    the threshold time."""

    def __init__(self, *ports: str, threshold: int = 15) -> None:
        self.threshold = threshold
        self._detectors = [Detector(port, False) for port in ports]
        self._index = -1

        #  TODO change the way data is registered
        self._event_data: EventData = [None] * len(self._detectors)  # make this obsolete
        self._event = {
            "detector_indices": [],
            "hit_data"        : [],
        }  # make this the new way of storing data

        # stores all the events
        self._data = EventDataCollection(len(ports))

        self._first_coincidence_hit_time = 0

    async def open(self) -> Self:
        """Opens asynchronously all ports for data collection"""
        self._index = -1
        # self._events.clear()
        self._data.clear()
        self._event_data = [None] * len(self._detectors)
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
    def get_ports(self) -> list[str]:
        """Get a list of ports from the used detectors. The index at which a port
        is returned corresponds to the index in the event list."""
        return [dt.port for dt in self._detectors]

    @property
    def event(self) -> int:
        return self._index + 1

    @property
    def data(self) -> EventDataCollection:
        return self._data

    def _get_number_of_detector_hits(self) -> int:
        """Get the number of detectors that were hit during a coincidence event."""
        sum_ = 0
        for _ in filter(lambda x: x is not None, self._event_data):
            sum_ += 1

        return sum_

    def run(self, hits: int, callback: Optional[Callback] = None, *args: Any, ) -> None:
        """Run the detectors, until the specified number of coincidence events are registered.
        Runs the callback function after every event, if one was specified. The Callback function takes
        the event data as first argument, while *args are the other arguments
        Opens and closes the Ports before and after the measurements.
        """

        async def run_():
            if self.is_open:
                await self.close()
            await self.open()
            await self._async_run(hits, callback, *args)
            await self.close()

        asyncio.run(run_())

    async def _async_run(self, hits: int, callback: Optional[Callback] = None, *args: Any, ) -> None:
        """Same as self.run(), but as an asynchronous function."""
        finished = False

        if callback is not None:
            c1, c2 = Pipe()

            def callback_executor(connection: Connection) -> None:
                """Function that is meant to execute the callback function after every hit in a different parallel
                process to not block reading from ports."""

                for _ in range(hits):
                    hits_in_threshold = connection.recv()
                    if callback is not None:
                        callback(hits_in_threshold, *args)

            callback_process = Process(target=callback_executor, args=(c1,))
            callback_process.start()

        async def run_detector(dt: Detector, dt_index: int):
            """reads hits asynchronously for the specified detector. if the hit time is not inside
            the threshold anymore, save the current event and begin a new one with the current hit time
            as first coincidence time."""

            nonlocal finished
            while True:
                try:
                    dct = await dt.measurement()
                except asyncio.CancelledError:
                    break
                if dt.comp_time - self._first_coincidence_hit_time <= self.threshold:
                    self._event_data[dt_index] = dct  # TODO delete this
                    if dt_index in self._event["detector_indices"]:
                        continue
                    self._event["detector_indices"].append(dt_index)
                    self._event["hit_data"].append(dct)
                else:
                    if len(self) == hits:
                        finished = True
                        break
                    # print(self._event)
                    if len(self._event["detector_indices"]) > 1:
                        # TODO save data in collection
                        if callback is not None:
                            c2.send(self._event)

                    # TODO delete this
                    if self._get_number_of_detector_hits() > 1:
                        self._data.add_event(self._event_data)
                        # if callback is not None:
                        #     c2.send(self._event_data)  # type: ignore
                    self._first_coincidence_hit_time = dt.comp_time
                    self._event_data = [None] * len(self._detectors)
                    self._event_data[dt_index] = dct
                    self._event = {
                        "detector_indices": [dt_index],
                        "hit_data"        : [dct],
                    }

        async def run_():
            tasks = [
                asyncio.create_task(
                    run_detector(self._detectors[i], i), name=self._detectors[i].port
                )
                for i in range(len(self._detectors))
            ]
            _, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)

            for task in pending:
                task.cancel()

        await run_()
        if callback is not None:
            callback_process.join()  # type: ignore

    def __len__(self) -> int:
        return len(self._data)

    async def __aenter__(self):
        if self.is_open:
            await self.close()
        await self.open()

        return self

    async def __aexit__(self, type_, value, traceback):
        await self.close()

import asyncio
import time
from asyncio import StreamReader, StreamWriter
from typing import Optional, List
import serial  # type: ignore
from serial_asyncio import open_serial_connection  # type: ignore

from .hit_data import HitData, parse_hit_data


class Detector:
    def __init__(self, port: str, save_data: bool = True) -> None:
        self.port = port
        self._reader: Optional[StreamReader] = None
        self._writer: Optional[StreamWriter] = None

        # list of all registered events by the detector
        # if save_data = false, _events should have length 1 with the data of the last hit
        self._events: List[HitData] = []
        self._start_time: int = 0
        self._index = -1
        self._save_data = save_data

        self._calibration = lambda x: 0

    async def open(self) -> "Detector":
        if self._reader is not None:
            raise Exception("port already open")
        reader, writer = await open_serial_connection(url=self.port, baudrate=9600)
        self._reader = reader
        self._writer = writer

        for _ in range(6):
            await reader.readline()

        # 0.9 is the delay time of the detector measurement (time in ms)
        self._start_time = int(time.time() * 1000) + 900
        self._events.clear()
        self._index = -1

        return self

    async def close(self) -> None:
        if self._writer is None:
            raise serial.PortNotOpenError

        self._writer.close()
        await self._writer.wait_closed()

        self._reader = None
        self._writer = None

    def run(self, hits: int) -> List[HitData]:
        """Run the detector until the specified number of hits was registered"""
        events: list = []

        async def run_():
            nonlocal events
            if self.is_open:
                await self.close()
            await self.open()
            for _ in range(hits):
                events.append(await self.measurement())
            await self.close()

        asyncio.run(run_())
        return events

    @property
    def is_open(self) -> bool:
        return self._reader is not None

    @property
    def start_time(self) -> float:
        """The time the detector was opened in milliseconds since the epoch."""
        return self._start_time

    async def measurement(self) -> HitData:
        if self._reader is None:
            raise serial.PortNotOpenError

        line = await self._reader.readline()
        output = line.decode()
        # data = output.split()

        # dct = self._make_dict_out_of_measurement(data, time.time() * 1000)
        hit_data = parse_hit_data(output, self._start_time)

        if self._save_data:
            # self._events.append(dct)
            self._events.append(hit_data)
            self._index = len(self._events) - 1
        else:
            self._index = 0
            self._events = [hit_data]

        return hit_data

    @property
    def rate(self) -> float:
        """Hit rate of the detector in # / s"""
        return (self[0].comp_time - self._start_time) / 1000

    def __iter__(self) -> "Detector":
        self._index = 0
        return self

    def __next__(self) -> HitData:
        if self._index == len(self._events):
            raise StopIteration

        res = self._events[self._index]
        self._index += 1

        return res

    async def __aenter__(self):
        if self.is_open:
            await self.close()
        await self.open()
        return self

    async def __aexit__(self, *args):
        await self.close()

    def __getitem__(self, index: int) -> HitData:
        return self._events[index]

    def __len__(self) -> int:
        return len(self._events)

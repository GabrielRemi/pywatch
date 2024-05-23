import asyncio
import time
from asyncio import StreamReader, StreamWriter
from typing import Any, Self

import serial  # type: ignore
from serial_asyncio import open_serial_connection  # type: ignore


class Detector:
    def __init__(self, port: str, save_data: bool = True) -> None:
        self.port = port
        self._reader: StreamReader | None = None
        self._writer: StreamWriter | None = None

        # output of the last readline() of the port split into a list
        self._output: list[str] = []

        # list of all registered events by the detector
        self._events: list[dict[str, int | float]] = []
        self._start_time: int = 0
        self._index = -1
        self._save_data = save_data

        self._calibration = lambda x: 0

    async def open(self) -> Self:
        if self._reader is not None:
            raise Exception("port already open")
        reader, writer = await open_serial_connection(url=self.port, baudrate=9600)
        self._reader = reader
        self._writer = writer

        for _ in range(6):
            await reader.readline()

        # 0.9 is the delay time of the detector measurement (time in ms)
        self._start_time = int(time.time() * 1000) + 900
        self._output.clear()
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

    def run(self, hits: int) -> list[dict[str, Any]]:
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

    async def measurement(self) -> dict[str, Any]:
        if self._reader is None:
            raise serial.PortNotOpenError

        line = await self._reader.readline()
        output = line.decode()
        data = output.split()

        dct = self._make_dict_out_of_measurement(data, time.time() * 1000)

        if self._save_data:
            self._events.append(dct)
            self._index = len(self._events) - 1
        else:
            self._index = 0
            self._events = [dct]
        self._output = data

        return dct

    def get_event(self, event_number: int) -> None:
        """load the data of the specified event"""
        if event_number < 1 or event_number > len(self._events):
            raise IndexError("event_number cannot be greater than total event count.")

        self._index = event_number - 1

    def get_list(self, key: str) -> list[float | int]:
        """Returns a list containing the data of all events specified by the key."""
        result = []

        for i in range(len(self)):
            result.append(self[i + 1][key])

        return result

    @property
    def output(self) -> str:
        return " ".join(self._output)

    @property
    def event(self) -> int:
        return self._index + 1

    @property
    def ard_time(self) -> int:
        """Time of event measured by the Arduino in ms"""
        return self._events[self._index]["ard_time"]  # type: ignore

    @property
    def comp_time(self) -> int:
        """Time of event measured by the computer in ms"""
        return self._events[self._index]["comp_time"]  # type: ignore

    @property
    def rate(self) -> float:
        """Hit rate of the detector in # / s"""
        return (self.ard_time - self._start_time) / 1000

    def _make_dict_out_of_measurement(
        self, output: list[str], time_
    ) -> dict[str, int | float]:
        """Take the output string and save all the data in a dictionary"""
        return {
            "ard_time"    : int(output[1]) + self._start_time + self._calibration(time_),
            "amplitude"   : int(output[2]),
            "sipm_voltage": float(output[3]),
            "dead_time"   : int(output[4]),
            "temp"        : float(output[5]),
            "comp_time"   : int(time_),
        }

    def __iter__(self) -> Self:
        self._index = 0
        return self

    def __next__(self) -> dict[str, Any]:
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

    def __getitem__(self, index: int) -> dict[str, int | float]:
        return self._events[index - 1]

    def __len__(self) -> int:
        return len(self._events)

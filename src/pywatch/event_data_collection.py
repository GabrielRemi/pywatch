import json

from typing import Self

# Type of data stored from a hit
HitData = dict[str, int | float]

# Type of data stored with an event
EventData = list[HitData | None]


class EventDataCollection:
    """Class for storing data efficiently registered in detector events"""

    _keys: list[str] = [
        "comp_time",
        "ard_time",
        "amplitude",
        "sipm_voltage",
        "dead_time",
        "temp",
    ]

    def __init__(self, detector_count: int):
        self._dct: dict = dict()
        self._detector_count = detector_count
        for key in self._keys:
            self._dct[key] = []
            for _ in range(detector_count):
                self._dct[key].append([])

        self._len = 0
        self._index = 0  # Index needed for the Iterator

    @property
    def len(self) -> int:
        return self._len

    def add_event(self, data: EventData) -> None:
        for key in self._keys:
            for index, hit in enumerate(data):
                if hit is not None:
                    self._dct[key][index].append(hit[key])
                else:
                    self._dct[key][index].append(None)

        self._len += 1

    def get_event(self, index: int) -> EventData:
        event_data: EventData = []
        for port in range(self._detector_count):
            dct = dict()
            for key in self._keys:
                dct[key] = self._dct[key][port][index]
            if dct["comp_time"] is None:
                event_data.append(None)
            else:
                event_data.append(dct)

        return event_data

    def clear(self) -> None:
        """Clear all the data from memory."""
        for key in self._keys:
            for index in range(self._detector_count):
                self._dct[key][index].clear()
        self._len = 0

    def to_json(self, file_path: str) -> None:
        with open(file_path, "w", encoding="utf-8") as file:
            json.dump(self._dct, file, indent=2)

    def __len__(self) -> int:
        return self._len

    def __getitem__(self, index: int) -> EventData:
        return self.get_event(index)

    def __iter__(self) -> Self:
        self._index = 0
        return self

    def __next__(self) -> EventData:
        if self._index == self._len:
            raise StopIteration
        self._index += 1
        return self[self._index - 1]

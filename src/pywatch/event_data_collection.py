import json
from typing import Iterator

from dataclasses import dataclass
from typing import Self

from .hit_data import HitData


# Type of data stored from a hit
# HitData = dict[str, int | float]


# Type of data stored with an event
# EventData = list[HitData | None]
EventData = dict[int, HitData]


class EventDataCollection:
    """Class for storing data efficiently registered in detector events"""

    def __init__(self):
        # TODO make memory efficient
        self._events: list[EventData] = []

        self._len = 0
        # self._index = 0  # Index needed for the Iterator

    @property
    def len(self) -> int:
        return self._len

    def add_event(self, data: EventData) -> None:
        # TODO make storing data more memory efficient

        # Check if data has the right type
        if not isinstance(data, dict):
            raise TypeError("data added to EventDataCollection must be a dict")

        type_key = set([type(key) for key in data.keys()])
        type_value = set([type(value) for value in data.values()])

        if type_key != {int} or type_value != {HitData}:
            raise TypeError("data added to EventDataCollection must be a dict with "
                            "integer keys and HitData as values.")

        self._events.append(data)

        self._len += 1

    def clear(self) -> None:
        """Clear all the data from memory."""
        self._events.clear()
        self._len = 0

    def to_json(self, file_path: str) -> None:
        raise NotImplementedError

    def __len__(self) -> int:
        return self._len

    def __getitem__(self, index: int) -> EventData:
        return self._events[index]

    def __iter__(self) -> Iterator[EventData]:
        return self._events.__iter__()


# TODO REWORK

def load_event_data_collection_from_json(file_path: str) -> EventDataCollection:
    """Loads the EventData made in a measurement into the EventDataCollection """
    with open(file_path, "r", encoding="utf-8") as file:
        dct = json.load(file)

    detector_count = len(dct["comp_time"])
    data = EventDataCollection(detector_count)

    data._dct = dct  # type: ignore
    data._len = dct["comp_time"][0].__len__()

    return data

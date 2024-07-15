import json
from typing import Iterator, Union, Dict, List

from .hit_data import HitData


class EventData(dict):
    def to_dict(self) -> Dict[int, Dict[str, Union[int, float]]]:
        new_dct = dict()
        for key, value in self.items():
            new_dct[key] = value.__dict__

        return new_dct


class EventDataCollection:
    """Class for storing data efficiently registered in detector events"""

    def __init__(self):
        # TODO make memory efficient
        self._events: List[EventData] = []

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
        with open(file_path, "w") as file:
            json.dump([x.to_dict() for x in self._events], file, indent=4)

    def __len__(self) -> int:
        return self._len

    def __getitem__(self, index: int) -> EventData:
        return self._events[index]

    def __iter__(self) -> Iterator[EventData]:
        return self._events.__iter__()


# TODO HANDLE EXCEPTIONS
def load_event_data_collection_from_json(file_path: str) -> EventDataCollection:
    """Loads the EventData made in a measurement into the EventDataCollection """
    with open(file_path, "r", encoding="utf-8") as file:
        raw = json.load(file)

    collection = EventDataCollection()
    for data in raw:
        event = EventData()
        for key, value in data.items():
            event[int(key)] = HitData(**value)

        collection.add_event(event)

    return collection

import json
from timeit import timeit

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

    def add_event(self, data: EventData) -> None:
        for key in self._keys:
            for index, hit in enumerate(data):
                if hit is not None:
                    self._dct[key][index].append(hit[key])
                else:
                    self._dct[key][index].append(None)

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

    def save_to_json(self, filename: str) -> None:
        with open(filename, "w") as file:
            json.dump(self._dct, file)


data = EventDataCollection(4)

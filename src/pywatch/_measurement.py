import importlib.util
import json
import sys
import types
from typing import Any, Callable, Union

from .detector_pool import DetectorPool
from .event_data_collection import EventData


# python_file = sys.argv[1]

# print(python_file)


callback_wo = Callable[[EventData], Any]
callback_w = Callable[[EventData, Any], Any]
callback = Union[callback_wo, callback_w]


# COMMANDLINE ARGUMENT PARSING

def import_module_from_path(module_name: str, file_path: str):
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module_ = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module_)
    return module_


def parse_commandline_arguments(index: int) -> types.ModuleType:
    """Get the file with all the Data needed for a measurement. The python script needs the following attributes:

    callback: Callable[[EventData, Any], Any]
    PORTS: List[str] with the names of the detector ports
    SAVE_FILE: file path for saving the collected data
    EVENT_COUNT: int with the number of events to record
    THRESHOLD: Time Threshold, in which multiple hits are defined as coincidence events

    :param index: Index of command line argument of python script path

    :returns: Tuple of python module, number of events to record, callback function (optional) and
    the name of the save file for data collection"""

    path = sys.argv[index]
    module_ = import_module_from_path("imported_module_5123098u", path)

    # TODO check for types of attributes

    if not hasattr(module_, "callback"):
        raise NotImplementedError(f"callback function not implemented in {path}")
    if not hasattr(module_, "PORTS"):
        raise NotImplementedError(f"PORTS not implemented in {path}")
    if not hasattr(module_, "SAVE_FILE"):
        raise NotImplementedError(f"SAVE_FILE not implemented in {path}")
    if not hasattr(module_, "EVENT_COUNT"):
        raise NotImplementedError(f"EVENT_COUNT not implemented in {path}")
    if not hasattr(module_, "THRESHOLD"):
        module_.THRESHOLD = 10
        # raise NotImplementedError(f"THRESHOLD not implemented in {path}")

    return module_


def measurement(index: int):
    module_ = parse_commandline_arguments(index)

    pool = DetectorPool(*module_.PORTS, threshold=module_.THRESHOLD)
    data: list = []

    def save():
        nonlocal data
        with open(module_.SAVE_FILE, "w") as f:
            json.dump(data, f, indent=4)

    i = 0

    def outer_callback(event):
        nonlocal i
        # data.append(event.to_dict())
        i += 1
        # print(i)
        print(i, end=" ")
        sys.stdout.flush()
        module_.callback(event)

        # save()

    print(f"starting measurement for {module_.EVENT_COUNT} events")

    events_run = 0
    tries = 5
    last_event_count = -1
    while events_run < module_.EVENT_COUNT:
        event_count, e = pool.run(module_.EVENT_COUNT - events_run, callback)
        if event_count == 0 and last_event_count == 0:
            tries -= 1
        print(event_count, repr(e), sep="\n", end="\n\n")
        events_run += event_count

        for event in pool.data:
            data.append(event.to_dict())

        if tries == 1:
            print("Failed to fetch data 5 times in a row. aborting.")
            break

        last_event_count = event_count

    save()
    print("data stored successfully")

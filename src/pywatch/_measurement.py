import importlib.util
import json
import sys
import types
from typing import Any, Callable, Union
from warnings import warn

from .detector_pool import DetectorPool
from .event_data_collection import EventData


# python_file = sys.argv[1]

# print(python_file)


callback_wo = Callable[[EventData], Any]
callback_w = Callable[[EventData, Any], Any]
callback = Union[callback_wo, callback_w]


def is_list_with_type(ls, type_) -> bool:
    if not isinstance(ls, list):
        return False

    for x in ls:
        if not isinstance(x, type_):
            return False

    return True


# COMMANDLINE ARGUMENT PARSING

def import_module_from_path(module_name: str, file_path: str):
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module_ = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module_)
    return module_


def parse_module_from_string(script_path: str) -> types.ModuleType:
    """Get the file with all the Data needed for a measurement. The python script needs the following attributes:

    callback: Callable[[EventData, Any], Any]
    PORTS: List[str] with the names of the detector ports
    SAVE_FILE: file path for saving the collected data
    EVENT_COUNT: int with the number of events to record
    THRESHOLD: Time Threshold, in which multiple hits are defined as coincidence events

    :param script_path: Path of python script

    :returns: Tuple of python module, number of events to record, callback function (optional) and
    the name of the save file for data collection"""

    module_ = import_module_from_path("imported_module_5123098u", script_path)

    # TODO check for types of attributes

    if not hasattr(module_, "callback"):
        # raise NotImplementedError(f"callback function not implemented in {path}")
        module_.callback = None
        # raise Warning("callback function was not specified")
        warn("callback function was not specified", RuntimeWarning)
    if module_.callback is not None:
        try:
            module_.callback(EventData(dict()))
        except Exception:
            raise TypeError("callback function must be a function, that takes EventData as an argument")

    if not hasattr(module_, "PORTS"):
        raise NotImplementedError(f"PORTS not implemented in {script_path}")
    if not is_list_with_type(module_.PORTS, str):
        raise TypeError("PORTS is not a list of strings")

    if not hasattr(module_, "SAVE_FILE"):
        module_.SAVE_FILE = None
    if module_.SAVE_FILE is not None and not isinstance(module_.SAVE_FILE, str):
        raise TypeError("SAVE_FILE is not a string")

        # raise NotImplementedError(f"SAVE_FILE not implemented in {path}")
    if not hasattr(module_, "EVENT_COUNT"):
        raise NotImplementedError(f"EVENT_COUNT not implemented in {script_path}")
    if not isinstance(module_.EVENT_COUNT, int):
        raise TypeError("EVENT_COUNT must be an integer")

    if not hasattr(module_, "THRESHOLD"):
        module_.THRESHOLD = 10
    if not isinstance(module_.THRESHOLD, int):
        raise TypeError("THRESHOLD must be an integer")

    if hasattr(module_, "SAVE_CHECKPOINT"):
        if not isinstance(module_.SAVE_CHECKPOINT, int):
            raise TypeError("SAVE_CHECKPOINT must be an integer")
    else:
        module_.SAVE_CHECKPOINT = None

    return module_


def measurement_from_script(script_path: str):
    module_ = parse_module_from_string(script_path)

    pool = DetectorPool(*module_.PORTS, threshold=module_.THRESHOLD)
    data: list = []

    def save():
        nonlocal data
        with open(module_.SAVE_FILE, "w") as f:
            json.dump({"event_count": len(data), "data": data}, f, indent=4)

        print(f"{len(data)} events saved")

    i = 0
    next_checkpoint = module_.SAVE_CHECKPOINT

    def outer_callback(event):
        nonlocal i, next_checkpoint, data
        data.append(event.to_dict())
        # data.append(event.to_dict())
        i += 1
        if next_checkpoint is not None:
            if i == next_checkpoint:
                save()
                next_checkpoint += module_.SAVE_CHECKPOINT
        # print(i)
        print(i, end=" ")
        sys.stdout.flush()
        if module_.callback is not None:
            module_.callback(event)

        # save()

    print(f"starting measurement for {module_.EVENT_COUNT} events")

    events_run = 0
    tries = 5
    last_event_count = -1
    while events_run < module_.EVENT_COUNT:
        event_count, e = pool.run(module_.EVENT_COUNT - events_run, outer_callback)
        if event_count == 0 and last_event_count == 0:
            tries -= 1
        print(event_count, repr(e), sep="\n", end="\n\n")
        events_run += event_count

        if len(data) == 0:
            for event in pool.data:
                data.append(event.to_dict())

        if tries == 1:
            print("Failed to fetch data 5 times in a row. aborting.")
            break

        last_event_count = event_count

    if module_.SAVE_FILE is not None:
        save()
        print("data stored successfully")
    else:
        print("measurement finished successfully")

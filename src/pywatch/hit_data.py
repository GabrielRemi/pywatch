from dataclasses import dataclass
import time


@dataclass
class HitData:
    comp_time: int
    ard_time: int
    amplitude: int
    sipm_voltage: float
    dead_time: int
    temp: float


def parse_hit_data(output: str, start_time_ms: int) -> HitData:
    """Parse hit data from CosmicWatch detector output.
    :param output: Output send through usb port from CosmicWatch Detector.
    :param start_time_ms: Computer time, when the Detector was opened."""

    data = output.split()

    comp_time = int(time.time() * 1000)
    ard_time = int(data[1]) + start_time_ms
    amplitude = int(data[2])
    sipm_voltage = float(data[3])
    dead_time = int(data[4])
    temp = float(data[5])

    return HitData(comp_time, ard_time, amplitude, sipm_voltage, dead_time, temp)

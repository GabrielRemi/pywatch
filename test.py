import asyncio
import time
from timeit import timeit

from pywatch import DetectorPool, Detector
from pywatch.event_data_collection import EventDataCollection
from pywatch.hit_data import HitData, parse_hit_data


# pool = DetectorPool("/dev/ttyUSB0", "/dev/ttyUSB1", threshold=10)

# pool.run(10, callback=lambda data: print(data))

dt = Detector("/dev/ttyUSB0")


async def main():
    async with dt:
        for _ in range(10):
            await dt.measurement()
            print(dt[0])


# asyncio.run(main())
hits = dt.run(10)

for hit in dt:
    print(hit)

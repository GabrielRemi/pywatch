import sys

from ._measurement import measurement_from_script


if len(sys.argv) > 1:
    if sys.argv[1] == "--measurement":
        path = sys.argv[2]
        measurement_from_script(path)

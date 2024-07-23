import sys

from ._measurement import measurement


if len(sys.argv) > 1:
    if sys.argv[1] == "--measurement":
        measurement(2)

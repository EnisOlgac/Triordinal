"""Runs the DTree benchmarks from the repository (same as ``python -m triordinal.dtree.bench``).

    python benchmarks/bench.py [--quick] [--dynamic] [--note "..."] [--no-save] [sizes...]

The benchmark code lives in the package (triordinal/dtree/bench.py), so users who installed
triordinal-dtree can run it as well.
"""

import os
import sys

_PY = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(_PY, "dtree"))
sys.path.insert(0, os.path.join(_PY, "dlist"))

from triordinal.dtree.bench import main  # noqa: E402

if __name__ == "__main__":
    main()

"""Run the desktop editor using its isolated Python environment."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

if __name__ == "__main__":
    from lumalock.app import main

    raise SystemExit(main())

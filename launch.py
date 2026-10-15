"""Start the local AI service and open its browser workspace."""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")

if __name__ == "__main__":
    from lumalock.webapp.server import main

    raise SystemExit(main())

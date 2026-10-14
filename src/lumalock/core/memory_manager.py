"""Sequential model lifetime and OOM retries with a final CPU attempt."""

import gc
import importlib.util
from threading import RLock

from lumalock.core.exceptions import UserError


def release_memory() -> None:
    gc.collect()
    if importlib.util.find_spec("torch"):
        import torch

        if torch.cuda.is_available():
            torch.cuda.empty_cache()


class MemoryManager:
    def __init__(self):
        self.lock = RLock()

    def run(self, operation, device="cuda", tile_size=512, on_retry=lambda device, size: None):
        attempts = [(device, size) for size in (tile_size, 384, 256) if size <= tile_size]
        if device != "cpu":
            attempts.append(("cpu", 256))
        with self.lock:
            for index, (target, size) in enumerate(dict.fromkeys(attempts)):
                if index:
                    on_retry(target, size)
                try:
                    return operation(target, size)
                except (RuntimeError, MemoryError) as exc:
                    if isinstance(exc, RuntimeError) and "out of memory" not in str(exc).lower():
                        raise
                    release_memory()
            raise UserError("Not enough memory. Try a smaller image or a lightweight backend.")

"""Small display previews; downloads and immutable originals remain full resolution."""

import io
import threading
from collections import OrderedDict

from PIL import Image


class PreviewCache:
    def __init__(self, limit=8 * 1024**2):
        self.limit = limit
        self.size = 0
        self.items = OrderedDict()
        self.lock = threading.Lock()

    def clear(self):
        with self.lock:
            self.items.clear()
            self.size = 0

    def get(self, path, maximum):
        stat = path.stat()
        key = (str(path), stat.st_mtime_ns, stat.st_size, maximum)
        # Serialize decoding so opening a long chat cannot start dozens of full-size decoders.
        with self.lock:
            if key in self.items:
                self.items.move_to_end(key)
                return self.items[key]
            with Image.open(path) as image:
                image.thumbnail((maximum, maximum), Image.Resampling.LANCZOS, reducing_gap=2)
                buffer = io.BytesIO()
                image.convert("RGB").save(buffer, "WEBP", quality=85)
            result = buffer.getvalue()
            if len(result) <= self.limit:
                while self.items and self.size + len(result) > self.limit:
                    _, expired = self.items.popitem(last=False)
                    self.size -= len(expired)
                self.items[key] = result
                self.size += len(result)
            return result

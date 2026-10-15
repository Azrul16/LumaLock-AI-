"""Conservative stage estimates based only on observed progress and elapsed time."""

import time


class JobTiming:
    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.started = clock()
        self.finished = None
        self.baseline = None
        self.latest = None
        self.rate = None
        self.interval = 0

    def update(self, value):
        now = self.clock()
        if value < 0:
            self.baseline = self.latest = self.rate = None
            return
        if self.latest is None or value < self.latest[1]:
            self.baseline = self.latest = (now, value)
            self.rate = None
            return
        if value > self.latest[1]:
            self.interval = now - self.latest[0]
            self.latest = (now, value)
            elapsed = now - self.baseline[0]
            gained = value - self.baseline[1]
            if elapsed >= 2 and gained >= 1:
                self.rate = gained / elapsed

    def snapshot(self, active=True):
        now = self.finished if self.finished is not None else self.clock()
        eta = None
        if (
            active
            and self.rate
            and self.latest
            and now - self.latest[0] <= max(15, 2 * self.interval)
        ):
            remaining = (100 - self.latest[1]) / self.rate - (now - self.latest[0])
            if remaining > 0:
                eta = round(remaining)
        return {"elapsed_seconds": round(now - self.started), "eta_seconds": eta}

    def finish(self):
        self.finished = self.clock()

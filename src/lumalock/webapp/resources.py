"""Cached system telemetry. Sampling never imports torch or runs on the HTTP loop."""

import csv
import math
import os
import subprocess
import threading
import time
from pathlib import Path

import psutil


def number(value):
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (ValueError, TypeError):
        return None


def gpu_sample():
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=2,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        if result.returncode:
            return None
        devices = []
        for row in csv.reader(result.stdout.splitlines(), skipinitialspace=True):
            if len(row) != 5:
                continue
            name, utilization, used, total, temperature = row
            devices.append(
                {
                    "name": name,
                    "percent": number(utilization),
                    "used_mib": number(used),
                    "total_mib": number(total),
                    "temperature_c": number(temperature),
                }
            )
        return max(devices, key=lambda device: device["total_mib"] or 0, default=None)
    except (OSError, subprocess.TimeoutExpired):
        return None


class ResourceMonitor:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.lock = threading.Lock()
        self.stopped = threading.Event()
        self.thread = None
        self.sample = {"measured_at": None, "cpu_percent": None, "gpu": None}
        self.last_io = None
        self.last_time = None
        self.last_gpu = None
        self.gpu_time = -float("inf")

    def start(self):
        self.thread = threading.Thread(target=self._run, daemon=True, name="system-resources")
        self.thread.start()

    def close(self):
        self.stopped.set()
        if self.thread:
            self.thread.join(timeout=4)

    def snapshot(self):
        with self.lock:
            result = dict(self.sample)
        result["stale"] = result["measured_at"] is None or time.time() - result["measured_at"] > 10
        return result

    def _run(self):
        psutil.cpu_percent(
            interval=None
        )  # Prime this thread's counter; first zero is not a measurement.
        while not self.stopped.wait(2):
            try:
                self.collect()
            except (OSError, psutil.Error):
                # Retain a timestamped, eventually stale sample instead of inventing zeros.
                continue

    def collect(self):
        now = time.monotonic()
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage(str(self.directory))
        io = psutil.disk_io_counters()
        read_rate = write_rate = None
        if io and self.last_io and now > self.last_time:
            seconds = now - self.last_time
            read_rate = max(0, io.read_bytes - self.last_io.read_bytes) / seconds / 1024**2
            write_rate = max(0, io.write_bytes - self.last_io.write_bytes) / seconds / 1024**2
        self.last_io, self.last_time = io, now
        if now - self.gpu_time >= 5:
            self.last_gpu, self.gpu_time = gpu_sample(), now
        sample = {
            "measured_at": time.time(),
            "cpu_percent": psutil.cpu_percent(interval=None),
            "ram_percent": memory.percent,
            "ram_used_gib": (memory.total - memory.available) / 1024**3,
            "ram_total_gib": memory.total / 1024**3,
            "ram_available_gib": memory.available / 1024**3,
            "disk_used_percent": disk.percent,
            "disk_free_gib": disk.free / 1024**3,
            "disk_drive": self.directory.resolve().anchor,
            "disk_read_mib_s": read_rate,
            "disk_write_mib_s": write_rate,
            "gpu": self.last_gpu,
        }
        with self.lock:
            self.sample = sample

"""Detect real hardware without requiring a tensor runtime for core launch."""

import platform
import subprocess
from dataclasses import asdict, dataclass

import psutil


@dataclass(frozen=True)
class Hardware:
    ram_gb: float
    gpu: str
    vram_gb: float
    profile: str
    python: str
    os: str

    def to_dict(self) -> dict:
        return asdict(self)


def detect_hardware() -> Hardware:
    ram = psutil.virtual_memory().total / 1024**3
    gpu, vram = "CPU", 0.0
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=5,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if result.returncode == 0:
            devices = [line.rsplit(",", 1) for line in result.stdout.strip().splitlines()]
            name, memory = max(devices, key=lambda device: float(device[1]))
            gpu, vram = name.strip(), float(memory) / 1024
    except (OSError, ValueError, subprocess.TimeoutExpired):
        pass
    profile = "LOW_MEMORY" if vram <= 4 or ram <= 8 else "STANDARD" if vram <= 12 else "ULTRA"
    return Hardware(
        round(ram, 2), gpu, round(vram, 2), profile, platform.python_version(), platform.platform()
    )

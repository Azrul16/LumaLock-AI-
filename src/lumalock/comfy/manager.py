"""Own a private, loopback-only ComfyUI process; never open its browser UI."""

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import requests
import yaml

from lumalock.core.config import data_dir, load_settings, model_dir, resource_path
from lumalock.core.exceptions import Cancelled, UserError
from lumalock.core.hardware import detect_hardware


def runtime_root():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent / "runtime" / "comfyui"
    return resource_path("runtime/comfyui")


def device_flags(device, vram_gb, stronger_offload=False):
    if device == "cuda" and vram_gb <= 0:
        raise UserError("NVIDIA GPU mode was selected, but no NVIDIA GPU was detected.")
    if device == "cpu" or vram_gb <= 0:
        return ["--cpu", "--cpu-vae"]
    flags = ["--novram" if stronger_offload or vram_gb <= 4 else "--lowvram"]
    # CUDA is also used for the tiled VAE on the first attempt. Only the stronger
    # memory-recovery attempt deliberately offloads it to CPU.
    if stronger_offload:
        flags.append("--cpu-vae")
    return flags


def transfer_flags(device, vram_gb, stronger_offload=False):
    if device != "cpu" and vram_gb > 0 and not stronger_offload:
        return ["--async-offload", "1"]
    return ["--disable-async-offload"]


class ComfyManager:
    def __init__(self):
        self.process = None
        self.log = None
        self.url = None
        self.log_start = 0
        self.worker_group = None
        self.http = requests.Session()
        self.http.trust_env = False

    def start(self, cancelled, progress, stronger_offload=False):
        root = runtime_root()
        if not (root / "main.py").is_file():
            raise UserError(
                "The bundled local ComfyUI runtime is missing. Repair the distribution."
            )
        from lumalock.comfy.compat import patch_gguf_runtime

        patch_gguf_runtime(root)
        python = Path(sys.executable)
        if getattr(sys, "frozen", False):
            python = python.parent / "runtime" / "python" / "python.exe"
        if not python.is_file():
            raise UserError(
                "The bundled Python runtime is missing. Keep the full distribution together."
            )
        working = data_dir() / "backend"
        working.mkdir(parents=True, exist_ok=True)
        for name in ("input", "output", "user"):
            (working / name).mkdir(parents=True, exist_ok=True)
        config = working / "model-paths.yaml"
        config.write_text(
            yaml.safe_dump(
                {
                    "lumalock": {
                        "base_path": str(model_dir() / "flux"),
                        "diffusion_models": "diffusion_models",
                        "text_encoders": "text_encoders",
                        "vae": "vae",
                    }
                }
            ),
            encoding="utf-8",
        )
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        self.url = f"http://127.0.0.1:{port}"
        hardware = detect_hardware()
        flags = [
            "--listen",
            "127.0.0.1",
            "--port",
            str(port),
            "--disable-auto-launch",
            "--offline",
            "--disable-metadata",
            "--cache-none",
            "--disable-smart-memory",
            "--disable-pinned-memory",
            "--mmap-torch-files",
            "--disable-dynamic-vram",
            "--reserve-vram",
            "1.6" if stronger_offload else "1.2",
            "--disable-all-custom-nodes",
            "--whitelist-custom-nodes",
            "ComfyUI-GGUF",
            "--extra-model-paths-config",
            str(config),
            "--input-directory",
            str(working / "input"),
            "--output-directory",
            str(working / "output"),
            "--user-directory",
            str(working / "user"),
        ]
        flags.extend(device_flags(load_settings().device, hardware.vram_gb, stronger_offload))
        flags.extend(transfer_flags(load_settings().device, hardware.vram_gb, stronger_offload))
        env = dict(
            os.environ,
            HF_HUB_OFFLINE="1",
            TRANSFORMERS_OFFLINE="1",
            HF_HUB_DISABLE_TELEMETRY="1",
            PYTHONNOUSERSITE="1",
            # Avoid competing BLAS pools and leave CPU capacity for the local UI/server.
            OMP_NUM_THREADS=str(max(1, min(4, (os.cpu_count() or 2) - 1))),
            MKL_NUM_THREADS=str(max(1, min(4, (os.cpu_count() or 2) - 1))),
            OPENBLAS_NUM_THREADS="1",
        )
        log_path = working / "backend.log"
        self.log_start = log_path.stat().st_size if log_path.exists() else 0
        self.log = log_path.open("ab")
        self.process = subprocess.Popen(
            [str(python), str(root / "main.py"), *flags],
            cwd=root,
            env=env,
            stdout=self.log,
            stderr=self.log,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        from lumalock.core.process_lifetime import ChildProcessGroup

        try:
            self.worker_group = ChildProcessGroup()
            self.worker_group.attach(self.process)
        except Exception:
            self.stop()
            raise
        progress(-1, "Starting local FLUX runtime…")
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            if cancelled():
                self.stop()
                raise Cancelled("Backend startup cancelled.")
            if self.process.poll() is not None:
                self.stop()
                raise UserError(
                    "Local FLUX runtime could not start. See backend/backend.log in the data folder."
                )
            try:
                response = self.http.get(self.url + "/system_stats", timeout=1)
                response.raise_for_status()
                selected = load_settings().device
                if selected == "cuda" and not any(
                    item.get("type") == "cuda" for item in response.json().get("devices", [])
                ):
                    self.stop()
                    raise UserError(
                        "GPU mode was selected, but the runtime did not initialize CUDA. Check the NVIDIA driver and project-local PyTorch installation."
                    )
                return self
            except requests.RequestException:
                time.sleep(0.3)
        self.stop()
        raise UserError("Local FLUX startup timed out. See the backend log.")

    def stop(self):
        if self.process:
            if self.process.poll() is None:
                self.process.terminate()
                try:
                    self.process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait(timeout=10)
            self.process = None
        if self.worker_group:
            self.worker_group.close()
            self.worker_group = None
        if self.log:
            self.log.close()
            self.log = None
        self.http.close()

    def memory_failed(self):
        path = data_dir() / "backend" / "backend.log"
        try:
            with path.open("rb") as stream:
                stream.seek(max(self.log_start, path.stat().st_size - 128 * 1024))
                text = stream.read().decode("utf-8", errors="replace").lower()
            return "out of memory" in text or "got an oom" in text
        except OSError:
            return False

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


class ComfyManager:
    def __init__(self):
        self.process = None
        self.log = None
        self.url = None
        self.http = requests.Session()
        self.http.trust_env = False

    def start(self, cancelled, progress, stronger_offload=False):
        root = runtime_root()
        if not (root / "main.py").is_file():
            raise UserError(
                "The bundled local ComfyUI runtime is missing. Repair the distribution."
            )
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
            "--disable-async-offload",
            "--mmap-torch-files",
            "--disable-dynamic-vram",
            "--novram" if stronger_offload else "--lowvram",
            "--cpu-vae",
            "--reserve-vram",
            "0.8",
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
        if load_settings().device == "cpu" or detect_hardware().vram_gb == 0:
            flags.remove("--novram" if stronger_offload else "--lowvram")
            flags.append("--cpu")
        env = dict(
            os.environ,
            HF_HUB_OFFLINE="1",
            TRANSFORMERS_OFFLINE="1",
            HF_HUB_DISABLE_TELEMETRY="1",
            PYTHONNOUSERSITE="1",
        )
        self.log = (working / "backend.log").open("ab")
        self.process = subprocess.Popen(
            [str(python), str(root / "main.py"), *flags],
            cwd=root,
            env=env,
            stdout=self.log,
            stderr=self.log,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
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
        if self.log:
            self.log.close()
            self.log = None
        self.http.close()

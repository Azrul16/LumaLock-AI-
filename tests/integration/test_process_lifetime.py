"""Windows must reclaim owned inference workers even if the server is terminated."""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import psutil
import pytest


@pytest.mark.skipif(os.name != "nt", reason="Windows job-object lifetime")
def test_owned_worker_dies_when_server_is_terminated(tmp_path):
    marker = tmp_path / "worker.pid"
    script = tmp_path / "owner.py"
    script.write_text(
        "import subprocess, sys, time\n"
        "from pathlib import Path\n"
        "from lumalock.core.process_lifetime import ChildProcessGroup\n"
        "group = ChildProcessGroup()\n"
        "worker = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(120)'])\n"
        "group.attach(worker)\n"
        f"Path({str(marker)!r}).write_text(str(worker.pid))\n"
        "time.sleep(120)\n",
        encoding="utf-8",
    )
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(Path(__file__).resolve().parents[2] / "src")
    owner = subprocess.Popen([sys.executable, str(script)], env=environment)
    worker = None
    try:
        deadline = time.monotonic() + 15
        while not marker.exists() and owner.poll() is None and time.monotonic() < deadline:
            time.sleep(0.1)
        assert marker.exists(), "Worker was not assigned to the server's job"
        worker = psutil.Process(int(marker.read_text()))
        assert worker.is_running()
        owner.kill()
        owner.wait(timeout=10)
        worker.wait(timeout=10)
        assert not worker.is_running()
    finally:
        if owner.poll() is None:
            owner.kill()
            owner.wait(timeout=10)
        if worker and worker.is_running():
            worker.kill()


@pytest.mark.skipif(os.name != "nt", reason="Windows CMD launcher")
def test_closing_launcher_cmd_stops_web_server(tmp_path):
    root = Path(__file__).resolve().parents[2]
    environment = os.environ.copy()
    environment["LUMALOCK_DATA_DIR"] = str(tmp_path)
    launcher = subprocess.Popen(
        [
            "cmd.exe",
            "/d",
            "/c",
            "call",
            str(root / "Launch LumaLock AI.cmd"),
            "--no-browser",
            "--port",
            "0",
        ],
        cwd=root,
        env=environment,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    server = None
    try:
        info = tmp_path / "server.json"
        deadline = time.monotonic() + 20
        while not info.exists() and launcher.poll() is None and time.monotonic() < deadline:
            time.sleep(0.1)
        assert info.exists(), "CMD did not launch the server"
        server = psutil.Process(json.loads(info.read_text())["pid"])
        launcher.kill()
        launcher.wait(timeout=10)
        server.wait(timeout=15)
        assert not server.is_running()
    finally:
        if launcher.poll() is None:
            launcher.kill()
            launcher.wait(timeout=10)
        if server and server.is_running():
            server.kill()

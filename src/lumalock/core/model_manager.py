"""Two curated local AI models, complete storage preflight and checksum verification."""

import hashlib
import importlib.util
import json
import logging
import os
import shutil
import threading
from pathlib import Path

import yaml

from lumalock.core.config import load_settings, model_dir, resource_path
from lumalock.core.exceptions import Cancelled, UserError
from lumalock.core.memory_manager import release_memory

MODEL_CONFIG = yaml.safe_load(resource_path("config/models.yaml").read_text(encoding="utf-8"))
MODEL_SPECS = MODEL_CONFIG["models"]


class ModelManager:
    def __init__(self, hardware):
        self.hardware = hardware
        os.environ.setdefault("HF_HOME", str(model_dir() / ".hub"))
        os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
        os.environ.setdefault("HF_XET_RECONSTRUCTION_DOWNLOAD_BUFFER_SIZE", "128mb")
        os.environ.setdefault("HF_XET_RECONSTRUCTION_DOWNLOAD_BUFFER_PERFILE_SIZE", "32mb")
        os.environ.setdefault("HF_XET_RECONSTRUCTION_DOWNLOAD_BUFFER_LIMIT", "256mb")
        self.settings = load_settings()
        self.lock = threading.RLock()

    def location(self, key):
        if key not in MODEL_SPECS:
            raise UserError("Only the configured FLUX image engine is supported.")
        return model_dir() / key

    def expected_files(self, key):
        spec = MODEL_SPECS[key]
        primary = dict(spec, destination="diffusion_models" if key == "flux" else "")
        return {
            str(Path(item["destination"]) / Path(item["file"]).name): item
            for item in [primary, *spec.get("support", [])]
        }

    def manifest(self, key):
        directory = self.location(key)
        try:
            manifest = json.loads((directory / "installation.json").read_text(encoding="utf-8"))
            spec = MODEL_SPECS[key]
            if manifest["id"] != spec["id"] or manifest["revision"] != spec["revision"]:
                raise ValueError("Wrong model revision")
            expected = self.expected_files(key)
            if set(manifest["files"]) != set(expected):
                raise ValueError("Missing required components")
            for name, record in manifest["files"].items():
                path = (directory / name).resolve()
                item = expected[name]
                if not path.is_relative_to(directory.resolve()):
                    raise ValueError("Invalid file path")
                if (
                    not isinstance(record, dict)
                    or record.get("repo") != item["id"]
                    or record.get("revision") != item["revision"]
                    or not isinstance(record.get("size"), int)
                    or record["size"] <= 0
                    or len(record.get("sha256", "")) != 64
                    or not path.is_file()
                    or path.stat().st_size != record["size"]
                ):
                    raise ValueError("Incomplete model files")
            return manifest
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
            raise UserError(
                "Model files are missing or incomplete. Download / Repair to continue."
            ) from exc

    def installed(self, key):
        if key not in MODEL_SPECS:
            return False
        try:
            self.manifest(key)
            return True
        except UserError:
            return False

    def component_status(self, key):
        result = []
        for name in self.expected_files(key):
            label = (
                "Transformer"
                if name.startswith("diffusion_models")
                else "Text encoder"
                if name.startswith("text_encoders")
                else "VAE"
            )
            path = self.location(key) / name
            result.append({"name": label, "present": path.is_file() and path.stat().st_size > 0})
        return result

    def available(self, key):
        if not self.installed(key):
            return False
        from lumalock.comfy.manager import runtime_root

        root = runtime_root()
        return (
            (root / "main.py").is_file()
            and (root / "custom_nodes/ComfyUI-GGUF/nodes.py").is_file()
            and all(
                importlib.util.find_spec(package) is not None
                for package in ("torch", "transformers", "gguf", "requests", "safetensors")
            )
        )

    @staticmethod
    def checksum(path, cancelled=lambda: False, report=lambda count: None):
        digest = hashlib.sha256()
        count = 0
        with path.open("rb") as stream:
            while chunk := stream.read(8 * 1024**2):
                if cancelled():
                    raise Cancelled("Paused. Download / Repair resumes completed files.")
                digest.update(chunk)
                count += len(chunk)
                report(count)
        return digest.hexdigest()

    def verify(self, key, cancelled=lambda: False, progress=lambda value, text: None):
        manifest = self.manifest(key)
        total = sum(record["size"] for record in manifest["files"].values())
        done = 0
        for name, record in manifest["files"].items():
            path = self.location(key) / name
            checksum = self.checksum(
                path,
                cancelled,
                lambda count: progress(
                    int(100 * (done + count) / total), f"Verifying {Path(name).name}"
                ),
            )
            if checksum != record["sha256"]:
                raise UserError(
                    "Model checksum verification failed. Download / Repair to continue."
                )
            done += record["size"]
        progress(100, "All required files verified")
        return manifest

    def download_plan(self):
        from huggingface_hub import HfApi

        api = HfApi()
        plan = []
        for key, spec in MODEL_SPECS.items():
            primary = dict(spec, destination="diffusion_models" if key == "flux" else "")
            for item in [primary, *spec.get("support", [])]:
                info = api.model_info(item["id"], revision=item["revision"], files_metadata=True)
                file = next((f for f in info.siblings if f.rfilename == item["file"]), None)
                if file is None or file.size is None:
                    raise UserError("A configured model file is missing from the pinned snapshot.")
                name = str(Path(item["destination"]) / Path(item["file"]).name)
                plan.append(
                    {
                        "key": key,
                        "repo": item["id"],
                        "revision": info.sha,
                        "file": item["file"],
                        "name": name,
                        "size": file.size,
                        "sha256": file.lfs.sha256 if file.lfs else None,
                    }
                )
        total = sum(item["size"] for item in plan)
        runtime_bytes = 0  # Python/runtime libraries are not AI model weights.
        if total + runtime_bytes > MODEL_CONFIG["limits"]["ai_storage_gib"] * 1024**3:
            raise UserError(
                f"Complete AI weights plus backend runtime exceed the 30 GiB budget: {(total + runtime_bytes) / 1024**3:.2f} GiB."
            )
        return plan

    def download(self, key, cancelled=lambda: False, progress=lambda value, text: None):
        if key not in MODEL_SPECS:
            raise UserError("Unsupported model.")
        if key == "flux" and not self.settings.flux_license_accepted:
            raise UserError("Acknowledge FLUX.2-dev's non-commercial license before downloading.")
        try:
            with self.lock:
                progress(-1, "Checking pinned model files and available disk space?")
                plan = self.download_plan()
                directory = self.location(key)
                directory.mkdir(parents=True, exist_ok=True)
                selected = [item for item in plan if item["key"] == key]
                remaining = sum(
                    item["size"] if not (directory / item["name"]).is_file() else 0
                    for item in selected
                )
                if shutil.disk_usage(directory).free < remaining + 1024**3:
                    raise UserError(
                        "Not enough disk space. Free space and retry Download / Repair."
                    )
                total = sum(item["size"] for item in selected)
                done = 0
                records = {}
                for index, item in enumerate(selected):
                    if cancelled():
                        raise Cancelled("Paused. Download / Repair resumes partial files.")
                    if not item["sha256"]:
                        raise UserError(
                            "Upstream checksum is unavailable; installation was stopped."
                        )
                    target = directory / item["name"]
                    target.parent.mkdir(parents=True, exist_ok=True)
                    valid = False
                    if target.is_file() and target.stat().st_size == item["size"]:
                        progress(int(100 * done / total), f"Checking existing {target.name}?")
                        valid = self.checksum(target, cancelled) == item["sha256"]
                    if not valid:
                        from lumalock.core.model_transfer import receive_file

                        receive_file(
                            item,
                            target,
                            cancelled,
                            lambda count, detail: progress(
                                min(99, int(100 * (done + count) / total)),
                                f"File {index + 1}/{len(selected)} ? {detail}",
                            ),
                        )
                        progress(
                            int(100 * (done + item["size"]) / total), f"Verifying {target.name}?"
                        )
                        partial = target.with_name(target.name + ".part")
                        checksum = self.checksum(partial, cancelled)
                        if partial.stat().st_size != item["size"] or checksum != item["sha256"]:
                            # Discard invalid bytes so retry cannot repeatedly reuse a corrupt prefix.
                            with partial.open("wb"):
                                pass
                            raise UserError(
                                "Downloaded file failed checksum verification. Retry Download / Repair."
                            )
                        partial.replace(target)
                    records[item["name"]] = {
                        "size": item["size"],
                        "sha256": item["sha256"],
                        "repo": item["repo"],
                        "revision": item["revision"],
                    }
                    done += item["size"]
                    progress(min(99, int(100 * done / total)), f"Verified {target.name}")
                manifest = directory / "installation.json"
                temporary = manifest.with_suffix(".tmp")
                temporary.write_text(
                    json.dumps(
                        {
                            "id": MODEL_SPECS[key]["id"],
                            "revision": MODEL_SPECS[key]["revision"],
                            "files": records,
                        }
                    ),
                    encoding="utf-8",
                )
                temporary.replace(manifest)
                progress(100, "Ready ? all required model files downloaded and verified")
        except (UserError, Cancelled):
            raise
        except Exception as exc:
            logging.getLogger("lumalock.models").exception("Download failed")
            raise UserError(
                "Download interrupted. Check connection or repository access, then retry; partial files are retained."
            ) from exc

    def remove(self, key):
        with self.lock:
            self.release_all()
            target = self.location(key).resolve()
            if target.parent != model_dir().resolve():
                raise UserError("Invalid removal path")
            if target.exists():
                shutil.rmtree(target)

    def release_all(self):
        release_memory()

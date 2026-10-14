"""Portable .luma ZIP projects, validated before replacing active state."""

import hashlib
import json
import uuid
import zipfile
from pathlib import Path

from lumalock import __version__
from lumalock.core.config import data_dir, model_dir
from lumalock.core.exceptions import UserError
from lumalock.project.edit_state import EditState
from lumalock.project.history import History, HistoryEntry


def source_fingerprint(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def save_project(path: Path, source: Path, history: History, prompts: list[str]) -> None:
    if path.resolve() == source.resolve():
        raise UserError("A project cannot overwrite its source photograph.")
    payload = {
        "version": 1,
        "app_version": __version__,
        "source": str(source.resolve()),
        "fingerprint": source_fingerprint(source),
        "history": [entry.model_dump() for entry in history.entries],
        "index": history.index,
        "prompts": prompts,
        "versions": {name: state.model_dump() for name, state in history.versions.items()},
        "model_metadata": [],
    }
    for marker in model_dir().glob("*/installation.json"):
        from lumalock.core.model_manager import MODEL_SPECS

        if marker.parent.name not in MODEL_SPECS:
            continue
        metadata = json.loads(marker.read_text(encoding="utf-8"))
        payload["model_metadata"].append({"id": metadata["id"], "revision": metadata["revision"]})
    temporary = path.with_suffix(".tmp")
    assets = {}
    states = [entry["state"] for entry in payload["history"]] + list(payload["versions"].values())
    for state in states:
        holders = [(layer, "mask_file") for layer in state["masks"]] + [(state, "generated_file")]
        for holder, key in holders:
            if holder[key]:
                file = Path(holder[key])
                if not file.is_file():
                    raise UserError("A project asset is missing; restore an earlier history state.")
                asset = assets.setdefault(str(file), f"assets/{len(assets)}{file.suffix}")
                holder[key] = asset
    try:
        with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as archive:
            for file, name in assets.items():
                archive.write(file, name)
            archive.writestr("project.json", json.dumps(payload, allow_nan=False))
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def load_project(path: Path) -> tuple[Path, History, list[str]]:
    try:
        with zipfile.ZipFile(path) as archive:
            info = archive.getinfo("project.json")
            if info.file_size > 20_000_000:
                raise ValueError("Project metadata too large")
            payload = json.loads(archive.read(info))
            if payload["version"] != 1:
                raise ValueError("Unsupported project version")
            source = Path(payload["source"])
            if not source.is_file():
                raise UserError("The original image is missing. Restore it to its saved path.")
            if source_fingerprint(source) != payload["fingerprint"]:
                raise UserError("The original image has changed since the project was saved.")
            entries = [HistoryEntry.model_validate(entry) for entry in payload["history"]]
            versions = {
                name: EditState.model_validate(state)
                for name, state in payload.get("versions", {}).items()
            }
            if not entries or not 0 <= payload["index"] < len(entries):
                raise ValueError("Invalid history")
            directory = data_dir() / "projects" / uuid.uuid4().hex
            directory.mkdir(parents=True)
            assets = {}
            for state in [entry.state for entry in entries] + list(versions.values()):
                holders = [(layer, "mask_file") for layer in state.masks] + [
                    (state, "generated_file")
                ]
                for holder, key in holders:
                    name = getattr(holder, key)
                    if name:
                        if not name.startswith("assets/") or ".." in name or "\\" in name:
                            raise ValueError("Invalid project asset path")
                        if name not in assets:
                            info = archive.getinfo(name)
                            if info.file_size > 250_000_000:
                                raise ValueError("Asset too large")
                            target = directory / Path(name).name
                            target.write_bytes(archive.read(info))
                            assets[name] = str(target)
                        setattr(holder, key, assets[name])
            history = History()
            history.entries, history.index = entries, payload["index"]
            history.versions = versions
            return source, history, [str(p) for p in payload["prompts"]]
    except UserError:
        raise
    except Exception as exc:
        raise UserError("This project is invalid or uses an unsupported format.") from exc

"""Create a clean shareable ZIP from the verified portable app folder."""

import argparse
import hashlib
import json
import zipfile
from pathlib import Path


def release_files(root):
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if (
            "__pycache__" in relative.parts
            or ".git" in relative.parts
            or path.suffix in (".pyc", ".pyo")
        ):
            continue
        if relative.parts[0] in ("models", "data", "outputs", "projects"):
            if relative != Path("data/settings.yaml"):
                continue
        yield path, relative


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--folder", type=Path, default=Path("dist/LumaLockAI"))
    parser.add_argument("--zip", type=Path, default=Path("dist/LumaLockAI-Windows-x64.zip"))
    args = parser.parse_args()
    root = args.folder.resolve()
    if (
        not (root / "LumaLockAI.exe").is_file()
        or not (root / "runtime/python/python311._pth").is_file()
    ):
        raise SystemExit("Build and validate the portable EXE/runtime first.")
    files = list(release_files(root))
    if any(path.suffix in (".gguf", ".safetensors") for path, _ in files):
        raise SystemExit("Model weights were found in the release; packaging stopped.")
    temporary = args.zip.with_suffix(".zip.partial")
    args.zip.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(
        temporary, "w", zipfile.ZIP_DEFLATED, compresslevel=1, allowZip64=True
    ) as archive:
        for index, (path, relative) in enumerate(files):
            archive.write(path, Path("LumaLockAI") / relative)
            if index % 3000 == 0:
                print(f"Archived {index + 1}/{len(files)} files", flush=True)
    with zipfile.ZipFile(temporary) as archive:
        damaged = archive.testzip()
        if damaged:
            raise SystemExit(f"Archive integrity failed for {damaged}")
    temporary.replace(args.zip)
    with args.zip.open("rb") as stream:
        checksum = hashlib.file_digest(stream, "sha256").hexdigest()
    report = {
        "archive": args.zip.name,
        "bytes": args.zip.stat().st_size,
        "sha256": checksum,
        "files": len(files),
        "uncompressed_bytes": sum(path.stat().st_size for path, _ in files),
        "models_included": False,
        "private_data_included": False,
        "integrity_passed": True,
    }
    args.zip.with_suffix(".json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    args.zip.with_suffix(".sha256").write_text(f"{checksum}  {args.zip.name}\n", encoding="ascii")
    print(json.dumps(report, indent=2), flush=True)


if __name__ == "__main__":
    main()

"""Build the complete portable Windows app, local backend, Python runtime; models download at first startup."""

import argparse
import importlib.metadata
import os
import shutil
import subprocess
import sys
from pathlib import Path


def main():
    if sys.prefix == sys.base_prefix:
        raise SystemExit("Run build.py using .venv's Python interpreter.")
    root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--reuse-runtime",
        action="store_true",
        help="Keep an already validated bundled backend while rebuilding the EXE",
    )
    args = parser.parse_args()
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--windowed",
        "--onedir",
        "--name",
        "LumaLockAI",
        "--paths",
        str(root / "src"),
        "--collect-submodules",
        "lumalock",
        "--collect-data",
        "cv2",
        "--add-data",
        str(root / "config") + ";config",
        "--exclude-module",
        "PySide6.QtWebEngineCore",
        "--exclude-module",
        "PySide6.QtWebEngineWidgets",
        str(root / "launch.py"),
    ]
    command[3:3] = [
        argument
        for name in ("torch", "torchvision", "diffusers", "timm")
        for argument in ("--exclude-module", name)
    ]
    for name in ("llama_cpp", "huggingface_hub"):
        if not importlib.util.find_spec(name):
            raise SystemExit(f"Missing {name}; install project-local AI dependencies first")
        command[3:3] = ["--collect-all", name]
    saved_runtime = root / "build" / "validated-runtime"
    runtime_source = root / "dist" / "LumaLockAI" / "runtime"
    preserved = []
    for name in ("models", "data"):
        source = root / "dist" / "LumaLockAI" / name
        staging = root / "build" / ("preserved-" + name)
        if source.is_dir():
            if staging.exists():
                raise SystemExit(f"Existing build staging needs recovery: {staging}")
            staging.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(source), str(staging))
            preserved.append((staging, source))
    if args.reuse_runtime:
        for path in (saved_runtime, runtime_source):
            if not path.resolve().is_relative_to(root.resolve()):
                raise ValueError("Invalid runtime staging path")
        if saved_runtime.exists() or not runtime_source.is_dir():
            raise SystemExit("Runtime staging is unavailable; use a normal build")
        saved_runtime.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(runtime_source), str(saved_runtime))
    try:
        subprocess.run(command, cwd=root, check=True)
    finally:
        for staging, source in preserved:
            source.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(staging), str(source))
        if args.reuse_runtime and saved_runtime.exists():
            runtime_source.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(saved_runtime), str(runtime_source))
    destination = root / "dist" / "LumaLockAI"
    shutil.copy2(root / "LICENSE", destination / "LICENSE.txt")
    shutil.copy2(root / "docs" / "licensing.md", destination / "THIRD_PARTY_NOTICES.md")
    for distribution in importlib.metadata.distributions():
        name = distribution.metadata.get("Name", "unknown")
        for entry in distribution.files or []:
            if "license" in str(entry).lower() or "copying" in str(entry).lower():
                source = distribution.locate_file(entry)
                if source.is_file():
                    safe_parts = [part for part in entry.parts if part not in (".", "..")]
                    target = destination / "third_party_licenses" / name / Path(*safe_parts)
                    if not target.resolve().is_relative_to(destination.resolve()):
                        raise ValueError("Invalid third-party license destination")
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, target)
    runtime_target = destination / "runtime"
    runtime_target.mkdir(exist_ok=True)
    if args.reuse_runtime:
        pass  # Restored in the finally block above, including after a failed build.
    else:
        backend_source = root / "runtime" / "comfyui"

        def ignore_backend(directory, names):
            skipped = {
                name for name in names if name in (".git", "__pycache__") or name.endswith(".pyc")
            }
            if Path(directory).resolve() == backend_source.resolve():
                skipped.update(
                    set(names) & {"tests-unit", "tests", "input", "output", "models", "web"}
                )
            return skipped

        shutil.copytree(
            backend_source, runtime_target / "comfyui", dirs_exist_ok=True, ignore=ignore_backend
        )
        python_target = runtime_target / "python"
        shutil.copytree(
            Path(sys.base_prefix),
            python_target,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "site-packages"),
        )
        packages = python_target / "Lib" / "site-packages"
        packages.mkdir(parents=True, exist_ok=True)
        shutil.copytree(
            Path(sys.prefix) / "Lib" / "site-packages",
            packages,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns(
                "__pycache__",
                "*.pyc",
                "PySide6",
                "shiboken6",
                "PyInstaller",
                "_pyinstaller_hooks_contrib",
                "pytest",
                "_pytest",
                "ruff",
                "diffusers",
                "timm",
                "__editable__*",
            ),
        )
        # A backend process must not resolve Python packages from the developer's environment.
        (python_target / "python311._pth").write_text(
            ".\nLib\nDLLs\nLib/site-packages\n../comfyui\nimport site\n", encoding="utf-8"
        )
    settings_dir = destination / "data"
    settings_dir.mkdir(exist_ok=True)
    import yaml

    from lumalock.core.config import Settings

    settings = Settings(flux_license_accepted=False, first_run_done=False)
    if not (settings_dir / "settings.yaml").exists():
        (settings_dir / "settings.yaml").write_text(
            yaml.safe_dump(settings.model_dump()), encoding="utf-8"
        )
    (destination / "START_HERE.txt").write_text(
        "Open LumaLockAI.exe. Keep this entire folder together.\nInference is local. FLUX.2-dev uses the Non-Commercial License.\n",
        encoding="utf-8",
    )
    for name in (
        "vcruntime140.dll",
        "vcruntime140_1.dll",
        "msvcp140.dll",
        "msvcp140_1.dll",
        "msvcp140_2.dll",
        "concrt140.dll",
    ):
        python_target = runtime_target / "python"
        source = Path(os.environ.get("WINDIR", "C:/Windows")) / "System32" / name
        if source.is_file():
            shutil.copy2(source, python_target / name)
    print("Built complete dist/LumaLockAI distribution; run LumaLockAI.exe.")


if __name__ == "__main__":
    main()

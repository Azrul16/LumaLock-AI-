"""Install only Qwen Q4_K_M and FLUX.2-dev Q2_K with complete storage preflight."""

import argparse

from lumalock.core.config import save_settings
from lumalock.core.exceptions import UserError
from lumalock.core.hardware import detect_hardware
from lumalock.core.model_manager import ModelManager


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--model", choices=["prompt", "flux"])
    parser.add_argument("--list", action="store_true")
    parser.add_argument(
        "--accept-flux-license",
        action="store_true",
        help="Acknowledge the FLUX.2-dev Non-Commercial License",
    )
    args = parser.parse_args()
    models = ModelManager(detect_hardware())
    if args.accept_flux_license:
        models.settings.flux_license_accepted = True
        save_settings(models.settings)
    plan = models.download_plan()
    print("LumaLock complete AI storage plan", flush=True)
    for item in plan:
        print(f"{item['file']}: {item['size'] / 1024**3:.3f} GiB", flush=True)
    print(f"Total: {sum(item['size'] for item in plan) / 1024**3:.3f} GiB / 30 GiB", flush=True)
    if args.list or not (args.all or args.model):
        return
    for key in ["prompt", "flux"] if args.all else [args.model]:
        if models.installed(key):
            models.verify(key)
            print(f"{key}: installed and verified", flush=True)
        else:
            models.download(
                key, progress=lambda value, message: print(f"{value}% {message}", flush=True)
            )


if __name__ == "__main__":
    try:
        main()
    except (UserError, KeyboardInterrupt) as exc:
        raise SystemExit(str(exc))

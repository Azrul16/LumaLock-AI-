"""Download or verify the FLUX engine and its required conditioning/VAE components."""

import argparse

from lumalock.core.config import save_settings
from lumalock.core.hardware import detect_hardware
from lumalock.core.model_manager import ModelManager


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--accept-flux-license", action="store_true")
    args = parser.parse_args()
    models = ModelManager(detect_hardware())
    if args.accept_flux_license:
        models.settings.flux_license_accepted = True
        save_settings(models.settings)
    if args.list:
        for item in models.download_plan():
            print(f"{item['file']}: {item['size'] / 1024**3:.3f} GiB")
        return

    def report(value, message):
        print(f"{value}% {message}", flush=True)

    if args.verify:
        models.verify("flux", progress=report)
    else:
        models.download("flux", progress=report)


if __name__ == "__main__":
    main()

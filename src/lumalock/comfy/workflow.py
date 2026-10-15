"""FLUX.2 reference editing using native ComfyUI nodes and only one image model."""

from lumalock.core.model_manager import MODEL_SPECS


def build_workflow(image_name, prompt, width, height, steps, strength, seed, low_memory=False):
    flux = MODEL_SPECS["flux"]
    encoder = flux["support"][0]["file"]
    workflow = {
        "1": {
            "class_type": "UnetLoaderGGUFAdvanced",
            "inputs": {
                "unet_name": flux["file"],
                "dequant_dtype": "target",
                "patch_dtype": "target",
                "patch_on_device": False,
            },
        },
        "2": {"class_type": "CLIPLoaderGGUF", "inputs": {"clip_name": encoder, "type": "flux2"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": "flux2-vae.safetensors"}},
        "4": {"class_type": "LoadImage", "inputs": {"image": image_name}},
        "5": {"class_type": "VAEEncode", "inputs": {"pixels": ["4", 0], "vae": ["3", 0]}},
        "6": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["2", 0]}},
        "7": {
            "class_type": "ReferenceLatent",
            "inputs": {"conditioning": ["6", 0], "latent": ["5", 0]},
        },
        "8": {"class_type": "FluxGuidance", "inputs": {"conditioning": ["7", 0], "guidance": 4.0}},
        "9": {"class_type": "BasicGuider", "inputs": {"model": ["1", 0], "conditioning": ["8", 0]}},
        "10": {"class_type": "RandomNoise", "inputs": {"noise_seed": seed}},
        "11": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "euler"}},
        "12": {
            "class_type": "Flux2Scheduler",
            "inputs": {"steps": steps, "width": width, "height": height},
        },
        "13": {
            "class_type": "SplitSigmas",
            "inputs": {"sigmas": ["12", 0], "step": int(steps * (1 - strength))},
        },
        "14": {
            "class_type": "SamplerCustomAdvanced",
            "inputs": {
                "noise": ["10", 0],
                "guider": ["9", 0],
                "sampler": ["11", 0],
                "sigmas": ["13", 1],
                "latent_image": ["5", 0],
            },
        },
        "15": {"class_type": "VAEDecode", "inputs": {"samples": ["14", 0], "vae": ["3", 0]}},
        "16": {
            "class_type": "SaveImage",
            "inputs": {"images": ["15", 0], "filename_prefix": "LumaLock"},
        },
    }
    if low_memory:
        # Bound VAE activation memory instead of decoding the entire frame at once.
        # These are native nodes in the pinned runtime; model weights/steps stay unchanged.
        for key, kind in (("5", "VAEEncodeTiled"), ("15", "VAEDecodeTiled")):
            workflow[key]["class_type"] = kind
            workflow[key]["inputs"].update(
                tile_size=512, overlap=64, temporal_size=64, temporal_overlap=8
            )
    return workflow

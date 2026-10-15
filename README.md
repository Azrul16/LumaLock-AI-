# LumaLock AI

A local browser photo editor powered by one image engine: FLUX.2-dev Q2_K.

Open **Launch LumaLock AI.cmd**. It opens the browser and runs the Python server in the
foreground. Keep its terminal open; closing it stops the server and its owned AI workers.
The application uses only this project's Python 3.11 `.venv`.

Attach a photo, choose Natural or Creative, optionally choose a photographic preset, and
describe your edit. Ordinary Python templates append editing requirements without translating
or rewriting your language. There is no separate prompt model or model-loading stage.
Save the returned PNG, choose Edit image to branch, or delete chats from the sidebar.

Preserve people restores original protected pixels. Protect area adds brush, ellipse,
rectangle and eraser tools; manual regions override automatic classical face selection.
Review protection coverage. No recognition score or extra neural mask model is used.

Quality is now the default: 1024px generation with a 40-step base schedule. Maximum uses
1536px / 50 base steps; Draft is explicitly 512px / 12 base steps. Actual sampling depends
on edit strength. Memory recovery retries at the same resolution with stronger offloading.
There is **no execution time cutoff**; Stop remains available.

**Save 4K image** exports a PNG with at least 3840px on its longest edge, keeping aspect
ratio and retaining larger source sizes. Square photos become 3840?3840. Working images
remain at original dimensions to preserve masks and edit branches. Current 4K enlargement
uses Lanczos; it is not native 4K generation or neural detail recovery. Smaller generated
images cannot regain genuine detail merely by enlarging them.

For conservative full-resolution correction, use Natural mode, no preset (or Professional
Enhance), and the exact prompt `auto enhance`, `professional enhance`, or `enhance this photo`.
This applies measured photo adjustments without diffusion or denoising. Other prompts use
FLUX. Protection still restores original pixels. Read [the quality review](docs/quality-research.md)
for observed degradation, the recommended architecture, candidate models and limitations.

`models/flux/` contains the transformer, required text-conditioning encoder and VAE, about
20.57 GiB. These are one image pipeline. Models & settings downloads/repairs/verifies only
that bundle. FLUX requires non-commercial license acknowledgement. Python libraries are
not counted as model storage. Chats, originals' managed copies, settings and logs are in data/.

Use only `.venv/Scripts/python.exe -m pip` for installations, never global pip or --user.
Run `.venv/Scripts/python.exe -m pytest -q` for tests, `download_models.py --verify` for
integrity, and `validate_models.py --image "my photo.jpg"` for real acceptance validation.
All commands must use `.venv/Scripts/python.exe`.

Legacy dist/build files and obsolete model weights may remain because automatic approval
review blocked deletion; they are unused. No EXE or ZIP build workflow is active.

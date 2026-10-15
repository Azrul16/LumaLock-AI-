"""Serialized background AI jobs and authoritative conversation state."""

import logging
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from lumalock.ai.prompt.presets import PRESETS
from lumalock.ai.prompt.prompt_builder import build_flux_prompt
from lumalock.core.config import load_settings, save_settings
from lumalock.core.exceptions import Cancelled, UserError
from lumalock.core.hardware import detect_hardware
from lumalock.core.model_manager import MODEL_SPECS, ModelManager
from lumalock.imaging.protection import ProtectionShape
from lumalock.pipeline.chat_edit import edit_chat_image
from lumalock.pipeline.photo_correction import is_photo_correction
from lumalock.project.chat import ChatStore, ChatTurn, Conversation
from lumalock.webapp.progress import JobTiming


class Busy(UserError):
    pass


class ImageService:
    def __init__(self, models=None, store=None, editor=None):
        self.hardware = detect_hardware()
        self.models = models or ModelManager(self.hardware)
        self.settings = load_settings()
        self.models.settings = self.settings
        self.store = store or ChatStore()
        self.editor = editor or edit_chat_image
        self.lock = threading.RLock()
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="lumalock-ai")
        # Recent() is newest-first; insertion order must remain oldest-first for selection/sidebar.
        self.chats = {chat.id: chat for chat in reversed(self.store.recent())}
        if not self.chats:
            self.new_chat()
        self.job = None
        self.cancelled = threading.Event()

    def require_idle(self):
        if self.job and self.job["status"] in ("running", "stopping"):
            raise Busy("An operation is already running. Wait for it to finish or press Stop.")

    def get_chat(self, identifier):
        if identifier not in self.chats:
            raise UserError("This chat was not found. Start a new chat.")
        return self.chats[identifier]

    def new_chat(self):
        with self.lock:
            if hasattr(self, "job"):
                self.require_idle()
            chat = Conversation()
            self.store.save(chat)
            self.chats[chat.id] = chat
            return chat.model_dump()

    def state(self, identifier=None):
        with self.lock:
            chat = self.get_chat(identifier) if identifier else next(reversed(self.chats.values()))
            return {
                "chat": chat.model_dump(),
                "chats": [{"id": c.id, "title": c.title} for c in reversed(self.chats.values())],
                "job": (
                    {
                        **self.job,
                        **self.timing.snapshot(self.job["status"] == "running"),
                    }
                    if self.job
                    else None
                ),
                "models": [
                    {
                        "key": key,
                        "name": spec["name"],
                        "complete": self.models.installed(key),
                        "available": self.models.available(key),
                        "gib": spec["size_gb"],
                        "components": getattr(self.models, "component_status", lambda _: [])(key),
                    }
                    for key, spec in MODEL_SPECS.items()
                ],
                "settings": {
                    "quality": self.settings.quality_mode,
                    "device": self.settings.device,
                    "license_accepted": self.settings.flux_license_accepted,
                },
                "presets": list(PRESETS),
                "hardware": self.hardware.to_dict(),
            }

    def delete_chat(self, identifier):
        with self.lock:
            self.require_idle()
            chat = self.get_chat(identifier)
            replacement = None
            if len(self.chats) == 1:
                replacement = Conversation()
                self.store.save(replacement)
            removed = self.store.delete(chat)
            del self.chats[identifier]
            if replacement:
                self.chats[replacement.id] = replacement
            if self.job and self.job.get("chat_id") == identifier:
                self.job = None
            return {
                "deleted": identifier,
                "next_chat_id": next(reversed(self.chats)),
                "removed_assets": removed,
            }

    def attach(self, identifier, temporary, filename):
        with self.lock:
            self.require_idle()
            chat = self.get_chat(identifier)
            name = self.store.remember_image(temporary)
            chat.selected_image = chat.selected_root = name
            chat.protection = []
            if not chat.turns:
                chat.title = Path(filename).stem[:48] or "Photo edit"
            self.store.save(chat)
            return chat.model_dump()

    def select(self, identifier, image):
        with self.lock:
            self.require_idle()
            chat = self.get_chat(identifier)
            if image is None:
                chat.selected_image = chat.selected_root = None
            else:
                allowed = {turn.result: turn.root for turn in chat.turns if turn.result}
                allowed.update({turn.source: turn.root for turn in chat.turns})
                if chat.selected_image:
                    allowed[chat.selected_image] = chat.selected_root
                if image not in allowed or not self.store.asset(image).is_file():
                    raise UserError("That image is unavailable in this chat. Attach it again.")
                if chat.selected_root != allowed[image]:
                    chat.protection = []
                chat.selected_image, chat.selected_root = image, allowed[image]
            self.store.save(chat)
            return chat.model_dump()

    def progress(self, value, message):
        with self.lock:
            if self.job and self.job["status"] == "running":
                self.timing.update(value)
                self.job.update(progress=value, message=message)

    def set_protection(self, identifier, shapes):
        with self.lock:
            self.require_idle()
            if not isinstance(shapes, list) or len(shapes) > 256:
                raise UserError("Use at most 256 protection strokes.")
            chat = self.get_chat(identifier)
            if not chat.selected_root:
                raise UserError("Attach a photo before adding protection.")
            chat.protection = [ProtectionShape.model_validate(shape) for shape in shapes]
            self.store.save(chat)
            return chat.model_dump()

    def start_edit(
        self,
        identifier,
        prompt,
        preserve=True,
        quality="Quality",
        device="auto",
        mode="Natural",
        preset=None,
    ):
        with self.lock:
            self.require_idle()
            if not isinstance(prompt, str):
                raise UserError("Enter your edit as a text prompt.")
            prompt = prompt.strip()
            if not prompt or len(prompt) > 12000:
                raise UserError("Enter a prompt between 1 and 12,000 characters.")
            build_flux_prompt(prompt, mode, preserve, preset=preset)
            if quality not in ("Preview", "Quality", "Maximum") or device not in (
                "auto",
                "cpu",
                "cuda",
            ):
                raise UserError("Choose a valid quality and processing device.")
            missing = [key for key in MODEL_SPECS if not self.models.installed(key)]
            if missing:
                raise UserError(
                    "AI models need setup or repair. Open Models & settings, then retry."
                )
            if any(not self.models.available(key) for key in MODEL_SPECS):
                raise UserError(
                    "The local AI runtime is missing. Keep the entire app folder together, or repair the application installation."
                )
            chat = self.get_chat(identifier)
            if not chat.selected_image or not chat.selected_root:
                raise UserError("Attach a photo before sending a prompt.")
            for name in (chat.selected_image, chat.selected_root):
                if not self.store.asset(name).is_file():
                    raise UserError("The selected photo is missing. Attach it again.")
            turn = ChatTurn(
                prompt=prompt,
                source=chat.selected_image,
                root=chat.selected_root,
                preserve_people=preserve,
                mode=mode,
                preset=preset,
                quality=quality,
                method="photo_correction" if is_photo_correction(prompt, mode, preset) else "flux",
                protection=chat.protection,
            )
            chat.turns.append(turn)
            chat.title = prompt[:48]
            self.store.save(chat)
            self.settings.quality_mode, self.settings.device = quality, device
            save_settings(self.settings)
            self.models.settings = self.settings
            self._begin("edit", identifier, turn.id)
            self.executor.submit(self._edit, chat, turn)
            return dict(self.job)

    def _begin(self, kind, chat_id=None, turn_id=None):
        self.cancelled.clear()
        self.timing = JobTiming()
        self.job = {
            "id": uuid.uuid4().hex,
            "kind": kind,
            "chat_id": chat_id,
            "turn_id": turn_id,
            "status": "running",
            "progress": -1,
            "message": "Preparing…",
            "limit_seconds": None,
        }

    def _edit(self, chat, turn):
        try:
            path = self.editor(
                self.store.asset(turn.root),
                self.store.asset(turn.source),
                turn.prompt,
                self.models,
                turn.preserve_people,
                self.cancelled.is_set,
                self.progress,
                mode=turn.mode,
                preset=turn.preset,
                protection=turn.protection,
            )
            if self.cancelled.is_set():
                raise Cancelled("Edit stopped. Your earlier images are unchanged.")
            name = self.store.remember_image(path)
            with self.lock:
                if self.cancelled.is_set():
                    raise Cancelled(
                        "Edit stopped before publishing. Your earlier images are unchanged."
                    )
                turn.result, turn.status = name, "complete"
                chat.selected_image, chat.selected_root = name, turn.root
                self.store.save(chat)
                self.job.update(status="complete", progress=100, message="Your image is ready.")
                self.timing.finish()
        except Exception as exc:
            self._failed(exc, chat, turn)

    def _failed(self, exc, chat=None, turn=None):
        if self.cancelled.is_set() and not isinstance(exc, Cancelled):
            exc = Cancelled("Operation stopped. Your earlier images are unchanged.")
        expected = isinstance(exc, (UserError, Cancelled))
        if not expected:
            logging.getLogger("lumalock.web").exception("Background operation failed")
        message = (
            str(exc)
            if expected
            else "The operation could not finish. Check Models & settings and retry. Details are in the local log."
        )
        with self.lock:
            if turn:
                turn.status, turn.error = "failed", message
                try:
                    self.store.save(chat)
                except OSError:
                    message += " Chat could not be saved; check disk space."
            self.job.update(
                status="cancelled" if isinstance(exc, Cancelled) else "failed", message=message
            )
            self.timing.finish()

    def start_models(self, keys, accepted=False, verify=False):
        with self.lock:
            self.require_idle()
            if not keys or any(key not in MODEL_SPECS for key in keys):
                raise UserError("Select the FLUX image engine.")
            if (
                "flux" in keys
                and not verify
                and not (accepted or self.settings.flux_license_accepted)
            ):
                raise UserError("Review and acknowledge the FLUX non-commercial license first.")
            if accepted:
                self.settings.flux_license_accepted = True
                save_settings(self.settings)
                self.models.settings = self.settings
            self._begin("verify" if verify else "download")
            self.executor.submit(self._models, list(dict.fromkeys(keys)), verify)
            return dict(self.job)

    def _models(self, keys, verify):
        try:
            total = sum(MODEL_SPECS[key]["size_gb"] for key in keys)
            completed = 0
            for key in keys:
                size = MODEL_SPECS[key]["size_gb"]

                def progress(value, message):
                    weighted = (
                        -1
                        if value < 0
                        else min(99, int(100 * (completed + size * value / 100) / total))
                    )
                    self.progress(weighted, message)

                if verify:
                    self.models.verify(key, self.cancelled.is_set, progress)
                else:
                    self.models.download(key, self.cancelled.is_set, progress)
                completed += size
            self.progress(100, "Every selected model file passed verification.")
            with self.lock:
                self.job["status"] = "complete"
                self.timing.finish()
        except Exception as exc:
            self._failed(exc)

    def cancel(self):
        with self.lock:
            if self.job and self.job["status"] == "running":
                self.cancelled.set()
                self.job.update(status="stopping", message="Stopping safely…")

    def close(self):
        self.cancel()
        self.executor.shutdown(wait=True, cancel_futures=True)

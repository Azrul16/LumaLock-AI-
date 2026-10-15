"""Durable local conversations and immutable image references."""

import logging
import re
import uuid
from pathlib import Path
from typing import Literal

from PIL import Image
from pydantic import BaseModel, Field

from lumalock.core.config import data_dir
from lumalock.core.exceptions import UserError
from lumalock.export.exporter import export_image
from lumalock.imaging.image_io import load_image
from lumalock.imaging.protection import ProtectionShape


class ChatTurn(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    prompt: str
    source: str
    root: str
    preserve_people: bool = True
    mode: Literal["Natural", "Creative"] = "Natural"
    preset: str | None = None
    quality: Literal["Preview", "Quality", "Maximum"] | None = None
    method: Literal["flux", "photo_correction"] | None = None
    protection: list[ProtectionShape] = Field(default_factory=list, max_length=256)
    status: Literal["working", "complete", "failed"] = "working"
    result: str | None = None
    error: str | None = None


class Conversation(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    title: str = "New chat"
    originals: list[str] = Field(default_factory=list)
    turns: list[ChatTurn] = Field(default_factory=list)
    selected_image: str | None = None
    selected_root: str | None = None
    protection: list[ProtectionShape] = Field(default_factory=list, max_length=256)


class ChatStore:
    def __init__(self, directory=None):
        self.directory = Path(directory or data_dir() / "chats")
        self.directory.mkdir(parents=True, exist_ok=True)
        (self.directory / "assets").mkdir(exist_ok=True)

    def asset(self, name):
        path = (self.directory / name).resolve()
        if not path.is_relative_to((self.directory / "assets").resolve()):
            raise UserError("Invalid conversation image reference.")
        return path

    def remember_image(self, source):
        document = load_image(source)
        name = f"assets/{uuid.uuid4().hex}.png"
        Image.fromarray(document.pixels).save(self.asset(name), format="PNG")
        return name

    def save(self, conversation):
        if len(conversation.id) != 32 or any(c not in "0123456789abcdef" for c in conversation.id):
            raise UserError("Invalid conversation identifier.")
        path = self.directory / f"{conversation.id}.json"
        temporary = path.with_suffix(".tmp")
        temporary.write_text(conversation.model_dump_json(indent=2), encoding="utf-8")
        temporary.replace(path)

    @staticmethod
    def references(conversation):
        names = {conversation.selected_image, conversation.selected_root} - {None}
        for turn in conversation.turns:
            names.update({turn.source, turn.root, turn.result} - {None})
        return names

    def delete(self, conversation):
        identifier = conversation.id
        if not re.fullmatch(r"[a-f0-9]{32}", identifier):
            raise UserError("Invalid conversation identifier.")
        candidates = {self.asset(name) for name in self.references(conversation)}
        retained = set()
        can_reclaim = True
        for path in self.directory.glob("*.json"):
            if path.name == f"{identifier}.json":
                continue
            try:
                other = self.load(path)
                retained.update(self.asset(name) for name in self.references(other))
                retained.update(Path(name).resolve() for name in other.originals)
            except (OSError, ValueError, UserError):
                # An unreadable chat may still reference an image. Keep its files safe.
                can_reclaim = False
        retained.update(Path(name).resolve() for name in conversation.originals)
        (self.directory / f"{identifier}.json").unlink(missing_ok=True)
        removed = 0
        if can_reclaim:
            for path in candidates - retained:
                if not re.fullmatch(r"[a-f0-9]{32}\.png", path.name):
                    continue
                try:
                    if path.is_file():
                        path.unlink()
                        removed += 1
                except OSError:
                    logging.getLogger("lumalock.chat").warning(
                        "Unused chat asset could not be removed"
                    )
        return removed

    def load(self, path):
        conversation = Conversation.model_validate_json(Path(path).read_text(encoding="utf-8"))
        for turn in conversation.turns:
            if turn.status == "working":
                turn.status, turn.error = (
                    "failed",
                    "The previous edit was interrupted. Retry to continue.",
                )
            for name in (turn.source, turn.root, turn.result):
                if name:
                    self.asset(name)
        for name in (conversation.selected_image, conversation.selected_root):
            if name:
                self.asset(name)
        return conversation

    def recent(self):
        result = []
        for path in sorted(
            self.directory.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True
        ):
            try:
                result.append(self.load(path))
            except (OSError, ValueError, UserError):
                continue
        return result

    def export(self, conversation, name, destination):
        target = Path(destination).resolve()
        # Protect user uploads as well as managed originals and previous results.
        for original in conversation.originals:
            source = Path(original)
            if target == source.resolve() or (
                target.exists() and source.exists() and target.samefile(source)
            ):
                raise UserError("Choose a different filename to keep your original photo safe.")
        protected = {turn.source for turn in conversation.turns} | {
            turn.root for turn in conversation.turns
        }
        protected |= {turn.result for turn in conversation.turns if turn.result}
        protected |= {conversation.selected_image, conversation.selected_root} - {None}
        if any(target == self.asset(asset) for asset in protected):
            raise UserError(
                "Save outside the conversation assets to keep your edit history intact."
            )
        document = load_image(self.asset(name))
        export_image(document, document.pixels, target)

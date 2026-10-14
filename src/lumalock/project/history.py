"""Parameter snapshots with branching undo and redo."""

from pydantic import BaseModel

from lumalock.project.edit_state import EditState


class HistoryEntry(BaseModel):
    label: str
    state: EditState


class History:
    def __init__(self, state: EditState | None = None):
        self.entries = [HistoryEntry(label="Opened image", state=state or EditState())]
        self.index = 0
        self.versions: dict[str, EditState] = {}

    @property
    def state(self) -> EditState:
        return self.entries[self.index].state.model_copy(deep=True)

    def push(self, label: str, state: EditState) -> None:
        if state == self.entries[self.index].state:
            return
        self.entries = self.entries[: self.index + 1]
        self.entries.append(HistoryEntry(label=label, state=state.model_copy(deep=True)))
        self.index += 1

    def select(self, index: int) -> EditState:
        self.index = max(0, min(index, len(self.entries) - 1))
        return self.state

    def undo(self) -> EditState:
        return self.select(self.index - 1)

    def redo(self) -> EditState:
        return self.select(self.index + 1)

    def save_version(self, name: str, state: EditState) -> None:
        self.versions[name] = state.model_copy(deep=True)

    def restore_version(self, name: str) -> EditState:
        state = self.versions[name].model_copy(deep=True)
        self.push(f"Version: {name}", state)
        return state

    def clone(self):
        history = History()
        history.entries = [entry.model_copy(deep=True) for entry in self.entries]
        history.index = self.index
        history.versions = {
            name: state.model_copy(deep=True) for name, state in self.versions.items()
        }
        return history

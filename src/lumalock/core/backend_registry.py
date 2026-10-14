"""Lazy backend factories permit extensions without inference imports in the UI."""

from collections.abc import Callable
from importlib import import_module


class BackendRegistry:
    def __init__(self):
        self.factories: dict[str, Callable] = {}

    def register(self, name: str, factory: Callable) -> None:
        if name in self.factories:
            raise ValueError(f"Backend already registered: {name}")
        self.factories[name] = factory

    def create(self, name: str, **dependencies):
        if name not in self.factories:
            raise ValueError(f"Unknown backend: {name}")
        return self.factories[name](**dependencies)


def lazy_factory(module: str, class_name: str):
    def create(**dependencies):
        return getattr(import_module(module), class_name)(**dependencies)

    return create


GENERATIVE_BACKENDS = BackendRegistry()
GENERATIVE_BACKENDS.register(
    "flux", lazy_factory("lumalock.ai.generative.flux_backend", "FluxBackend")
)

"""In-process registry mapping model name -> backend instance.

The core (routers) talks only to this registry, never to a concrete backend."""

from __future__ import annotations

from .base import Voice, VoiceBackend


class Registry:
    def __init__(self) -> None:
        self._backends: dict[str, VoiceBackend] = {}
        self._default: str | None = None

    def register(self, backend: VoiceBackend, *, default: bool = False) -> None:
        self._backends[backend.name] = backend
        if default or self._default is None:
            self._default = backend.name

    def get(self, model: str | None) -> VoiceBackend | None:
        """Resolve a model name to a backend.

        Known name -> that backend. Unknown/OpenAI name (e.g. "tts-1") ->
        the default backend, so OpenAI SDK calls work unmodified."""
        if model and model in self._backends:
            return self._backends[model]
        if self._default is not None:
            return self._backends[self._default]
        return None

    def has(self, model: str) -> bool:
        return model in self._backends

    def models(self) -> list[str]:
        return list(self._backends)

    def all_voices(self) -> list[Voice]:
        return [v for backend in self._backends.values() for v in backend.list_voices()]


#: Process-wide singleton populated at app startup.
registry = Registry()

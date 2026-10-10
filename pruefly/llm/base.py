"""Provider-agnostic model layer.

Everything that talks to an LLM goes through :class:`ModelRouter`. Providers only
implement :meth:`ModelProvider.complete_json`. Swapping or re-ordering models is a
configuration change, never a code change.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Callable, Literal, Mapping, Protocol, Sequence, TypeVar

log = logging.getLogger("pruefly.llm")

Task = Literal["derender", "transform"]
T = TypeVar("T")


@dataclass(frozen=True)
class ImageInput:
    data: bytes
    media_type: str  # image/jpeg | image/png | image/webp | image/gif


class ProviderError(Exception):
    """A provider could not produce a usable answer (transport, refusal, truncation)."""


class AllProvidersFailed(Exception):
    def __init__(self, task: str, errors: list[tuple[str, str]]):
        self.task = task
        self.errors = errors
        detail = "; ".join(f"{name}: {msg}" for name, msg in errors) or "no provider configured"
        super().__init__(f"all providers failed for '{task}' ({detail})")


class ModelProvider(Protocol):
    name: str

    async def complete_json(
        self,
        *,
        system: str | None,
        prompt: str,
        image: ImageInput | None = None,
        max_output_tokens: int = 8192,
    ) -> str:
        """Return the raw text answer. Parsing and validation happen outside."""
        ...


@dataclass(frozen=True)
class RouterResult:
    value: object
    provider: str


class ModelRouter:
    """Tries providers in the configured order for each task.

    A provider counts as failed if the call raises OR if ``parse`` rejects the answer,
    so a second model can rescue a malformed answer from the first.
    """

    def __init__(self, providers: Mapping[str, ModelProvider], routes: Mapping[Task, Sequence[str]]):
        for task, order in routes.items():
            unknown = [n for n in order if n not in providers]
            if unknown:
                raise ValueError(f"route '{task}' references unknown provider(s): {unknown}")
        self._providers = dict(providers)
        self._routes = {k: tuple(v) for k, v in routes.items()}

    def route(self, task: Task) -> tuple[str, ...]:
        return self._routes.get(task, ())

    async def run(
        self,
        task: Task,
        *,
        prompt: str,
        parse: Callable[[str], T],
        system: str | None = None,
        image: ImageInput | None = None,
        max_output_tokens: int = 8192,
    ) -> tuple[T, str]:
        errors: list[tuple[str, str]] = []
        for name in self.route(task):
            provider = self._providers[name]
            started = time.monotonic()
            try:
                text = await provider.complete_json(
                    system=system, prompt=prompt, image=image, max_output_tokens=max_output_tokens
                )
                value = parse(text)
            except Exception as exc:  # noqa: BLE001 - any failure moves on to the next provider
                msg = f"{type(exc).__name__}: {exc}"[:300]
                errors.append((name, msg))
                log.warning("task=%s provider=%s failed (%.1fs): %s", task, name, time.monotonic() - started, msg)
                continue
            log.info("task=%s provider=%s ok (%.1fs)", task, name, time.monotonic() - started)
            return value, name
        raise AllProvidersFailed(task, errors)

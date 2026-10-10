"""Builds a ModelRouter from Settings. Providers are constructed lazily and only if routed."""
from __future__ import annotations

import logging

from ..config import Settings
from .base import ModelProvider, ModelRouter

log = logging.getLogger("pruefly.llm")


def _build(name: str, s: Settings) -> ModelProvider:
    if name == "anthropic":
        from .anthropic_provider import AnthropicProvider

        return AnthropicProvider(model=s.anthropic_model)
    if name == "gemini":
        from .gemini_provider import GeminiProvider

        return GeminiProvider(model=s.gemini_model, project=s.gemini_project, location=s.gemini_location)
    if name == "fake":
        from .fake import FakeProvider

        return FakeProvider()
    raise ValueError(f"unknown provider '{name}'")


def build_router(s: Settings) -> ModelRouter:
    wanted = list(dict.fromkeys([*s.derender_providers, *s.transform_providers]))
    providers: dict[str, ModelProvider] = {}
    for name in wanted:
        try:
            providers[name] = _build(name, s)
        except Exception as exc:  # noqa: BLE001 - a misconfigured fallback must not kill the app
            log.warning("provider '%s' unavailable: %s", name, exc)
    routes = {
        "derender": [n for n in s.derender_providers if n in providers],
        "transform": [n for n in s.transform_providers if n in providers],
    }
    return ModelRouter(providers, routes)

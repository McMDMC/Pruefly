"""Anthropic provider (Messages API, async)."""
from __future__ import annotations

import base64

from .base import ImageInput, ProviderError

CONTINUE = "Setze das JSON EXAKT an der Abbruchstelle fort. Keine Wiederholung, kein Markdown."
MAX_CONTINUATIONS = 2


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, model: str, api_key: str | None = None):
        from anthropic import AsyncAnthropic  # lazy: only needed when this provider is routed

        self._model = model
        # api_key=None -> SDK reads ANTHROPIC_API_KEY
        self._client = AsyncAnthropic(api_key=api_key, max_retries=2, timeout=120.0)

    async def complete_json(
        self,
        *,
        system: str | None,
        prompt: str,
        image: ImageInput | None = None,
        max_output_tokens: int = 8192,
    ) -> str:
        content: list[dict] = []
        if image is not None:
            content.append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": image.media_type,
                        "data": base64.standard_b64encode(image.data).decode("ascii"),
                    },
                }
            )
        content.append({"type": "text", "text": prompt})

        messages: list[dict] = [{"role": "user", "content": content}]
        collected = ""
        for _ in range(MAX_CONTINUATIONS + 1):
            kwargs: dict = {"model": self._model, "max_tokens": max_output_tokens, "messages": messages}
            if system:
                kwargs["system"] = system
            resp = await self._client.messages.create(**kwargs)
            if resp.stop_reason == "refusal":
                raise ProviderError("model refused the request")
            collected += "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
            if not collected.strip():
                raise ProviderError(f"empty answer (stop_reason={resp.stop_reason})")
            if resp.stop_reason != "max_tokens":
                return collected
            # Truncated: ask the model to continue exactly where it stopped.
            messages = [
                {"role": "user", "content": content},
                {"role": "assistant", "content": collected},
                {"role": "user", "content": CONTINUE},
            ]
        raise ProviderError("answer still truncated after continuations")

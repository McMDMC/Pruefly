"""Gemini provider (Vertex AI via google-genai, Application Default Credentials)."""
from __future__ import annotations

from .base import ImageInput, ProviderError


class GeminiProvider:
    name = "gemini"

    def __init__(self, model: str, project: str, location: str):
        from google import genai  # lazy import

        if not project:
            raise ProviderError("PRUEFLY_GEMINI_PROJECT (or GOOGLE_CLOUD_PROJECT) is not set")
        self._model = model
        self._client = genai.Client(vertexai=True, project=project, location=location)

    async def complete_json(
        self,
        *,
        system: str | None,
        prompt: str,
        image: ImageInput | None = None,
        max_output_tokens: int = 8192,
    ) -> str:
        from google.genai import types

        contents: list = []
        if image is not None:
            contents.append(types.Part.from_bytes(data=image.data, mime_type=image.media_type))
        contents.append(prompt)

        config = types.GenerateContentConfig(
            system_instruction=system,
            response_mime_type="application/json",
            max_output_tokens=max_output_tokens,
            temperature=0.2,
        )
        resp = await self._client.aio.models.generate_content(
            model=self._model, contents=contents, config=config
        )
        text = resp.text
        if not text or not text.strip():
            raise ProviderError("empty answer")
        return text

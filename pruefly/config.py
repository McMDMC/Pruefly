"""Runtime settings, read once from the environment."""
from __future__ import annotations

import os
from dataclasses import dataclass


def _csv(value: str) -> tuple[str, ...]:
    return tuple(p.strip().lower() for p in value.split(",") if p.strip())


@dataclass(frozen=True)
class Settings:
    env: str = "prod"
    access_code: str = ""
    derender_providers: tuple[str, ...] = ("anthropic", "gemini")
    transform_providers: tuple[str, ...] = ("anthropic", "gemini")
    anthropic_model: str = "claude-sonnet-5-5"
    gemini_model: str = "gemini-3.5-flash"
    gemini_project: str = ""
    gemini_location: str = "europe-west1"
    max_image_bytes: int = 8_000_000
    rate_limit_per_hour: int = 60

    @property
    def is_dev(self) -> bool:
        return self.env == "dev"

    @classmethod
    def from_env(cls, environ: dict[str, str] | None = None) -> "Settings":
        e = os.environ if environ is None else environ
        d = cls()
        return cls(
            env=e.get("PRUEFLY_ENV", d.env).strip().lower(),
            access_code=e.get("PRUEFLY_ACCESS_CODE", d.access_code),
            derender_providers=_csv(e.get("PRUEFLY_DERENDER_PROVIDERS", ",".join(d.derender_providers))),
            transform_providers=_csv(e.get("PRUEFLY_TRANSFORM_PROVIDERS", ",".join(d.transform_providers))),
            anthropic_model=e.get("PRUEFLY_ANTHROPIC_MODEL", d.anthropic_model),
            gemini_model=e.get("PRUEFLY_GEMINI_MODEL", d.gemini_model),
            gemini_project=e.get("PRUEFLY_GEMINI_PROJECT", e.get("GOOGLE_CLOUD_PROJECT", d.gemini_project)),
            gemini_location=e.get("PRUEFLY_GEMINI_LOCATION", d.gemini_location),
            max_image_bytes=int(e.get("PRUEFLY_MAX_IMAGE_BYTES", d.max_image_bytes)),
            rate_limit_per_hour=int(e.get("PRUEFLY_RATE_LIMIT_PER_HOUR", d.rate_limit_per_hour)),
        )

"""Orchestration: photo -> IR (derender) and IR -> new IR (transform)."""
from __future__ import annotations

import logging
import secrets

from ..llm.base import AllProvidersFailed, ImageInput, ModelRouter
from . import engine, prompts, validate
from .jsonutil import extract_json
from .schema import IR, LEXICAL_TYPES

log = logging.getLogger("pruefly.pipeline")


async def analyze(router: ModelRouter, image: ImageInput) -> tuple[IR, dict, str]:
    """Photo -> (IR, slot report, provider used)."""
    ir, provider = await router.run(
        "derender",
        system=prompts.DERENDER_SYSTEM,
        prompt=prompts.derender_prompt(),
        image=image,
        max_output_tokens=8192,
        parse=lambda text: validate.parse_ir(extract_json(text)),
    )
    return ir, validate.slot_report(ir), provider


async def transform(router: ModelRouter, ir: IR, seed: int | None = None) -> tuple[IR, list[str], str | None]:
    """IR -> new variant. Numeric tasks deterministic; lexical tasks via model, validated.

    Returns (new IR, warnings, provider used for lexical part or None).
    """
    seed = secrets.randbits(31) if seed is None else seed
    out = engine.regenerate(ir, seed)
    warnings: list[str] = []
    provider_used: str | None = None

    if any(t.type in LEXICAL_TYPES for t in ir.tasks):
        try:
            replaced, provider_used = await router.run(
                "transform",
                system=prompts.TRANSFORM_SYSTEM,
                prompt=prompts.transform_prompt(validate.lexical_subset(ir), ir.grade),
                max_output_tokens=4096,
                parse=lambda text: validate.parse_lexical(extract_json(text), ir),
            )
            for t in out.tasks:
                if t.id in replaced:
                    t.c = replaced[t.id].c
        except AllProvidersFailed as exc:
            log.warning("lexical transform failed: %s", exc)
            warnings.append("Wörter/Sätze konnten nicht neu erzeugt werden – diese Aufgaben sind unverändert.")
    validate.fix_info_boxes(out)
    return out, warnings, provider_used

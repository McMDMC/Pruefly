"""Tolerant JSON extraction from model output."""
from __future__ import annotations

import json
import re

_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.I)


def extract_json(text: str) -> dict:
    """Parse the first JSON object in ``text`` (handles ```json fences and chatter)."""
    t = _FENCE.sub("", text.strip()).strip()
    try:
        v = json.loads(t)
    except json.JSONDecodeError:
        start = t.find("{")
        if start < 0:
            raise ValueError("no JSON object in answer") from None
        v, _ = json.JSONDecoder().raw_decode(t[start:])
    if not isinstance(v, dict):
        raise ValueError("JSON root is not an object")
    return v

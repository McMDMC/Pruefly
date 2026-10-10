"""Deterministic offline provider for tests and demo mode (PRUEFLY_*_PROVIDERS=fake)."""
from __future__ import annotations

import json
import re

from .base import ImageInput

DEMO_IR = {
    "title": "Mathe-Test Plus und Minus",
    "subject": "mathe",
    "grade": 1,
    "tasks": [
        {
            "id": "t1",
            "type": "eq_grid",
            "title": "Rechne.",
            "instr": "Schreibe das Ergebnis auf.",
            "c": {
                "items": [
                    {"tpl": "{a} + {b} = _", "giv": {"a": 7, "b": 5}},
                    {"tpl": "{a} + {b} = _", "giv": {"a": 8, "b": 9}},
                    {"tpl": "{a} - {b} = _", "giv": {"a": 15, "b": 6}},
                    {"tpl": "{a} + _ = {r}", "giv": {"a": 6, "r": 14}},
                ]
            },
        },
        {
            "id": "t2",
            "type": "word_sort",
            "title": "Ordne nach dem Alphabet.",
            "instr": "Schreibe die Wörter in der richtigen Reihenfolge auf.",
            "c": {"words": ["Haus", "Apfel", "Ball", "Zebra", "Ente"]},
        },
        {
            "id": "t3",
            "type": "number_line",
            "title": "Zahlenstrahl",
            "instr": "Welche Zahlen stehen bei den Pfeilen?",
            "c": {"from": 0, "to": 20, "ask": [4, 13, 17], "given": [10]},
        },
    ],
}

_IR_RE = re.compile(r"<<<IR\s*(.*?)\s*IR>>>", re.S)


class FakeProvider:
    """Derender -> fixed demo worksheet. Transform -> echoes the IR it was given."""

    name = "fake"

    async def complete_json(
        self,
        *,
        system: str | None,
        prompt: str,
        image: ImageInput | None = None,
        max_output_tokens: int = 8192,
    ) -> str:
        if image is not None:
            return json.dumps(DEMO_IR, ensure_ascii=False)
        m = _IR_RE.search(prompt)
        if m:
            return m.group(1)
        return json.dumps(DEMO_IR, ensure_ascii=False)

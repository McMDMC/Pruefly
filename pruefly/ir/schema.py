"""Intermediate representation (IR) of a worksheet.

Slot roles (the core invariant, inherited from the Wandelbar engine):
  GEGEBEN  given value in the original, always regenerated
  LUECKE   blank the pupil fills in, always stays blank (rendered as ``_``)
  FIX      structure/text that is never touched
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

TaskType = Literal[
    "eq_grid", "table_vn", "alphabet_errors", "word_sort", "chain", "number_line",
    "measure", "draw_lines", "shapes", "info_box", "gap_text", "text",
]
TASK_TYPES: tuple[str, ...] = TaskType.__args__  # type: ignore[attr-defined]

# Types whose new values the model must invent (words, sentences). Everything else is
# regenerated deterministically in code.
LEXICAL_TYPES = frozenset({"word_sort", "gap_text"})

# Zahlenraum (upper bound, inclusive) by Klasse, BW Bildungsplan Grundschule.
ZAHLENRAUM = {1: 20, 2: 100, 3: 1000, 4: 1_000_000}

Subject = Literal["mathe", "deutsch", "sachunterricht"]

MAX_TASKS = 30


class Task(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(max_length=32)
    type: TaskType
    title: str = Field(default="", max_length=300)
    instr: str = Field(default="", max_length=600)
    c: dict[str, Any] = Field(default_factory=dict)


class IR(BaseModel):
    model_config = ConfigDict(extra="ignore")

    title: str = Field(default="Arbeitsblatt", max_length=200)
    subject: Subject = "mathe"
    grade: int = Field(default=1, ge=1, le=4)
    tasks: list[Task] = Field(default_factory=list, max_length=MAX_TASKS)

    @field_validator("grade", mode="before")
    @classmethod
    def _grade(cls, v: Any) -> int:
        try:
            return min(4, max(1, int(v)))
        except (TypeError, ValueError):
            return 1

    @field_validator("subject", mode="before")
    @classmethod
    def _subject(cls, v: Any) -> str:
        s = str(v or "").lower()
        if s.startswith("math"):
            return "mathe"
        if s.startswith("deut"):
            return "deutsch"
        if s.startswith("sach"):
            return "sachunterricht"
        return s if s in ("mathe", "deutsch", "sachunterricht") else "mathe"

    def limit(self) -> int:
        return ZAHLENRAUM[self.grade]

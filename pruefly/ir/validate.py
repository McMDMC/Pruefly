"""Deterministic validation + reconciliation. Structure always wins over model output."""
from __future__ import annotations

import re
from typing import Any

from pydantic import ValidationError

from . import engine
from .schema import IR, LEXICAL_TYPES, Task

WORD_RE = re.compile(r"^[A-Za-zÄÖÜäöüß]{2,24}$")

# Geometric solids: counts must match. Sets tolerate curved solids (Zylinder/Kugel/Kegel).
SOLIDS: dict[str, dict[str, set[int]]] = {
    "würfel": {"Ecken": {8}, "Kanten": {12}, "Flächen": {6}},
    "quader": {"Ecken": {8}, "Kanten": {12}, "Flächen": {6}},
    "pyramide": {"Ecken": {5}, "Kanten": {8}, "Flächen": {5}},
    "kugel": {"Ecken": {0}, "Kanten": {0}, "Flächen": {1, 0}},
    "zylinder": {"Ecken": {0}, "Kanten": {2, 0}, "Flächen": {3, 2}},
    "kegel": {"Ecken": {1, 0}, "Kanten": {1, 0}, "Flächen": {2}},
}


def parse_ir(data: dict) -> IR:
    """Strict-ish parse for a derender answer. Raises ValueError so the router tries the next model."""
    try:
        ir = IR.model_validate(data)
    except ValidationError as exc:
        raise ValueError(f"invalid IR: {exc.errors()[0]['msg']}") from exc
    if not ir.tasks:
        raise ValueError("no tasks recognised")
    seen: set[str] = set()
    for i, t in enumerate(ir.tasks):
        if t.id in seen:
            t.id = f"t{i + 1}"
        seen.add(t.id)
    return ir


def fix_info_boxes(ir: IR) -> list[str]:
    """Correct wrong solid facts from the fact table. Returns warnings."""
    warns: list[str] = []
    for t in ir.tasks:
        if t.type != "info_box":
            continue
        name = str(t.c.get("title", "")).strip().lower()
        facts = t.c.get("facts")
        table = SOLIDS.get(name)
        if not table or not isinstance(facts, dict):
            continue
        for k, ok in table.items():
            if k in facts and facts[k] not in ok:
                warns.append(f"{t.id}: {k} von {t.c.get('title')} korrigiert ({facts[k]} -> {sorted(ok)[0]})")
                facts[k] = sorted(ok)[0]
    return warns


def slot_report(ir: IR) -> dict[str, Any]:
    """Counts shown to the teacher so she can verify recognition before generating."""
    rep: dict[str, Any] = {"tasks": [], "warnings": []}
    for t in ir.tasks:
        entry: dict[str, Any] = {"id": t.id, "type": t.type, "title": t.title}
        if t.type == "eq_grid":
            items = [i for i in t.c.get("items", []) if isinstance(i, dict)]
            ok = [i for i in items if engine.solve_item(i)]
            entry["items"], entry["solvable"] = len(items), len(ok)
            if len(ok) < len(items):
                rep["warnings"].append(f"{t.id}: {len(items) - len(ok)} Gleichung(en) nicht lösbar erkannt – bleiben unverändert.")
        elif t.type == "word_sort":
            entry["items"] = len(t.c.get("words", []))
        elif t.type == "gap_text":
            entry["items"] = len(t.c.get("sentences", []))
        entry["regenerable"] = t.type in engine._REGEN or t.type in LEXICAL_TYPES
        rep["tasks"].append(entry)
    rep["warnings"] += fix_info_boxes(ir)
    return rep


# --------------------------------------------------------------------------- lexical reconcile

def lexical_subset(ir: IR) -> dict:
    return {"tasks": [t.model_dump() for t in ir.tasks if t.type in LEXICAL_TYPES]}


def parse_lexical(text_obj: dict, orig: IR) -> dict[str, Task]:
    """Validate model output for lexical tasks against the original. Raises ValueError on any drift."""
    want = {t.id: t for t in orig.tasks if t.type in LEXICAL_TYPES}
    got_raw = text_obj.get("tasks")
    if not isinstance(got_raw, list):
        raise ValueError("missing tasks list")
    result: dict[str, Task] = {}
    for raw in got_raw:
        if not isinstance(raw, dict) or raw.get("id") not in want:
            continue
        o = want[raw["id"]]
        c = raw.get("c")
        if raw.get("type") != o.type or not isinstance(c, dict):
            raise ValueError(f"{o.id}: type/content drift")
        if o.type == "word_sort":
            words = c.get("words")
            ow = [str(w) for w in o.c.get("words", [])]
            if not isinstance(words, list) or len(words) != len(ow):
                raise ValueError(f"{o.id}: word count drift")
            words = [str(w).strip() for w in words]
            if not all(WORD_RE.match(w) for w in words) or len({engine.collate_key(w) for w in words}) != len(words):
                raise ValueError(f"{o.id}: invalid or duplicate words")
            if {engine.collate_key(w) for w in words} & {engine.collate_key(w) for w in ow} == {engine.collate_key(w) for w in ow}:
                raise ValueError(f"{o.id}: words not renewed")
            new_c = {**o.c, "words": words}
        else:  # gap_text
            sents = c.get("sentences")
            osn = o.c.get("sentences", [])
            if not isinstance(sents, list) or len(sents) != len(osn):
                raise ValueError(f"{o.id}: sentence count drift")
            clean = []
            for s in sents:
                if not isinstance(s, dict) or str(s.get("s", "")).count("_") != 1 or not str(s.get("a", "")).strip():
                    raise ValueError(f"{o.id}: sentence needs exactly one gap and an answer")
                if len(str(s["s"])) > 160:
                    raise ValueError(f"{o.id}: sentence too long")
                clean.append({"s": str(s["s"]), "a": str(s["a"]).strip()})
            new_c = {**o.c, "sentences": clean}
        result[o.id] = o.model_copy(update={"c": new_c})
    missing = set(want) - set(result)
    if missing:
        raise ValueError(f"missing tasks: {sorted(missing)}")
    return result

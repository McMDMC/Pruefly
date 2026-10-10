"""Deterministic core: equation solver, regeneration of numeric tasks, derived answers.

Nothing in here trusts a model. Answers are always computed from the given values.
"""
from __future__ import annotations

import random
import re
import string
from dataclasses import dataclass
from typing import Any

from .schema import IR, Task

# --------------------------------------------------------------------------- equations

_TOKEN = re.compile(r"\{(\w+)\}|(_)|(\d+)|([+\-−–×÷*/:])|(=)|(\s+)")
_OPS = {"+": "+", "-": "-", "−": "-", "–": "-", "×": "*", "*": "*", "÷": "/", ":": "/", "/": "/"}
_SHOW = {"+": "+", "-": "−", "*": "·", "/": ":"}  # Grundschule: Malpunkt, Geteiltzeichen


@dataclass
class Eq:
    """x op y = z (``rev`` -> written as z = x op y). Operand: ('var',n) | ('lit',n) | ('blank',)."""

    op: str
    ops: list[tuple]  # [x, y, z]
    rev: bool


def parse_eq(tpl: str) -> Eq | None:
    toks: list[tuple] = []
    pos = 0
    while pos < len(tpl):
        m = _TOKEN.match(tpl, pos)
        if not m:
            return None
        pos = m.end()
        var, blank, lit, op, eq, ws = m.groups()
        if ws:
            continue
        if var is not None:
            toks.append(("var", var))
        elif blank:
            toks.append(("blank",))
        elif lit is not None:
            toks.append(("lit", int(lit)))
        elif op:
            toks.append(("op", _OPS[op]))
        else:
            toks.append(("eq",))
    kinds = [t[0] for t in toks]
    if len(toks) != 5:
        return None
    if kinds[1:2] == ["op"] and kinds[3:4] == ["eq"]:
        x, o, y, _, z = toks
        rev = False
    elif kinds[1:2] == ["eq"] and kinds[3:4] == ["op"]:
        z, _, x, o, y = toks
        rev = True
    else:
        return None
    if any(t[0] in ("op", "eq") for t in (x, y, z)) or sum(t[0] == "blank" for t in (x, y, z)) != 1:
        return None
    return Eq(op=o[1], ops=[x, y, z], rev=rev)


def _val(operand: tuple, giv: dict) -> int | None:
    if operand[0] == "lit":
        return operand[1]
    if operand[0] == "var":
        v = giv.get(operand[1])
        return v if isinstance(v, int) and not isinstance(v, bool) else None
    return None


def _solve(op: str, x: int | None, y: int | None, z: int | None) -> int | None:
    """Exactly one of x,y,z is None. Returns a non-negative integer or None."""
    try:
        if z is None:
            r = {"+": x + y, "-": x - y, "*": x * y, "/": (x // y if y and x % y == 0 else None)}[op]  # type: ignore[operator]
        elif x is None:
            r = {"+": z - y, "-": z + y, "*": (z // y if y and z % y == 0 else None), "/": z * y}[op]  # type: ignore[operator]
        else:
            r = {"+": z - x, "-": x - z, "*": (z // x if x and z % x == 0 else None), "/": (x // z if z and x % z == 0 else None)}[op]  # type: ignore[operator]
    except TypeError:
        return None
    return r if isinstance(r, int) and r >= 0 else None


def solve_item(item: dict) -> dict | None:
    """-> {'x','y','z' (all filled), 'text'} or None if not a solvable one-unknown equation."""
    eq = parse_eq(str(item.get("tpl", "")))
    giv = item.get("giv") or {}
    if eq is None or not isinstance(giv, dict):
        return None
    vals = [None if o[0] == "blank" else _val(o, giv) for o in eq.ops]
    if sum(v is None for v in vals) != 1:
        return None
    i = next(k for k, v in enumerate(vals) if v is None)
    known = list(vals)
    known[i] = None
    ans = _solve(eq.op, *known)
    if ans is None:
        return None
    vals[i] = ans
    x, y, z = vals
    s = f"{x} {_SHOW[eq.op]} {y} = {z}" if not eq.rev else f"{z} = {x} {_SHOW[eq.op]} {y}"
    return {"x": x, "y": y, "z": z, "unknown": i, "answer": ans, "text": s}


def _digits(n: int) -> int:
    return len(str(abs(n)))


def _crossing(op: str, x: int, y: int) -> bool:
    if op == "+":
        return x % 10 + y % 10 >= 10
    if op == "-":
        return x % 10 < y % 10
    return False


def _rand_digits(rng: random.Random, d: int, cap: int) -> int:
    lo = 1 if d == 1 else 10 ** (d - 1)
    hi = min(10**d - 1, cap)
    if hi < lo:
        return lo
    return rng.randint(lo, hi)


def _gen_triple(op: str, orig: tuple[int, int, int], limit: int, rng: random.Random) -> tuple[int, int, int] | None:
    x0, y0, z0 = orig
    cap = max(limit, z0, x0, y0)
    for _ in range(400):
        if op == "+":
            x, y = _rand_digits(rng, _digits(x0), cap), _rand_digits(rng, _digits(y0), cap)
            z = x + y
            ok = z <= cap and _crossing("+", x, y) == _crossing("+", x0, y0)
        elif op == "-":
            x, y = _rand_digits(rng, _digits(x0), cap), _rand_digits(rng, _digits(y0), cap)
            z = x - y
            ok = z >= 0 and _crossing("-", x, y) == _crossing("-", x0, y0)
        elif op == "*":
            x, y = _rand_digits(rng, _digits(x0), 10), _rand_digits(rng, _digits(y0), 10)
            if _digits(x0) > 1 or _digits(y0) > 1:
                x, y = _rand_digits(rng, _digits(x0), cap), _rand_digits(rng, _digits(y0), cap)
            z = x * y
            ok = z <= cap and x > 1 and y > 1
        else:  # "/" : x = dividend, y = divisor, z = quotient
            y = _rand_digits(rng, _digits(y0), 10 if _digits(y0) == 1 else cap)
            z = _rand_digits(rng, _digits(z0), 10 if _digits(z0) == 1 else cap)
            x = y * z
            ok = x <= cap and y > 1 and z > 1
        if ok and (x, y, z) != orig:
            return x, y, z
    return None


def _render_tpl(eq: Eq, new: tuple[int, int, int]) -> tuple[str, dict]:
    """Rebuild tpl/giv with new values, keeping variable names and the blank position."""
    giv: dict[str, int] = {}
    parts: list[str] = []
    for o, v in zip(eq.ops, new):
        if o[0] == "blank":
            parts.append("_")
        elif o[0] == "var":
            giv[o[1]] = v
            parts.append("{" + o[1] + "}")
        else:
            parts.append(str(v))
    x, y, z = parts
    sym = {"+": "+", "-": "-", "*": "×", "/": ":"}[eq.op]
    return (f"{z} = {x} {sym} {y}" if eq.rev else f"{x} {sym} {y} = {z}"), giv


def regenerate_eq_item(item: dict, limit: int, rng: random.Random) -> dict:
    solved = solve_item(item)
    eq = parse_eq(str(item.get("tpl", "")))
    if solved is None or eq is None:
        return item
    triple = _gen_triple(eq.op, (solved["x"], solved["y"], solved["z"]), limit, rng)
    if triple is None:
        return item
    tpl, giv = _render_tpl(eq, triple)
    return {"tpl": tpl, "giv": giv}


# --------------------------------------------------------------------------- helpers

def collate_key(word: str) -> str:
    """German DIN 5007-1 style: ä->a, ö->o, ü->u, ß->ss, case-insensitive."""
    t = word.casefold().replace("ß", "ss")
    for a, b in (("ä", "a"), ("ö", "o"), ("ü", "u")):
        t = t.replace(a, b)
    return t


def sort_words(words: list[str]) -> list[str]:
    return sorted(words, key=lambda w: (collate_key(w), w))


ALPHABET = string.ascii_uppercase


def _step_for(span: int) -> int:
    """Tick step so a number line never has more than ~20 labelled ticks."""
    for s in (1, 2, 5, 10, 20, 25, 50, 100, 200, 250, 500, 1000, 2000, 2500, 5000, 10_000, 20_000, 25_000, 50_000,
              100_000, 200_000, 250_000, 500_000, 1_000_000):
        if span / s <= 20:
            return s
    return span


def tick_step(lo: int, hi: int) -> int:
    return _step_for(max(1, hi - lo))


def _int(v: Any, default: int = 0) -> int:
    return v if isinstance(v, int) and not isinstance(v, bool) else default


# --------------------------------------------------------------------------- per-task regeneration

def _regen_eq_grid(c: dict, limit: int, rng: random.Random) -> dict:
    return {"items": [regenerate_eq_item(i, limit, rng) for i in c.get("items", []) if isinstance(i, dict)]}


def _vn_fill(row: dict) -> dict | None:
    cells = [row.get("vor"), row.get("zahl"), row.get("nach")]
    nums = [(i, v) for i, v in enumerate(cells) if isinstance(v, int) and not isinstance(v, bool)]
    if len(nums) != 1:
        return None
    i, v = nums[0]
    z = v - (i - 1)
    return {"vor": z - 1, "zahl": z, "nach": z + 1, "given": i}


def _regen_table_vn(c: dict, limit: int, rng: random.Random) -> dict:
    rows = []
    for r in c.get("rows", []):
        f = _vn_fill(r) if isinstance(r, dict) else None
        if f is None:
            rows.append(r)
            continue
        z = rng.randint(2, max(3, limit - 1))
        new = {"vor": z - 1, "zahl": z, "nach": z + 1}
        keys = ("vor", "zahl", "nach")
        rows.append({k: (new[k] if i == f["given"] else "_") for i, k in enumerate(keys)})
    return {"rows": rows}


def _chain_values(ch: dict) -> list[int] | None:
    start = ch.get("start")
    if not isinstance(start, int):
        return None
    out, cur = [start], start
    for st in ch.get("steps", []):
        m = re.fullmatch(r"\s*([+\-−×÷*:/])\s*(\d+)\s*", str(st))
        if not m:
            return None
        o, n = _OPS[m.group(1)], int(m.group(2))
        if o == "+":
            cur += n
        elif o == "-":
            cur -= n
        elif o == "*":
            cur *= n
        else:
            if n == 0 or cur % n:
                return None
            cur //= n
        out.append(cur)
    return out


def _regen_chain(c: dict, limit: int, rng: random.Random) -> dict:
    chains = []
    for ch in c.get("chains", []):
        steps = [str(s) for s in ch.get("steps", [])] if isinstance(ch, dict) else []
        orig = _chain_values(ch) if isinstance(ch, dict) else None
        if orig is None:
            chains.append(ch)
            continue
        done = None
        for _ in range(300):
            start = _rand_digits(rng, _digits(orig[0]), limit)
            cur, new_steps, ok = start, [], True
            for s in steps:
                m = re.fullmatch(r"\s*([+\-−×÷*:/])\s*(\d+)\s*", s)
                o, n0 = _OPS[m.group(1)], int(m.group(2))  # type: ignore[union-attr]
                n = _rand_digits(rng, _digits(n0), 10 if o in "*/" else limit)
                if o == "+":
                    cur += n
                elif o == "-":
                    cur -= n
                elif o == "*":
                    cur *= n
                else:
                    if n < 2 or cur % n:
                        ok = False
                        break
                    cur //= n
                if cur < 0 or cur > limit:
                    ok = False
                    break
                new_steps.append(f"{_SHOW[o]}{n}".replace("·", "×"))
            if ok:
                done = {"start": start, "steps": new_steps}
                break
        chains.append(done or ch)
    return {"chains": chains}


def _regen_number_line(c: dict, limit: int, rng: random.Random) -> dict:
    lo, hi = _int(c.get("from"), 0), _int(c.get("to"), 20)
    if hi <= lo:
        return c
    step = tick_step(lo, hi)
    ticks = [t for t in range(lo, hi + 1, step) if lo < t < hi]  # interior ticks only: ends are labelled anyway
    n_ask, n_giv = len(c.get("ask", [])), len(c.get("given", []))
    need = n_ask + n_giv
    if need > len(ticks):
        return c
    pick = rng.sample(ticks, need)
    return {"from": lo, "to": hi, "ask": sorted(pick[:n_ask]), "given": sorted(pick[n_ask:])}


def _regen_measure(c: dict, limit: int, rng: random.Random) -> dict:
    items = []
    for it in c.get("items", []):
        if not isinstance(it, dict):
            continue
        n = it.get("len")
        if isinstance(n, (int, float)) and n > 0:
            cap = 15 if it.get("unit", "cm") == "cm" else 150
            n2 = rng.randint(2, cap)
            if n2 == n:
                n2 = n2 + 1 if n2 < cap else n2 - 1
            it = {**it, "len": n2}
        items.append(it)
    return {"items": items}


def _regen_alphabet(c: dict, limit: int, rng: random.Random) -> dict:
    rows = []
    for r in c.get("rows", []):
        seq = r.get("seq") if isinstance(r, dict) else None
        if not isinstance(seq, list) or len(seq) < 4:
            rows.append(r)
            continue
        n = len(seq)
        start = rng.randint(0, 26 - n)
        good = list(ALPHABET[start : start + n])
        bad = rng.randrange(1, n - 1)
        wrong = rng.choice([ch for ch in ALPHABET if ch not in good])
        rows.append({"seq": [wrong if i == bad else ch for i, ch in enumerate(good)]})
    return {"rows": rows}


def _regen_shapes(c: dict, limit: int, rng: random.Random) -> dict:
    items = []
    for it in c.get("items", []):
        if isinstance(it, dict) and isinstance(it.get("count"), int):
            n = rng.randint(1, 9)
            if n == it["count"]:
                n = n % 9 + 1
            it = {**it, "count": n}
        items.append(it)
    return {**c, "items": items}


_REGEN = {
    "eq_grid": _regen_eq_grid,
    "table_vn": _regen_table_vn,
    "chain": _regen_chain,
    "number_line": _regen_number_line,
    "measure": _regen_measure,
    "alphabet_errors": _regen_alphabet,
    "shapes": _regen_shapes,
}


def regenerate(ir: IR, seed: int | None = None) -> IR:
    """Deterministically regenerate every numeric task (seeded). Lexical tasks are untouched."""
    rng = random.Random(seed)
    out = ir.model_copy(deep=True)
    for t in out.tasks:
        fn = _REGEN.get(t.type)
        if fn is not None:
            t.c = fn(t.c, out.limit(), rng)
    return out


# --------------------------------------------------------------------------- derived answers

def derive(task: Task) -> dict:
    """Answers recomputed from the task content. Never stored, never trusted from a model."""
    c = task.c
    if task.type == "eq_grid":
        return {"answers": [solve_item(i) for i in c.get("items", []) if isinstance(i, dict)]}
    if task.type == "table_vn":
        return {"rows": [_vn_fill(r) if isinstance(r, dict) else None for r in c.get("rows", [])]}
    if task.type == "chain":
        return {"values": [_chain_values(ch) if isinstance(ch, dict) else None for ch in c.get("chains", [])]}
    if task.type == "word_sort":
        return {"sorted": sort_words([str(w) for w in c.get("words", [])])}
    if task.type == "alphabet_errors":
        out = []
        for r in c.get("rows", []):
            seq = [str(s).upper() for s in (r.get("seq") if isinstance(r, dict) else []) or []]
            if len(seq) < 4:
                out.append(None)
                continue
            # the correct run is the one that matches the majority of consecutive positions
            best = None
            for s in range(0, 26 - len(seq) + 1):
                good = list(ALPHABET[s : s + len(seq)])
                diff = [i for i, (a, b) in enumerate(zip(seq, good)) if a != b]
                if len(diff) <= 1 and (best is None or len(diff) < len(best[1])):
                    best = (good, diff)
            out.append({"good": best[0], "bad": best[1]} if best else None)
        return {"rows": out}
    if task.type == "number_line":
        return {"ask": list(c.get("ask", []))}
    if task.type == "measure":
        return {"len": [i.get("len") for i in c.get("items", []) if isinstance(i, dict)]}
    if task.type == "shapes":
        return {"counts": [i.get("count") for i in c.get("items", []) if isinstance(i, dict)]}
    if task.type == "gap_text":
        return {"answers": [s.get("a") for s in c.get("sentences", []) if isinstance(s, dict)]}
    return {}

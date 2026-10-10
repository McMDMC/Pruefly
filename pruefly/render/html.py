"""IR -> self-contained HTML (A4 sheet). Everything user/model-derived is escaped."""
from __future__ import annotations

from html import escape as e
from pathlib import Path

from ..ir import engine
from ..ir.schema import IR, Task
from . import svg

CSS = (Path(__file__).parent / "sheet.css").read_text(encoding="utf-8")
COLORS = ["#2563eb", "#059669", "#d97706", "#7c3aed", "#db2777", "#0891b2"]
SHOW_OP = {"+": "+", "-": "−", "*": "·", "/": ":"}


def _n(v: object) -> str:
    return e(f"{v:,}".replace(",", ".")) if isinstance(v, int) and not isinstance(v, bool) and abs(v) >= 10000 else e(str(v))


def _blank(sol: bool, text: object = "") -> str:
    return f'<span class="blank">{_n(text) if sol else ""}</span>'


def _eq_html(item: dict, sol: bool) -> str:
    s = engine.solve_item(item)
    eq = engine.parse_eq(str(item.get("tpl", "")))
    if s is None or eq is None:  # unsolvable: show text as-is with blanks
        txt = str(item.get("tpl", "")).replace("_", "\0")
        giv = item.get("giv") if isinstance(item.get("giv"), dict) else {}
        for k, v in giv.items():
            txt = txt.replace("{" + str(k) + "}", str(v))
        return e(txt).replace("\0", _blank(False))
    vals = [s["x"], s["y"], s["z"]]
    parts = [(_blank(sol, vals[i]) if i == s["unknown"] else _n(vals[i])) for i in range(3)]
    op = SHOW_OP[eq.op]
    x, y, z = parts
    return f"{z} = {x} {op} {y}" if eq.rev else f"{x} {op} {y} = {z}"


def _task_body(t: Task, sol: bool) -> str:
    c, d = t.c, engine.derive(t)
    if t.type == "eq_grid":
        cells = [f'<div class="eq">{_eq_html(i, sol)}</div>' for i in c.get("items", []) if isinstance(i, dict)]
        return f'<div class="grid">{"".join(cells)}</div>'
    if t.type == "table_vn":
        rows = []
        for r, f in zip(c.get("rows", []), d["rows"]):
            if not f:
                continue
            tds = []
            for i, k in enumerate(("vor", "zahl", "nach")):
                if i == f["given"]:
                    tds.append(f"<td>{_n(f[k])}</td>")
                else:
                    tds.append(f'<td><span class="ans">{_n(f[k]) if sol else ""}</span></td>')
            rows.append("<tr>" + "".join(tds) + "</tr>")
        return ('<table class="vn"><tr><th>Vorgänger</th><th>Zahl</th><th>Nachfolger</th></tr>'
                + "".join(rows) + "</table>")
    if t.type == "alphabet_errors":
        out = []
        for r, f in zip(c.get("rows", []), d["rows"]):
            seq = [str(x).upper()[:2] for x in (r.get("seq") or [])]
            bad = set(f["bad"]) if f else set()
            letters = "".join(f'<span class="l{" bad" if i in bad else ""}">{e(ch)}</span>' for i, ch in enumerate(seq))
            fix = ""
            if sol and f:
                fix = "".join(f'<span class="fix">{e(f["good"][i])}</span>' for i in f["bad"])
            out.append(f'<div class="letters">{letters}{fix}</div>')
        return "".join(out)
    if t.type == "word_sort":
        words = "".join(f"<span>{e(str(w))}</span>" for w in c.get("words", []))
        if sol:
            lines = "".join(f"<div>{i + 1}. {e(w)}</div>" for i, w in enumerate(d["sorted"]))
        else:
            lines = "".join(f"<div>{i + 1}.</div>" for i in range(len(c.get("words", []))))
        return f'<div class="words">{words}</div><div class="lines">{lines}</div>'
    if t.type == "chain":
        out = []
        for ch, vals in zip(c.get("chains", []), d["values"]):
            if not vals:
                continue
            bits = [f'<span class="box">{_n(vals[0])}</span>']
            for step, v in zip(ch.get("steps", []), vals[1:]):
                bits.append(f'<span class="arr">{e(str(step).replace("*", "×").replace("/", ":"))}<i>→</i></span>')
                bits.append(f'<span class="box ans">{_n(v) if sol else ""}</span>')
            out.append(f'<div class="chain">{"".join(bits)}</div>')
        return "".join(out)
    if t.type == "number_line":
        lo, hi = engine._int(c.get("from"), 0), engine._int(c.get("to"), 20)
        ask = [v for v in c.get("ask", []) if isinstance(v, int)]
        giv = [v for v in c.get("given", []) if isinstance(v, int)]
        return svg.number_line(lo, max(hi, lo + 1), ask, giv, sol)
    if t.type == "measure":
        out = []
        for it in c.get("items", []):
            if not isinstance(it, dict) or not isinstance(it.get("len"), (int, float)):
                continue
            unit = "mm" if it.get("unit") == "mm" else "cm"
            cm = it["len"] / 10 if unit == "mm" else it["len"]
            ans = f'{_n(it["len"])} {unit}' if sol else f'<span class="blank"></span> {unit}'
            out.append(f'<div class="measure">{e(str(it.get("label", "")))}'
                       f'<div class="bar" style="width:{min(cm, 17):.2f}cm"></div>Länge: {ans}</div>')
        return "".join(out) + '<p class="warn">Beim Drucken „Tatsächliche Größe“ (100 %) wählen.</p>'
    if t.type == "draw_lines":
        return svg.draw_grid(engine._int(c.get("cols"), 6), engine._int(c.get("rows"), 4), c.get("segments", []))
    if t.type == "shapes":
        out = []
        for it, cnt in zip(c.get("items", []), d["counts"]):
            if not isinstance(it, dict) or not isinstance(cnt, int):
                continue
            kind = it.get("shape") if it.get("shape") in svg.SHAPES else "circle"
            icons = "".join(svg.shape_svg(kind) for _ in range(min(cnt, 20)))
            out.append(f'<div class="shape-row">{icons}<span>Anzahl: <span class="box ans">{cnt if sol else ""}</span></span></div>')
        return "".join(out)
    if t.type == "info_box":
        facts = c.get("facts") if isinstance(c.get("facts"), dict) else {}
        lis = "".join(f"<li>{e(str(k))}: {e(str(v))}</li>" for k, v in facts.items())
        return f'<div class="info"><h3>{e(str(c.get("title", "")))}</h3><ul>{lis}</ul></div>'
    if t.type == "gap_text":
        sents = [s for s in c.get("sentences", []) if isinstance(s, dict)]
        bank = "".join(f"<span>{e(w)}</span>" for w in engine.sort_words([str(s.get("a", "")) for s in sents]))
        out = [f'<div class="bank">{bank}</div>']
        for s in sents:
            left, _, right = str(s.get("s", "")).partition("_")
            out.append(f'<div class="gap">{e(left)}{_blank(sol, s.get("a", ""))}{e(right)}</div>')
        return "".join(out)
    return f'<p class="text">{e(str(c.get("text", "")))}</p>'


def render_html(ir: IR, solution: bool = False) -> str:
    tasks = []
    for i, t in enumerate(ir.tasks):
        color = COLORS[i % len(COLORS)]
        try:
            body = _task_body(t, solution)
        except Exception:  # noqa: BLE001 - malformed model content must never kill the whole sheet
            body = '<p class="warn">Diese Aufgabe konnte nicht dargestellt werden.</p>'
        tasks.append(
            f'<section class="task" style="--tc:{color}"><h2><span class="no">{i + 1}</span>{e(t.title)}</h2>'
            + (f'<p class="instr">{e(t.instr)}</p>' if t.instr else "")
            + body + "</section>"
        )
    banner = '<div class="sol-banner">Lösungsblatt – nur für die Lehrkraft</div>' if solution else ""
    meta = "" if solution else '<div class="meta">Name: ____________ &nbsp; Datum: ________</div>'
    return (
        '<!doctype html><html lang="de"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>{e(ir.title)}</title><style>{CSS}</style></head>"
        f'<body class="{"sol" if solution else ""}"><div class="sheet">{banner}'
        f'<header class="top"><h1>{e(ir.title)}</h1>{meta}</header>{"".join(tasks)}</div></body></html>'
    )

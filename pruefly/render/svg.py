"""Small SVG builders. All text goes through html.escape."""
from __future__ import annotations

from html import escape as e

from ..ir import engine

SHAPES = {"circle", "square", "triangle", "rect"}


def shape_svg(kind: str, size: int = 26, fill: str = "#93c5fd") -> str:
    s = size
    body = {
        "circle": f'<circle cx="{s/2}" cy="{s/2}" r="{s/2-2}"/>',
        "square": f'<rect x="2" y="2" width="{s-4}" height="{s-4}"/>',
        "rect": f'<rect x="1" y="{s*0.2}" width="{s-2}" height="{s*0.6}"/>',
        "triangle": f'<polygon points="{s/2},2 {s-2},{s-2} 2,{s-2}"/>',
    }.get(kind, f'<circle cx="{s/2}" cy="{s/2}" r="{s/2-2}"/>')
    return (f'<svg width="{s}" height="{s}" viewBox="0 0 {s} {s}" fill="{fill}" stroke="#1b1b1f" '
            f'stroke-width="1.5">{body}</svg>')


def number_line(lo: int, hi: int, ask: list[int], given: list[int], solution: bool) -> str:
    w, h, pad = 640, 90, 24
    span = max(1, hi - lo)
    step = engine.tick_step(lo, hi)
    x = lambda v: pad + (v - lo) / span * (w - 2 * pad)  # noqa: E731
    out = [f'<svg viewBox="0 0 {w} {h}" width="100%" style="max-width:170mm" font-family="DejaVu Sans, sans-serif">',
           f'<line x1="{pad-8}" y1="50" x2="{w-pad+8}" y2="50" stroke="#1b1b1f" stroke-width="2"/>']
    first = lo - lo % step if lo % step else lo
    labelled = set(given) | {lo, hi}
    for v in range(first, hi + 1, step):
        if v < lo:
            continue
        big = v in labelled
        out.append(f'<line x1="{x(v):.1f}" y1="{42 if big else 45}" x2="{x(v):.1f}" y2="{58 if big else 55}" stroke="#1b1b1f" stroke-width="{2 if big else 1.2}"/>')
        if big:
            out.append(f'<text x="{x(v):.1f}" y="76" font-size="13" text-anchor="middle">{e(f"{v:,}".replace(",", "."))}</text>')
    for v in ask:
        if lo <= v <= hi:
            out.append(f'<path d="M{x(v):.1f} 40 l-6 -12 h12 z" fill="#c2410c"/>')
            if solution:
                out.append(f'<text x="{x(v):.1f}" y="20" font-size="13" font-weight="700" fill="#c2410c" text-anchor="middle">{e(f"{v:,}".replace(",", "."))}</text>')
            else:
                out.append(f'<rect x="{x(v)-16:.1f}" y="2" width="32" height="16" rx="3" fill="none" stroke="#1b1b1f" stroke-width="1.4"/>')
    out.append("</svg>")
    return "".join(out)


def draw_grid(cols: int, rows: int, segments: list) -> str:
    cell, pad = 24, 10
    w, h = cols * cell + 2 * pad, rows * cell + 2 * pad
    out = [f'<svg viewBox="0 0 {w} {h}" width="{min(w*1.6, 420)}" height="{min(h*1.6, 420*h/w):.0f}">']
    for i in range(cols + 1):
        out.append(f'<line x1="{pad+i*cell}" y1="{pad}" x2="{pad+i*cell}" y2="{pad+rows*cell}" stroke="#cbd5e1"/>')
    for j in range(rows + 1):
        out.append(f'<line x1="{pad}" y1="{pad+j*cell}" x2="{pad+cols*cell}" y2="{pad+j*cell}" stroke="#cbd5e1"/>')
    for seg in segments:
        try:
            (x1, y1), (x2, y2) = seg
            out.append(f'<line x1="{pad+x1*cell}" y1="{pad+y1*cell}" x2="{pad+x2*cell}" y2="{pad+y2*cell}" stroke="#1b1b1f" stroke-width="2.2"/>')
        except (TypeError, ValueError):
            continue
    out.append("</svg>")
    return "".join(out)

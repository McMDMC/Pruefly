from __future__ import annotations

from ..ir.schema import IR
from .html import render_html


def render_pdf(ir: IR, solution: bool = False) -> bytes:
    from weasyprint import HTML  # heavy import, keep lazy

    # No base_url and no network: the sheet is fully self-contained.
    return HTML(string=render_html(ir, solution), base_url=None).write_pdf()

import pytest

from pruefly.ir.schema import IR
from pruefly.llm.fake import DEMO_IR
from pruefly.render.html import render_html


def test_solution_vs_student_sheet():
    ir = IR.model_validate(DEMO_IR)
    stu, sol = render_html(ir, False), render_html(ir, True)
    assert "Lösungsblatt" in sol and "Lösungsblatt" not in stu
    assert "7 + 5 = <span class=\"blank\"></span>" in stu
    assert "7 + 5 = <span class=\"blank\">12</span>" in sol
    assert "Apfel" in sol and "Name:" in stu


def test_html_is_escaped():
    ir = IR.model_validate({"title": "<script>alert(1)</script>", "tasks": [
        {"id": "t1", "type": "text", "title": "<img src=x onerror=1>", "c": {"text": "<b>x</b>"}},
        {"id": "t2", "type": "word_sort", "c": {"words": ["<i>a</i>", "b"]}},
        {"id": "t3", "type": "info_box", "c": {"title": "<u>", "facts": {"<k>": "<v>"}}},
    ]})
    out = render_html(ir)
    assert "<script>alert" not in out and "<img src" not in out and "<b>x" not in out and "<i>a" not in out


def test_huge_number_line_is_small():
    ir = IR.model_validate({"grade": 4, "tasks": [{"id": "t1", "type": "number_line",
                                                   "c": {"from": 0, "to": 1_000_000, "ask": [250000], "given": [500000]}}]})
    assert render_html(ir).count("<line") < 60


def test_garbage_content_does_not_crash():
    ir = IR.model_validate({"tasks": [
        {"id": "a", "type": "eq_grid", "c": {"items": ["x", {"tpl": 5}, {"tpl": "{a}+_", "giv": 3}]}},
        {"id": "b", "type": "table_vn", "c": {"rows": [1, {"zahl": "x"}]}},
        {"id": "c", "type": "chain", "c": {"chains": [{"start": "q"}, 3]}},
        {"id": "d", "type": "measure", "c": {"items": [{"len": "?"}, 4]}},
        {"id": "e", "type": "shapes", "c": {"items": [{"shape": "evil", "count": 3}]}},
        {"id": "f", "type": "gap_text", "c": {"sentences": [None, {"s": "ohne Lücke"}]}},
        {"id": "g", "type": "alphabet_errors", "c": {"rows": [{"seq": 5}]}},
    ]})
    render_html(ir, True)
    render_html(ir, False)


def test_pdf_smoke():
    pytest.importorskip("weasyprint")
    from pruefly.render.pdf import render_pdf

    pdf = render_pdf(IR.model_validate(DEMO_IR), True)
    assert pdf.startswith(b"%PDF")

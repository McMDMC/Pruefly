import random

import pytest

from pruefly.ir import engine
from pruefly.ir.schema import IR, Task


def test_solve_basic_and_unknown_positions():
    assert engine.solve_item({"tpl": "{a} + {b} = _", "giv": {"a": 7, "b": 5}})["answer"] == 12
    assert engine.solve_item({"tpl": "{a} + _ = {r}", "giv": {"a": 6, "r": 14}})["answer"] == 8
    assert engine.solve_item({"tpl": "_ - {b} = {r}", "giv": {"b": 4, "r": 3}})["answer"] == 7
    assert engine.solve_item({"tpl": "{a} - _ = {r}", "giv": {"a": 15, "r": 6}})["answer"] == 9
    assert engine.solve_item({"tpl": "{a} × {b} = _", "giv": {"a": 6, "b": 7}})["answer"] == 42
    assert engine.solve_item({"tpl": "_ : {b} = {r}", "giv": {"b": 4, "r": 5}})["answer"] == 20
    assert engine.solve_item({"tpl": "{r} = {a} + _", "giv": {"a": 3, "r": 10}})["answer"] == 7


@pytest.mark.parametrize(
    "item",
    [
        {"tpl": "{a} + {b} = {c}", "giv": {"a": 1, "b": 2, "c": 3}},  # no unknown
        {"tpl": "{a} : _ = {r}", "giv": {"a": 7, "r": 2}},  # not divisible
        {"tpl": "_ - {b} = {r}", "giv": {"b": 4}},  # missing given
        {"tpl": "gibberish", "giv": {}},
    ],
)
def test_unsolvable_returns_none(item):
    assert engine.solve_item(item) is None


def test_regenerate_keeps_structure_pattern_and_range():
    ir = IR(grade=2, tasks=[Task(id="t1", type="eq_grid", c={"items": [
        {"tpl": "{a} + {b} = _", "giv": {"a": 47, "b": 28}},   # crossing
        {"tpl": "{a} - {b} = _", "giv": {"a": 62, "b": 25}},   # crossing
        {"tpl": "{a} + _ = {r}", "giv": {"a": 30, "r": 74}},
    ]})])
    for seed in range(40):
        new = engine.regenerate(ir, seed)
        items = new.tasks[0].c["items"]
        assert [i["tpl"].count("_") for i in items] == [1, 1, 1]
        for it in items:
            s = engine.solve_item(it)
            assert s is not None and 0 <= s["z"] <= 100
        a, b = items[0]["giv"]["a"], items[0]["giv"]["b"]
        assert engine._crossing("+", a, b) and a >= 10 and b >= 10
        a, b = items[1]["giv"]["a"], items[1]["giv"]["b"]
        assert engine._crossing("-", a, b) and a >= b
    assert engine.regenerate(ir, 1) == engine.regenerate(ir, 1)  # seeded
    assert engine.regenerate(ir, 1) != engine.regenerate(ir, 2)


def test_original_not_mutated():
    ir = IR(grade=1, tasks=[Task(id="t1", type="eq_grid", c={"items": [{"tpl": "{a} + {b} = _", "giv": {"a": 7, "b": 5}}]})])
    engine.regenerate(ir, 3)
    assert ir.tasks[0].c["items"][0]["giv"] == {"a": 7, "b": 5}


def test_grade1_stays_within_20():
    ir = IR(grade=1, tasks=[Task(id="t1", type="eq_grid", c={"items": [{"tpl": "{a} + {b} = _", "giv": {"a": 7, "b": 5}}]})])
    for seed in range(100):
        s = engine.solve_item(engine.regenerate(ir, seed).tasks[0].c["items"][0])
        assert s["z"] <= 20


def test_mult_and_div_regeneration_exact():
    ir = IR(grade=3, tasks=[Task(id="t1", type="eq_grid", c={"items": [
        {"tpl": "{a} × {b} = _", "giv": {"a": 6, "b": 7}},
        {"tpl": "{a} : {b} = _", "giv": {"a": 56, "b": 7}},
    ]})])
    for seed in range(50):
        for it in engine.regenerate(ir, seed).tasks[0].c["items"]:
            s = engine.solve_item(it)
            assert s is not None


def test_german_collation():
    assert engine.sort_words(["Zebra", "Äpfel", "Apfel", "Ball", "ärger", "Ente"]) == [
        "Apfel", "Äpfel", "ärger", "Ball", "Ente", "Zebra"
    ]
    assert engine.sort_words(["Strauß", "Strauch", "Straße"]) == ["Straße", "Strauch", "Strauß"]


def test_tick_step_never_explodes():
    assert engine.tick_step(0, 20) == 1
    assert engine.tick_step(0, 100) == 5
    assert (1_000_000 - 0) / engine.tick_step(0, 1_000_000) <= 20


def test_number_line_regen_on_ticks():
    c = {"from": 0, "to": 100, "ask": [20, 70], "given": [50]}
    for seed in range(30):
        n = engine._regen_number_line(c, 100, random.Random(seed))
        step = engine.tick_step(0, 100)
        assert all(v % step == 0 for v in n["ask"] + n["given"])
        assert len(n["ask"]) == 2 and len(n["given"]) == 1
        assert not set(n["ask"]) & set(n["given"])
        assert all(0 < v < 100 for v in n["ask"] + n["given"])


def test_chain_and_vn_and_alphabet():
    t = Task(id="t", type="chain", c={"chains": [{"start": 7, "steps": ["+5", "−3", "+8"]}]})
    assert engine.derive(t)["values"] == [[7, 12, 9, 17]]
    new = engine._regen_chain(t.c, 20, random.Random(1))
    vals = engine._chain_values(new["chains"][0])
    assert vals and all(0 <= v <= 20 for v in vals)

    row = engine._vn_fill({"vor": "_", "zahl": 45, "nach": "_"})
    assert (row["vor"], row["nach"]) == (44, 46)
    row = engine._vn_fill({"vor": "_", "zahl": "_", "nach": 80})
    assert (row["vor"], row["zahl"]) == (78, 79)

    a = Task(id="a", type="alphabet_errors", c={"rows": [{"seq": ["D", "E", "X", "G", "H"]}]})
    d = engine.derive(a)["rows"][0]
    assert d["good"] == list("DEFGH") and d["bad"] == [2]
    new = engine._regen_alphabet(a.c, 20, random.Random(5))
    assert engine.derive(Task(id="a", type="alphabet_errors", c=new))["rows"][0] is not None

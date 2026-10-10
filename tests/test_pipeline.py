import asyncio
import json

import pytest

from pruefly.ir import pipeline, validate
from pruefly.ir.schema import IR
from pruefly.llm.base import AllProvidersFailed, ImageInput, ModelRouter
from pruefly.llm.fake import DEMO_IR, FakeProvider

IMG = ImageInput(b"x", "image/jpeg")


class Scripted:
    def __init__(self, name, answers):
        self.name, self.answers, self.calls = name, list(answers), 0

    async def complete_json(self, **kw):
        self.calls += 1
        a = self.answers.pop(0)
        if isinstance(a, Exception):
            raise a
        return a


def run(coro):
    return asyncio.run(coro)


def test_router_falls_back_on_call_failure_and_parse_failure():
    bad_call = Scripted("anthropic", [RuntimeError("boom")])
    bad_parse = Scripted("gemini", ["not json at all"])
    good = Scripted("fake", [json.dumps(DEMO_IR)])
    r = ModelRouter({"anthropic": bad_call, "gemini": bad_parse, "fake": good},
                    {"derender": ["anthropic", "gemini", "fake"], "transform": []})
    ir, rep, prov = run(pipeline.analyze(r, IMG))
    assert prov == "fake" and ir.tasks and bad_call.calls == bad_parse.calls == 1


def test_router_all_fail():
    r = ModelRouter({"a": Scripted("a", [RuntimeError("x")])}, {"derender": ["a"], "transform": []})
    with pytest.raises(AllProvidersFailed):
        run(pipeline.analyze(r, IMG))


def test_unknown_route_rejected():
    with pytest.raises(ValueError):
        ModelRouter({}, {"derender": ["nope"]})


def test_transform_full_demo_flow():
    r = ModelRouter({"fake": FakeProvider()}, {"derender": ["fake"], "transform": ["fake"]})
    ir, rep, _ = run(pipeline.analyze(r, IMG))
    assert rep["tasks"][0]["solvable"] == 4
    new, warns, _ = run(pipeline.transform(r, ir, seed=7))
    assert new.tasks[0].c != ir.tasks[0].c  # numbers regenerated
    assert [t.type for t in new.tasks] == [t.type for t in ir.tasks]
    assert new.tasks[1].c["words"] == ir.tasks[1].c["words"]  # fake echoes -> unchanged
    assert new.tasks[0].c["items"][3]["tpl"].count("_") == 1  # LÜCKE preserved


def test_lexical_reconcile_rejects_drift():
    ir = IR.model_validate(DEMO_IR)
    good = {"tasks": [{"id": "t2", "type": "word_sort", "c": {"words": ["Igel", "Katze", "Maus", "Nuss", "Rose"]}}]}
    assert validate.parse_lexical(good, ir)["t2"].c["words"][0] == "Igel"
    for bad in (
        {"tasks": [{"id": "t2", "type": "word_sort", "c": {"words": ["Igel", "Katze"]}}]},               # count
        {"tasks": [{"id": "t2", "type": "word_sort", "c": {"words": ["Igel", "Igel", "Maus", "Nuss", "Rose"]}}]},  # dup
        {"tasks": [{"id": "t2", "type": "word_sort", "c": {"words": ["Ig3l", "Katze", "Maus", "Nuss", "Rose"]}}]},  # chars
        {"tasks": []},                                                                                      # missing
    ):
        with pytest.raises(ValueError):
            validate.parse_lexical(bad, ir)


def test_info_box_facts_corrected():
    ir = IR.model_validate({"tasks": [{"id": "t1", "type": "info_box",
                                       "c": {"title": "Würfel", "facts": {"Ecken": 6, "Kanten": 12, "Flächen": 6}}}]})
    assert validate.fix_info_boxes(ir)
    assert ir.tasks[0].c["facts"]["Ecken"] == 8

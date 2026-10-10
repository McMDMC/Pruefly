import base64

import pytest
from fastapi.testclient import TestClient

from pruefly.config import Settings
from pruefly.llm.base import ModelRouter
from pruefly.llm.fake import FakeProvider
from pruefly.main import create_app

JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 300
B64 = base64.b64encode(JPEG).decode()
H = {"X-Access-Code": "geheim"}


def make(**kw):
    s = Settings(access_code=kw.pop("code", "geheim"), env=kw.pop("env", "prod"), **kw)
    r = ModelRouter({"fake": FakeProvider()}, {"derender": ["fake"], "transform": ["fake"]})
    return TestClient(create_app(s, r))


def test_fail_closed_without_code():
    c = make(code="")
    assert c.post("/api/check").status_code == 503
    assert c.post("/api/analyze", json={"image_b64": B64}).status_code == 503


def test_dev_mode_open_without_code():
    assert make(code="", env="dev").post("/api/check").status_code == 200


def test_wrong_and_missing_code():
    c = make()
    assert c.post("/api/check").status_code == 401
    assert c.post("/api/check", headers={"X-Access-Code": "nope"}).status_code == 401
    assert c.post("/api/check", headers=H).status_code == 200


def test_full_flow_and_pdf():
    c = make()
    r = c.post("/api/analyze", json={"image_b64": B64}, headers=H)
    assert r.status_code == 200, r.text
    ir = r.json()["ir"]
    t = c.post("/api/transform", json={"ir": ir, "seed": 3}, headers=H).json()
    assert t["ir"]["tasks"][0]["c"] != ir["tasks"][0]["c"]
    h = c.post("/api/render", json={"ir": t["ir"], "format": "html"}, headers=H).json()["html"]
    assert "<!doctype html>" in h
    p = c.post("/api/render", json={"ir": t["ir"], "format": "pdf", "solution": True}, headers=H)
    assert p.status_code == 200 and p.content.startswith(b"%PDF")
    assert "attachment" in p.headers["content-disposition"]


def test_rejects_non_image_and_bad_base64():
    c = make()
    bad = base64.b64encode(b"<html>" + b"x" * 300).decode()
    assert c.post("/api/analyze", json={"image_b64": bad}, headers=H).status_code == 415
    assert c.post("/api/analyze", json={"image_b64": "!" * 200}, headers=H).status_code == 400


def test_size_limits():
    c = make(max_image_bytes=1000)
    big = base64.b64encode(JPEG + b"\x00" * 5000).decode()
    assert c.post("/api/analyze", json={"image_b64": big}, headers=H).status_code == 413


def test_rate_limit():
    c = make(rate_limit_per_hour=2)
    for _ in range(2):
        assert c.post("/api/analyze", json={"image_b64": B64}, headers=H).status_code == 200
    assert c.post("/api/analyze", json={"image_b64": B64}, headers=H).status_code == 429


def test_security_headers_and_no_docs():
    c = make()
    r = c.get("/api/health")
    assert "frame-ancestors 'none'" in r.headers["content-security-policy"]
    assert c.get("/docs").status_code in (404, 405)


def test_invalid_ir_rejected():
    c = make()
    r = c.post("/api/render", json={"ir": {"tasks": [{"id": "t", "type": "evil"}]}}, headers=H)
    assert r.status_code == 422

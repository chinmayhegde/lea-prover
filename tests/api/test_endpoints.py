"""Endpoint behavior for the synchronous v1 surface (config, tools, meta, auth)."""

import shutil

import pytest
from fastapi.testclient import TestClient

from lea_api.settings import Settings

from .conftest import scripted_runner


# ---- config -----------------------------------------------------------------

def test_config_validate_ok(client):
    r = client.post("/v1/config/validate", json={"config": None})
    assert r.status_code == 200
    body = r.json()
    assert body["valid"] is True
    assert body["config"]["model_name"]            # resolved from default.yaml
    assert body["config"]["narrate_tool_steps"] is False
    assert "mcp_servers" in body["config"]


def test_config_validate_accepts_narration_flag(client):
    r = client.post("/v1/config/validate", json={"config": {"agent": {"narrate_tool_steps": True}}})
    assert r.status_code == 200
    assert r.json()["config"]["narrate_tool_steps"] is True


def test_config_validate_typed_error(client):
    r = client.post("/v1/config/validate", json={"config": {"model": {"stream": "yes"}}})
    assert r.status_code == 422
    err = r.json()["error"]
    assert err["type"] == "InvalidConfigValueError"
    assert err["field"] == "model.stream"


def test_config_default(client):
    r = client.get("/v1/config/default")
    assert r.status_code == 200
    assert "model" in r.json()


# ---- tools ------------------------------------------------------------------

def test_list_tools(client):
    r = client.get("/v1/tools")
    assert r.status_code == 200
    names = [t["name"] for t in r.json()["tools"]]
    assert "lean_check" in names
    assert len(names) >= 6                          # the six built-ins


def test_get_tool_and_404(client):
    assert client.get("/v1/tools/lean_check").json()["name"] == "lean_check"
    assert client.get("/v1/tools/nope").status_code == 404


# ---- meta -------------------------------------------------------------------

def test_meta(client):
    assert client.get("/v1/healthz").json()["status"] == "ok"
    v = client.get("/v1/version").json()
    assert "schema_version" in v
    caps = client.get("/v1/capabilities").json()
    assert "sse" in caps["transports"]
    assert caps["endpoints"]["runs"] is True


# ---- auth -------------------------------------------------------------------

def test_auth_optional_off_by_default(client):
    assert client.get("/v1/tools").status_code == 200       # no key needed


def test_auth_enforced_when_keys_set(build_app):
    app, _ = build_app(scripted_runner([]), settings=Settings(api_keys="secret"))
    with TestClient(app) as c:
        assert c.get("/v1/tools").status_code == 401
        assert c.get("/v1/tools", headers={"Authorization": "Bearer secret"}).status_code == 200
        assert c.get("/v1/tools", headers={"Authorization": "Bearer wrong"}).status_code == 401
        assert c.get("/v1/healthz").status_code == 200       # meta stays open


# ---- verify (gated on a Lean toolchain) -------------------------------------

_has_lean = bool(shutil.which("lean") or shutil.which("lake"))


@pytest.mark.skipif(not _has_lean, reason="no Lean toolchain installed")
def test_verify_trivial(client):
    r = client.post("/v1/verify", json={
        "proof": "theorem foo : 2 + 2 = 4 := by rfl", "imports": [], "target": "foo"})
    assert r.status_code == 200
    assert r.json()["verified"] is True


@pytest.mark.skipif(_has_lean, reason="Lean present; toolchain-missing path not exercised")
def test_verify_reports_missing_toolchain(client, monkeypatch):
    monkeypatch.setenv("LEA_DISABLE_LSP", "1")       # skip the LSP fast path
    r = client.post("/v1/verify", json={"proof": "theorem foo : True := trivial", "imports": []})
    assert r.status_code == 502

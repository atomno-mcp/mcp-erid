"""Серверный слой: hosted/proxy wrappers, tool paths, client singleton."""

from __future__ import annotations

from dataclasses import replace

import pytest

import mcp_erid.server as srv
from mcp_erid.errors import BackendError, EridError


async def test_hosted_no_token_hint(monkeypatch) -> None:
    monkeypatch.setattr(srv, "_settings", replace(srv._settings, token=None))
    out = await srv._hosted_call("audit_batch", lambda: _fail())
    assert out["error"] == "missing_token"
    assert "MCP_ERID_API_KEY" in out["message_ru"]
    assert out["disclaimer"] == srv.DISCLAIMER


async def test_hosted_disclaimer_injected(monkeypatch) -> None:
    monkeypatch.setattr(srv, "_settings", replace(srv._settings, token="k"))

    async def _ok() -> dict:
        return {"results": []}

    out = await srv._hosted_call("audit_batch", _ok)
    assert out["disclaimer"] == srv.DISCLAIMER


async def test_hosted_backend_error_500(monkeypatch) -> None:
    monkeypatch.setattr(srv, "_settings", replace(srv._settings, token="k"))

    async def _boom() -> dict:
        raise BackendError(500, "down")

    out = await srv._hosted_call("audit_batch", _boom)
    assert out["error"] == "backend_error"
    assert out["status"] == 500


async def test_hosted_backend_error_401(monkeypatch) -> None:
    monkeypatch.setattr(srv, "_settings", replace(srv._settings, token="k"))

    async def _boom() -> dict:
        raise BackendError(401, "bad")

    out = await srv._hosted_call("audit_batch", _boom)
    assert out["error"] == "missing_token"


async def test_hosted_erid_error(monkeypatch) -> None:
    monkeypatch.setattr(srv, "_settings", replace(srv._settings, token="k"))

    async def _boom() -> dict:
        raise EridError("offline")

    out = await srv._hosted_call("audit_batch", _boom)
    assert out["error"] == "unavailable"


async def test_proxy_works_without_token(monkeypatch) -> None:
    monkeypatch.setattr(srv, "_settings", replace(srv._settings, token=None))

    async def _ok() -> dict:
        return {"valid_format": True}

    out = await srv._proxy_call("verify_erid", _ok)
    assert out["valid_format"] is True
    assert out["disclaimer"] == srv.DISCLAIMER


async def test_proxy_backend_error_carries_disclaimer(monkeypatch) -> None:
    monkeypatch.setattr(srv, "_settings", replace(srv._settings, token=None))

    async def _boom() -> dict:
        raise BackendError(500, "boom")

    out = await srv._proxy_call("audit_ad_page", _boom)
    assert out["error"] == "backend_error"
    assert out["status"] == 500
    assert out["disclaimer"] == srv.DISCLAIMER


@pytest.fixture
def mock_call(monkeypatch):
    async def _mock_call(fn):
        return {"ok": True}

    monkeypatch.setattr(srv, "_call", _mock_call)
    return _mock_call


async def test_verify_erid_tool(mock_call) -> None:
    out = await srv.verify_erid("2Vfnxxxxxx")
    assert out["disclaimer"] == srv.DISCLAIMER


async def test_audit_ad_page_tool(mock_call) -> None:
    out = await srv.audit_ad_page("https://example.com/ad")
    assert out["ok"] is True


async def test_check_compliance_38fz_tool(mock_call) -> None:
    out = await srv.check_compliance_38fz(True, False, "2Vfn", "https://x")
    assert out["disclaimer"] == srv.DISCLAIMER


async def test_explain_marking_requirement_tool(mock_call) -> None:
    out = await srv.explain_marking_requirement("erid")
    assert out["disclaimer"] == srv.DISCLAIMER


async def test_audit_batch_tool(monkeypatch, mock_call) -> None:
    monkeypatch.setattr(srv, "_settings", replace(srv._settings, token="k"))
    out = await srv.audit_batch(["https://a", "https://b"])
    assert out["ok"] is True


async def test_get_client_singleton(monkeypatch) -> None:
    monkeypatch.setattr(srv, "_client", None)
    monkeypatch.setattr(srv, "_settings", replace(srv._settings, token="k", api_base="http://test"))

    class FakeClient:
        async def aclose(self) -> None:
            return None

    monkeypatch.setattr(srv, "EridClient", lambda _s: FakeClient())
    first = await srv._get_client()
    second = await srv._get_client()
    assert first is second


def test_build_arg_parser_version() -> None:
    parser = srv._build_arg_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["--version"])


async def _fail() -> dict:
    raise AssertionError("should not be called without token")

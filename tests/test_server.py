"""Серверный слой: формат, кабинет ОРД, честные отказы."""

from __future__ import annotations

from dataclasses import replace

import pytest

import mcp_erid.server as srv
from mcp_erid.errors import AuthError, BackendError, EridError, NotFoundInCabinet, SourceUnavailable


async def test_verify_erid_format_valid() -> None:
    out = await srv.verify_erid("2Vfnxxxxxx")
    assert out["valid_format"] is True
    assert out["found"] == "unknown"
    assert out["disclaimer"] == srv.DISCLAIMER
    assert "ЕРИР" in out["message_ru"]


async def test_verify_erid_format_invalid() -> None:
    out = await srv.verify_erid("ab")
    assert out["valid_format"] is False
    assert out["ready"] is True


async def test_explain_local() -> None:
    out = await srv.explain_marking_requirement("erid")
    assert out["ready"] is True
    assert "erid" in out["summary_ru"].lower()


async def test_lookup_without_ord_key(monkeypatch) -> None:
    monkeypatch.setattr(srv, "_settings", replace(srv._settings, ord_token=None, ord_provider=None))
    out = await srv.lookup_erid("LgsiTCSaD")
    assert out["error"] == "source_not_configured"
    assert out.get("found") is not False
    assert "MCP_ERID_ORD_TOKEN" in out["message_ru"]


async def test_lookup_yandex_spec_closed(monkeypatch) -> None:
    monkeypatch.setattr(
        srv, "_settings", replace(srv._settings, ord_token="t", ord_provider="yandex")
    )
    out = await srv.lookup_erid("LgsiTCSaD")
    assert out["error"] == "spec_closed"
    assert out.get("found") is not False


async def test_lookup_vk_found(monkeypatch) -> None:
    monkeypatch.setattr(srv, "_settings", replace(srv._settings, ord_token="t", ord_provider="vk"))

    class Fake:
        async def get_by_erid(self, erid: str) -> dict:
            return {"ready": True, "found": True, "erid": erid, "creative": {"erid": erid}}

        async def aclose(self) -> None:
            return None

    monkeypatch.setattr(srv, "OrdVkClient", lambda **kwargs: Fake())
    out = await srv.lookup_erid("LgsiTCSaD")
    assert out["found"] is True
    assert out["disclaimer"] == srv.DISCLAIMER


async def test_lookup_vk_bad_key(monkeypatch) -> None:
    monkeypatch.setattr(srv, "_settings", replace(srv._settings, ord_token="bad", ord_provider="vk"))

    class Fake:
        async def get_by_erid(self, erid: str) -> dict:
            raise AuthError("ОРД VK отклонил ключ")

        async def aclose(self) -> None:
            return None

    monkeypatch.setattr(srv, "OrdVkClient", lambda **kwargs: Fake())
    out = await srv.lookup_erid("LgsiTCSaD")
    assert out["error"] == "invalid_credentials"
    assert out.get("found") is not False


async def test_lookup_vk_not_in_cabinet(monkeypatch) -> None:
    monkeypatch.setattr(srv, "_settings", replace(srv._settings, ord_token="t", ord_provider="vk"))

    class Fake:
        async def get_by_erid(self, erid: str) -> dict:
            raise NotFoundInCabinet("не найден в кабинете")

        async def aclose(self) -> None:
            return None

    monkeypatch.setattr(srv, "OrdVkClient", lambda **kwargs: Fake())
    out = await srv.lookup_erid("LgsiTCSaD")
    assert out["found"] is False
    assert out["ready"] is True
    assert "ЕРИР" in out["message_ru"] or "кабинет" in out["message_ru"]


async def test_lookup_vk_unavailable(monkeypatch) -> None:
    monkeypatch.setattr(srv, "_settings", replace(srv._settings, ord_token="t", ord_provider="vk"))

    class Fake:
        async def get_by_erid(self, erid: str) -> dict:
            raise SourceUnavailable("ОРД VK не ответил вовремя.")

        async def aclose(self) -> None:
            return None

    monkeypatch.setattr(srv, "OrdVkClient", lambda **kwargs: Fake())
    out = await srv.lookup_erid("LgsiTCSaD")
    assert out["error"] == "source_unavailable"
    assert out.get("found") is not False


async def test_audit_ad_page_not_implemented() -> None:
    out = await srv.audit_ad_page("https://example.com/ad")
    assert out["error"] == "not_implemented"
    assert "нет маркировки" in out["message_ru"]


async def test_compliance_not_implemented() -> None:
    out = await srv.check_compliance_38fz(True, False, "2Vfn", "https://x")
    assert out["error"] == "not_implemented"


async def test_audit_batch_not_implemented() -> None:
    out = await srv.audit_batch(["https://a"])
    assert out["error"] == "not_implemented"


async def test_hosted_no_token_hint(monkeypatch) -> None:
    monkeypatch.setattr(srv, "_settings", replace(srv._settings, token=None))
    out = await srv._hosted_call("audit_batch", lambda: _fail())
    assert out["error"] == "source_not_configured"


async def test_hosted_401_invalid(monkeypatch) -> None:
    monkeypatch.setattr(srv, "_settings", replace(srv._settings, token="k"))

    async def _boom() -> dict:
        raise BackendError(401, "bad")

    out = await srv._hosted_call("audit_batch", _boom)
    assert out["error"] == "invalid_credentials"


async def test_hosted_500(monkeypatch) -> None:
    monkeypatch.setattr(srv, "_settings", replace(srv._settings, token="k"))

    async def _boom() -> dict:
        raise BackendError(500, "boom")

    out = await srv._hosted_call("audit_batch", _boom)
    assert out["error"] == "backend_error"


async def test_hosted_erid_error(monkeypatch) -> None:
    monkeypatch.setattr(srv, "_settings", replace(srv._settings, token="k"))

    async def _boom() -> dict:
        raise EridError("offline")

    out = await srv._hosted_call("audit_batch", _boom)
    assert out["error"] == "unavailable"


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

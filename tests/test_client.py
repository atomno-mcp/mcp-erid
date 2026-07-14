"""HTTP-клиент к hosted-бэкенду: happy path, 4xx/5xx, таймаут (respx-моки)."""

from __future__ import annotations

import httpx
import pytest
import respx

from mcp_erid.client import EridClient
from mcp_erid.config import Settings
from mcp_erid.errors import BackendError, BackendUnavailable

BASE = "http://test/erid"


def _client(token: str | None = "k") -> EridClient:
    return EridClient(Settings(api_base=BASE, token=token, timeout=5.0))


@respx.mock
async def test_verify_erid_happy_path() -> None:
    respx.post(f"{BASE}/v1/verify").mock(
        return_value=httpx.Response(
            200,
            json={"valid_format": True, "found": "unknown", "source": "public", "checked_at": "2026-07-04T00:00:00Z"},
        )
    )
    c = _client()
    try:
        out = await c.verify_erid("2Vfnxxabc")
        assert out["valid_format"] is True
        assert out["source"] == "public"
    finally:
        await c.aclose()


@respx.mock
async def test_audit_page_sends_url() -> None:
    route = respx.post(f"{BASE}/v1/audit-page").mock(
        return_value=httpx.Response(200, json={"signals": {"ad_label": "present"}})
    )
    c = _client()
    try:
        out = await c.audit_ad_page("https://example.com/post")
        assert out["signals"]["ad_label"] == "present"
        assert b"example.com" in route.calls.last.request.read()
    finally:
        await c.aclose()


@respx.mock
async def test_compliance_sends_signals() -> None:
    route = respx.post(f"{BASE}/v1/compliance").mock(
        return_value=httpx.Response(200, json={"verdict": "issues"})
    )
    c = _client()
    try:
        out = await c.check_compliance(True, False, "2Vfnxxabc", "https://example.com")
        assert out["verdict"] == "issues"
        assert b"has_advertiser_info" in route.calls.last.request.read()
    finally:
        await c.aclose()


@respx.mock
async def test_backend_401() -> None:
    respx.post(f"{BASE}/v1/audit-batch").mock(return_value=httpx.Response(401, json={"error": "unauthorized"}))
    c = _client()
    try:
        with pytest.raises(BackendError) as ei:
            await c.audit_batch(["https://example.com"])
        assert ei.value.status_code == 401
    finally:
        await c.aclose()


@respx.mock
async def test_backend_500() -> None:
    respx.post(f"{BASE}/v1/verify").mock(return_value=httpx.Response(500, text="boom"))
    c = _client()
    try:
        with pytest.raises(BackendError) as ei:
            await c.verify_erid("X")
        assert ei.value.status_code == 500
    finally:
        await c.aclose()


@respx.mock
async def test_timeout() -> None:
    respx.post(f"{BASE}/v1/explain").mock(side_effect=httpx.TimeoutException("slow"))
    c = _client()
    try:
        with pytest.raises(BackendUnavailable):
            await c.explain("responsibility")
    finally:
        await c.aclose()

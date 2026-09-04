"""ОРД VK: официальный GET /v2/creative/by_erid (моки)."""

from __future__ import annotations

import httpx
import pytest
import respx

from mcp_erid.errors import AuthError, NotFoundInCabinet, SourceUnavailable
from mcp_erid.ord_vk import DEFAULT_VK_BASE, OrdVkClient

CREATIVE = {
    "brand": "Tide. Lenor",
    "erid": "LgsiTCSaD",
    "external_id": "rpaa90bw4a4-5fb2nvhx2",
    "name": "Реклама во ВКонтакте",
    "extra_undocumented": "drop-me",
}


@respx.mock
async def test_get_by_erid_keeps_documented_fields() -> None:
    respx.get(f"{DEFAULT_VK_BASE}/v2/creative/by_erid/LgsiTCSaD").mock(
        return_value=httpx.Response(200, json=CREATIVE)
    )
    client = OrdVkClient(token="t")
    try:
        out = await client.get_by_erid("LgsiTCSaD")
        assert out["found"] is True
        assert out["creative"]["erid"] == "LgsiTCSaD"
        assert "extra_undocumented" not in out["creative"]
        assert out["scope"] == "ord_cabinet"
    finally:
        await client.aclose()


@respx.mock
async def test_401_is_auth_error() -> None:
    respx.get(f"{DEFAULT_VK_BASE}/v2/creative/by_erid/x").mock(
        return_value=httpx.Response(401, json={"error": "unauthorized"})
    )
    client = OrdVkClient(token="bad")
    try:
        with pytest.raises(AuthError):
            await client.get_by_erid("x")
    finally:
        await client.aclose()


@respx.mock
async def test_404_is_cabinet_miss_not_erir() -> None:
    respx.get(f"{DEFAULT_VK_BASE}/v2/creative/by_erid/missing").mock(
        return_value=httpx.Response(404, json={"error": "not found"})
    )
    client = OrdVkClient(token="t")
    try:
        with pytest.raises(NotFoundInCabinet, match="кабинете"):
            await client.get_by_erid("missing")
    finally:
        await client.aclose()


@respx.mock
async def test_timeout() -> None:
    respx.get(f"{DEFAULT_VK_BASE}/v2/creative/by_erid/slow").mock(
        side_effect=httpx.TimeoutException("slow")
    )
    client = OrdVkClient(token="t")
    try:
        with pytest.raises(SourceUnavailable):
            await client.get_by_erid("slow")
    finally:
        await client.aclose()

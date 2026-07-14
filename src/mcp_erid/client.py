"""HTTP-клиент к hosted-бэкенду erid (api.atomno-mcp.ru/erid).

Тонкая обёртка над httpx: один общий AsyncClient, заголовок X-API-Key (для
Pro-тулов), маппинг ошибок в EridError. Никакой бизнес-логики: валидация токена,
парсинг рекламных страниц и чек-листы 38-ФЗ — на приватном сервере. ПДн третьих
лиц на нашей стороне не персистятся.
"""

from __future__ import annotations

from typing import Any

import httpx

from . import __version__
from .config import Settings
from .errors import BackendError, BackendUnavailable

_USER_AGENT = f"atomno-mcp-erid/{__version__}"


class EridClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        headers = {"User-Agent": _USER_AGENT, "Accept": "application/json"}
        if settings.token:
            headers["X-API-Key"] = settings.token
        self._client = httpx.AsyncClient(
            base_url=settings.api_base,
            timeout=settings.timeout,
            headers=headers,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            resp = await self._client.post(path, json=payload)
        except httpx.TimeoutException as exc:
            raise BackendUnavailable(f"timeout calling {path}") from exc
        except httpx.HTTPError as exc:
            raise BackendUnavailable(f"network error calling {path}: {exc}") from exc
        return self._parse(resp)

    @staticmethod
    def _parse(resp: httpx.Response) -> dict[str, Any]:
        if resp.status_code >= 400:
            raise BackendError(resp.status_code, _extract_detail(resp))
        try:
            return resp.json()
        except ValueError as exc:
            raise BackendError(resp.status_code, "invalid JSON in response") from exc

    async def verify_erid(self, erid: str) -> dict[str, Any]:
        return await self._post("/v1/verify", {"erid": erid})

    async def audit_ad_page(self, url: str) -> dict[str, Any]:
        return await self._post("/v1/audit-page", {"url": url})

    async def check_compliance(
        self,
        has_ad_label: bool | None,
        has_advertiser_info: bool | None,
        erid: str | None,
        url: str | None,
    ) -> dict[str, Any]:
        return await self._post(
            "/v1/compliance",
            {
                "has_ad_label": has_ad_label,
                "has_advertiser_info": has_advertiser_info,
                "erid": erid,
                "url": url,
            },
        )

    async def explain(self, topic: str) -> dict[str, Any]:
        return await self._post("/v1/explain", {"topic": topic})

    async def audit_batch(self, urls: list[str]) -> dict[str, Any]:
        return await self._post("/v1/audit-batch", {"urls": urls})


def _extract_detail(resp: httpx.Response) -> str:
    try:
        body = resp.json()
    except ValueError:
        return resp.text[:300] or resp.reason_phrase
    if isinstance(body, dict):
        for key in ("message_ru", "detail", "message", "error"):
            if body.get(key):
                return str(body[key])
    return str(body)[:300]

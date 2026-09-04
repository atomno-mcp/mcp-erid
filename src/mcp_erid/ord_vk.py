"""Клиент ОРД VK по официальному описанию.

Документ: https://ord.vk.com/help/api/ref/creative.html
Метод: GET /v2/creative/by_erid/{erid}
Заголовок: Authorization: Bearer <ключ из кабинета ОРД>
База: https://api.ord.vk.com (прод), https://api-sandbox.ord.vk.com (песочница)

Это кабинет клиента, не общий поиск по ЕРИР.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

import httpx

from . import __version__
from .errors import AuthError, EridError, NotFoundInCabinet, SourceUnavailable

DEFAULT_VK_BASE = "https://api.ord.vk.com"
SOURCE = "ОРД VK, кабинет клиента (GET /v2/creative/by_erid/{erid})"

# Поля из официального примера ответа метода by_erid.
_PASSTHROUGH = (
    "brand",
    "category",
    "contract_external_id",
    "create_date",
    "description",
    "erid",
    "external_id",
    "form",
    "media_urls",
    "name",
    "okveds",
    "kktus",
    "pay_type",
    "target_urls",
    "targeting",
    "texts",
)


class OrdVkClient:
    def __init__(
        self,
        *,
        token: str,
        base_url: str = DEFAULT_VK_BASE,
        timeout: float = 30.0,
    ) -> None:
        self._base = base_url.rstrip("/")
        self._client = httpx.AsyncClient(
            base_url=self._base,
            timeout=timeout,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
                "User-Agent": f"atomno-mcp-erid/{__version__}",
            },
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def get_by_erid(self, erid: str) -> dict[str, Any]:
        token = erid.strip()
        path = f"/v2/creative/by_erid/{quote(token, safe='')}"
        try:
            resp = await self._client.get(path)
        except httpx.TimeoutException as exc:
            raise SourceUnavailable("ОРД VK не ответил вовремя.") from exc
        except httpx.HTTPError as exc:
            raise SourceUnavailable(f"ОРД VK недоступен: {exc}") from exc

        if resp.status_code in (401, 403):
            raise AuthError(
                "ОРД VK отклонил ключ (401/403). Проверьте MCP_ERID_ORD_TOKEN. "
                "Это не ответ «erid не найден в ЕРИР»."
            )
        if resp.status_code == 404:
            raise NotFoundInCabinet(
                "В кабинете этого ОРД VK креатив с таким erid не найден. "
                "Это не проверка всей базы ЕРИР."
            )
        if resp.status_code == 429:
            raise SourceUnavailable("ОРД VK ограничил частоту запросов (429).")
        if resp.status_code >= 500:
            raise SourceUnavailable(f"ОРД VK ответил {resp.status_code}.")
        if resp.status_code >= 400:
            raise EridError(f"ОРД VK ответил {resp.status_code}: {_detail(resp)}")

        try:
            payload = resp.json()
        except ValueError as exc:
            raise SourceUnavailable("ОРД VK вернул не JSON.") from exc
        if not isinstance(payload, dict):
            raise SourceUnavailable("ОРД VK вернул неожиданный формат.")

        kept = {key: payload[key] for key in _PASSTHROUGH if key in payload}
        return {
            "ready": True,
            "found": True,
            "scope": "ord_cabinet",
            "erid": token,
            "creative": kept,
            "source": SOURCE,
            "message_ru": (
                "Креатив найден в кабинете ОРД VK по официальному методу "
                "GET /v2/creative/by_erid/{erid}. Это не поиск по всему ЕРИР."
            ),
        }


def _detail(resp: httpx.Response) -> str:
    try:
        body = resp.json()
    except ValueError:
        return (resp.text or "")[:200]
    if isinstance(body, dict) and body.get("error"):
        return str(body["error"])[:200]
    return str(body)[:200]

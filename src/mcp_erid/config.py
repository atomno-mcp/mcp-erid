"""Конфигурация из переменных окружения.

Проверка формата erid и справка работают без ключа.
Поиск в кабинете ОРД — ключ клиента (сейчас описан обмен ОРД VK).
Наше размещение — отдельная услуга (MCP_ERID_API_KEY).
Своего доступа к ЕРИР и к чужому кабинету ОРД у нас нет.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

DEFAULT_API_BASE = "https://api.atomno-mcp.ru/erid"
DEFAULT_TIMEOUT = 30.0
DEFAULT_VK_BASE = "https://api.ord.vk.com"
SUPPORTED_ORD = ("vk",)


@dataclass(frozen=True)
class Settings:
    api_base: str
    token: str | None
    timeout: float
    ord_token: str | None = None
    ord_provider: str | None = None
    ord_base_url: str | None = None

    @classmethod
    def from_env(cls) -> Settings:
        base = (os.environ.get("MCP_ERID_API_BASE") or DEFAULT_API_BASE).rstrip("/")
        token = os.environ.get("MCP_ERID_API_KEY") or None
        try:
            timeout = float(os.environ.get("MCP_ERID_TIMEOUT") or DEFAULT_TIMEOUT)
        except ValueError:
            timeout = DEFAULT_TIMEOUT
        ord_token = (os.environ.get("MCP_ERID_ORD_TOKEN") or "").strip() or None
        provider = (os.environ.get("MCP_ERID_ORD_PROVIDER") or "").strip().lower() or None
        ord_base = (os.environ.get("MCP_ERID_ORD_BASE_URL") or "").strip() or None
        return cls(
            api_base=base,
            token=token,
            timeout=timeout,
            ord_token=ord_token,
            ord_provider=provider,
            ord_base_url=ord_base,
        )

    @property
    def has_token(self) -> bool:
        return bool(self.token)

    @property
    def has_ord(self) -> bool:
        return bool(self.ord_token)

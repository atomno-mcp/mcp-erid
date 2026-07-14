"""Конфигурация тонкого клиента из переменных окружения.

Проверочные тулы (verify_erid / audit_ad_page / check_compliance_38fz /
explain_marking_requirement) идут через hosted-бэкенд и работают БЕЗ ключа
(лимит по IP на стороне бэкенда). Pro-тул `audit_batch` требует ключ.

    MCP_ERID_API_BASE — базовый URL hosted-бэкенда (default: публичный прод).
    MCP_ERID_API_KEY  — API-ключ (заголовок X-API-Key). Нужен только для Pro-тулов.
    MCP_ERID_TIMEOUT  — таймаут HTTP в секундах (default 30).
"""

from __future__ import annotations

import os
from dataclasses import dataclass

DEFAULT_API_BASE = "https://api.atomno-mcp.ru/erid"
DEFAULT_TIMEOUT = 30.0


@dataclass(frozen=True)
class Settings:
    api_base: str
    token: str | None
    timeout: float

    @classmethod
    def from_env(cls) -> Settings:
        base = (os.environ.get("MCP_ERID_API_BASE") or DEFAULT_API_BASE).rstrip("/")
        token = os.environ.get("MCP_ERID_API_KEY") or None
        try:
            timeout = float(os.environ.get("MCP_ERID_TIMEOUT") or DEFAULT_TIMEOUT)
        except ValueError:
            timeout = DEFAULT_TIMEOUT
        return cls(api_base=base, token=token, timeout=timeout)

    @property
    def has_token(self) -> bool:
        return bool(self.token)

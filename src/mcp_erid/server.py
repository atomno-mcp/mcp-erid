"""FastMCP entrypoint для atomno-mcp-erid (тонкий клиент).

Все тулы проксируют к hosted-бэкенду Atomno Labs. Проверочные тулы
(verify_erid / audit_ad_page / check_compliance_38fz / explain_marking_requirement)
работают БЕЗ ключа (лимит по IP на бэкенде). Pro-тул `audit_batch` требует
MCP_ERID_API_KEY. Каждый ответ несёт disclaimer/source.

Роль инструмента — «читалка/валидатор»: справочно, не юридическое заключение;
ответственность за маркировку рекламы по 38-ФЗ несёт рекламодатель/
рекламораспространитель (см. spec §1, §8, FR-004).
"""

from __future__ import annotations

import argparse
import asyncio
import atexit
import logging
import os
from typing import Annotated, Any

from fastmcp import FastMCP
from pydantic import Field

from . import __version__
from .client import EridClient
from .config import Settings
from .errors import BackendError, EridError

logger = logging.getLogger("mcp_erid")

_SUPPORTED_TRANSPORTS = ("stdio", "http", "sse", "streamable-http")
_DEFAULT_TRANSPORT = "stdio"
_DEFAULT_HTTP_HOST = "127.0.0.1"
_DEFAULT_HTTP_PORT = 8000
_VALID_LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")

DISCLAIMER = (
    "Справочно, не является юридическим заключением. Ответственность за "
    "корректность маркировки рекламы по 38-ФЗ несёт рекламодатель/"
    "рекламораспространитель, а не данный инструмент (роль — «читалка/"
    "валидатор»). Проверка ведётся только по публично доступным данным; полная "
    "база ЕРИР закрыта (доступ у РКН/ФАС) и не проверяется. Не аффилировано с "
    "ЕРИР, ОРД, РКН или ФАС."
)

mcp: FastMCP = FastMCP(
    name="atomno-mcp-erid",
    instructions=(
        "Russian internet-ad marking (маркировка рекламы, 38-ФЗ) checker for AI "
        "agents: validate an erid token, audit an ad page/post for the mandatory "
        "«Реклама» label, advertiser details and an erid on the surface, run a "
        "38-ФЗ compliance checklist over the collected signals, and explain the "
        "marking requirements (erid / ОРД / ЕРИР, responsibility, deadlines, "
        "fines). The tool is a read-only validator — it does not place, register "
        "or mark ads. verify_erid / audit_ad_page / check_compliance_38fz / "
        "explain_marking_requirement are free (rate-limited by IP); batch auditing "
        "(audit_batch) needs a Pro key (MCP_ERID_API_KEY). Every answer carries a "
        "disclaimer and a source; it is advisory, not a legal opinion, and "
        "responsibility for ad marking under 38-ФЗ stays with the advertiser / "
        "distributor. Only publicly available data is used; the full ЕРИР registry "
        "is closed (РКН/ФАС). Pro key: https://atomno-mcp.ru/pricing#erid-pro."
    ),
)

_client: EridClient | None = None
_client_lock = asyncio.Lock()
_settings = Settings.from_env()


async def _get_client() -> EridClient:
    global _client
    if _client is not None:
        return _client
    async with _client_lock:
        if _client is None:
            _client = EridClient(_settings)
            atexit.register(_close_client_atexit)
    assert _client is not None
    return _client


def _close_client_atexit() -> None:
    if _client is None:
        return
    try:
        asyncio.run(_client.aclose())
    except RuntimeError:
        pass


def _no_token_hint() -> dict[str, Any]:
    return {
        "error": "missing_token",
        "message_ru": (
            "Не задан MCP_ERID_API_KEY. Пакетная проверка размещений — платная "
            "(тариф Pro). Ключ: https://atomno-mcp.ru/pricing#erid-pro. Разовые "
            "проверки (verify_erid, audit_ad_page, check_compliance_38fz, "
            "explain_marking_requirement) доступны без ключа."
        ),
        "disclaimer": DISCLAIMER,
    }


async def _proxy_call(name: str, coro_factory) -> dict[str, Any]:
    """Свободный вызов hosted-бэкенда (без обязательного ключа; лимит по IP)."""
    try:
        result = await coro_factory()
        result.setdefault("disclaimer", DISCLAIMER)
        return result
    except BackendError as exc:
        logger.warning("%s backend %s: %s", name, exc.status_code, exc.detail)
        return {
            "error": "backend_error",
            "status": exc.status_code,
            "message": exc.detail,
            "disclaimer": DISCLAIMER,
        }
    except EridError as exc:
        logger.warning("%s failed: %s", name, exc)
        return {"error": "unavailable", "message": str(exc), "disclaimer": DISCLAIMER}


async def _hosted_call(name: str, coro_factory) -> dict[str, Any]:
    """Вызов Pro-тула: требует ключ, иначе подсказка."""
    if not _settings.has_token:
        return _no_token_hint()
    try:
        result = await coro_factory()
        result.setdefault("disclaimer", DISCLAIMER)
        return result
    except BackendError as exc:
        if exc.status_code == 401:
            return _no_token_hint()
        logger.warning("%s backend %s: %s", name, exc.status_code, exc.detail)
        return {
            "error": "backend_error",
            "status": exc.status_code,
            "message": exc.detail,
            "disclaimer": DISCLAIMER,
        }
    except EridError as exc:
        logger.warning("%s failed: %s", name, exc)
        return {"error": "unavailable", "message": str(exc), "disclaimer": DISCLAIMER}


async def _call(fn) -> dict[str, Any]:
    client = await _get_client()
    return await fn(client)


@mcp.tool
async def verify_erid(
    erid: Annotated[
        str,
        Field(min_length=1, description="Токен идентификатора рекламы для проверки (напр. «2Vfnxxxxxx»)."),
    ],
) -> dict[str, Any]:
    """Валидация токена erid: формат/контрольные признаки, найден ли по публичным данным, читаемость. Бесплатно."""
    return await _proxy_call(
        "verify_erid",
        lambda: _call(lambda c: c.verify_erid(erid)),
    )


@mcp.tool
async def audit_ad_page(
    url: Annotated[
        str,
        Field(min_length=1, description="URL рекламной страницы/поста для аудита маркировки."),
    ],
) -> dict[str, Any]:
    """Аудит рекламной поверхности: наличие пометки «Реклама», данных рекламодателя, привязки erid (present/absent/uncertain). Бесплатно."""
    return await _proxy_call(
        "audit_ad_page",
        lambda: _call(lambda c: c.audit_ad_page(url)),
    )


@mcp.tool
async def check_compliance_38fz(
    has_ad_label: Annotated[
        bool | None,
        Field(default=None, description="Есть ли на поверхности пометка «Реклама» (из audit_ad_page)."),
    ] = None,
    has_advertiser_info: Annotated[
        bool | None,
        Field(default=None, description="Указаны ли данные рекламодателя (наименование/ИНН)."),
    ] = None,
    erid: Annotated[
        str | None,
        Field(default=None, description="Найденный на поверхности токен erid (если есть)."),
    ] = None,
    url: Annotated[
        str | None,
        Field(default=None, description="URL размещения (контекст проверки)."),
    ] = None,
) -> dict[str, Any]:
    """Детерминированный чек-лист соответствия 38-ФЗ по собранным признакам: вердикт ok / issues / insufficient_data. Бесплатно."""
    return await _proxy_call(
        "check_compliance_38fz",
        lambda: _call(lambda c: c.check_compliance(has_ad_label, has_advertiser_info, erid, url)),
    )


@mcp.tool
async def explain_marking_requirement(
    topic: Annotated[
        str,
        Field(min_length=1, description="Тема справки: erid, ord, erir, responsibility, deadlines, fines и т.п."),
    ],
) -> dict[str, Any]:
    """Справка по требованиям маркировки рекламы (что такое erid/ОРД/ЕРИР, кто за что отвечает, сроки, штрафы). Бесплатно."""
    return await _proxy_call(
        "explain_marking_requirement",
        lambda: _call(lambda c: c.explain(topic)),
    )


@mcp.tool
async def audit_batch(
    urls: Annotated[
        list[str],
        Field(min_length=1, max_length=100, description="Список URL размещений для пакетной проверки маркировки."),
    ],
) -> dict[str, Any]:
    """Пакетная проверка размещений: таблица результатов по каждому url. Тариф Pro (MCP_ERID_API_KEY)."""
    return await _hosted_call(
        "audit_batch",
        lambda: _call(lambda c: c.audit_batch(urls)),
    )


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="atomno-mcp-erid",
        description=(
            "MCP server: проверка маркировки интернет-рекламы РФ (38-ФЗ): "
            "валидация erid, аудит страницы, чек-лист 38-ФЗ."
        ),
    )
    parser.add_argument(
        "--version",
        "-V",
        action="version",
        version=f"atomno-mcp-erid {__version__}",
        help="Show version and exit.",
    )
    parser.add_argument(
        "--transport",
        "-t",
        choices=_SUPPORTED_TRANSPORTS,
        default=_DEFAULT_TRANSPORT,
        help=f"MCP transport (default: {_DEFAULT_TRANSPORT}).",
    )
    parser.add_argument(
        "--host",
        default=_DEFAULT_HTTP_HOST,
        help=f"Host for http transports (default: {_DEFAULT_HTTP_HOST}).",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=_DEFAULT_HTTP_PORT,
        help=f"Port for http transports (default: {_DEFAULT_HTTP_PORT}).",
    )
    parser.add_argument(
        "--log-level",
        "-l",
        choices=_VALID_LOG_LEVELS,
        default=None,
        help="Logging level; overrides MCP_ERID_LOG_LEVEL (default: INFO).",
    )
    return parser


def _resolve_log_level(cli_value: str | None) -> str:
    if cli_value is not None:
        return cli_value
    env_raw = os.environ.get("MCP_ERID_LOG_LEVEL")
    if env_raw is None:
        return "INFO"
    env_norm = env_raw.strip().upper()
    if env_norm in _VALID_LOG_LEVELS:
        return env_norm
    raise ValueError(
        f"MCP_ERID_LOG_LEVEL={env_raw!r} is invalid. "
        f"Allowed: {', '.join(_VALID_LOG_LEVELS)}."
    )


def main(argv: list[str] | None = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)
    try:
        log_level = _resolve_log_level(args.log_level)
    except ValueError as exc:
        parser.error(str(exc))
        return 2  # pragma: no cover

    logging.basicConfig(level=log_level)
    run_kwargs: dict[str, Any] = {"transport": args.transport}
    if args.transport in ("http", "sse", "streamable-http"):
        run_kwargs["host"] = args.host
        run_kwargs["port"] = args.port
    mcp.run(**run_kwargs)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

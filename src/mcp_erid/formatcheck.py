"""Проверка формата токена erid. В реестр не ходит."""

from __future__ import annotations

import re

_ERID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{7,63}$")
SOURCE = "проверка формата токена erid (не реестр ЕРИР)"


def validate_erid_format(erid: str) -> tuple[bool, str | None]:
    token = erid.strip()
    if not token:
        return False, "Пустой токен erid."
    if len(token) < 8 or len(token) > 64:
        return False, "Длина erid должна быть от 8 до 64 символов."
    if not _ERID_RE.match(token):
        return False, (
            "Допустимы латиница, цифры, дефис и подчёркивание; "
            "первый символ — буква или цифра."
        )
    return True, None


def format_result(erid: str) -> dict:
    token = erid.strip()
    valid, reason = validate_erid_format(token)
    return {
        "ready": True,
        "valid_format": valid,
        "found": "unknown",
        "erid": token,
        "source": SOURCE,
        "access": {"erir_lookup": "restricted"},
        "message_ru": (
            "Формат токена erid соответствует ожидаемому шаблону. "
            "Это не проверка регистрации в ЕРИР: полная база закрыта. "
            "Поиск в кабинете вашего ОРД — тул lookup_erid и ключ оператора."
            if valid
            else f"Формат erid не прошёл проверку: {reason}"
        ),
        "format_hint_ru": reason,
    }

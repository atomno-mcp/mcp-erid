# Changelog

Все заметные изменения фиксируются здесь. Формат — [Keep a Changelog](https://keepachangelog.com/ru/1.1.0/),
версии — [SemVer](https://semver.org/lang/ru/).

## [0.1.6] — 2026-11-23

### Fixed

- Обновлён адрес автора Python-пакета.

## [0.1.5] — 2026-09-04

### Added

- Тул `lookup_erid`: поиск креатива в кабинете ОРД VK по ключу клиента (`GET /v2/creative/by_erid/{erid}`).
- Переменные `MCP_ERID_ORD_TOKEN`, `MCP_ERID_ORD_PROVIDER`, `MCP_ERID_ORD_BASE_URL`.

### Changed

- `verify_erid` проверяет формат токена локально.
- `lookup_erid` без ключа ОРД отвечает `source_not_configured`; неверный ключ — `invalid_credentials`.

## [0.1.0] — 2026-07-04

### Added

- Тонкий MCP-клиент `atomno-mcp-erid` (публичный клиент + hosted corporate API, тариф Pro).
- 5 тулов через hosted API: бесплатные `verify_erid`, `audit_ad_page`,
  `check_compliance_38fz`, `explain_marking_requirement` и Pro-тул `audit_batch`.
- Роль «читалка/валидатор»: обязательный дисклеймер (справочно, не юр-заключение;
  ответственность за маркировку по 38-ФЗ — на рекламодателе/распространителе;
  работаем только с публичными данными, полная ЕРИР закрыта) в каждом ответе.
- CLI argparse (`--help/--version/--transport/--host/--port/--log-level`), env `MCP_ERID_*`.
- Метаданные для офиц. MCP Registry (`server.json` + workflow OIDC + маркер `mcp-name`), `glama.json`, `Dockerfile`.

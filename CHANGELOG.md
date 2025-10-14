# Changelog

All notable changes to this project will be documented in this file.

## [1.0.0] - 2025-10-14

### 🚨 BREAKING CHANGE: Telegram Bot Removed

Transitioned to CLI-only architecture. Use `pixi run coach-cli --config my_config.yaml` instead of bot commands.

### Removed
- Telegram bot interface (`bot/`, `main.py`)
- Multi-user security layer (`core/security/`)
- Dependencies: `python-telegram-bot`, `cryptography`
- ~1,500+ lines of code

### Changed
- All configuration files updated to remove Telegram references
- Documentation updated for CLI-only usage

### Architecture
- **Before:** Telegram Bot → Multi-user → Encrypted Storage
- **After:** CLI → Config File → Direct Output

---

## [0.1.0] - Previous
- Initial release with Telegram bot interface
- LangGraph AI workflows
- Garmin Connect integration
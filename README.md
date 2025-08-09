# Tele Garmin — AI Triathlon Coach (Telegram)

Minimal, fast, production-ready Telegram bot that analyzes your Garmin Connect data using AI. Credentials are stored encrypted; analysis results are delivered with clear, structured messages.

## Quick start

Using Pixi (recommended):

1) Create environment file
```bash
# .env.dev
TELE_BOT_KEY=your_telegram_bot_token
ANTHROPIC_API_KEY=your_anthropic_api_key
ENVIRONMENT=development
ENV_FILE=.env.dev
```

2) Start the bot (dev)
```bash
pixi run start-dev
```

Production
```bash
# expects .env with the same keys
pixi run start-prod
```

Alternative (not recommended): plain Python
```bash
pip install -r requirements.txt
python main.py
```

## Basic usage

- /start — bootstraps the bot UI and shows available actions
- /login — secure Garmin login; credentials encrypted locally
- /coach — run AI coach (analysis + planning)
- /races — manage upcoming competitions
- /roadmap — show roadmap
- /help — quick command overview

## Security

- Encrypted at rest using Fernet keys scoped per-user in ~/.garmin_bot
- Strict file permissions enforced
- No credentials printed to logs
- Structured logging for auditability

Relevant modules:
- Secure storage: [`core/security/base.py`](core/security/base.py)
- Credentials/reports: [`core/security/credentials.py`](core/security/credentials.py), [`core/security/reports.py`](core/security/reports.py)
- Execution limits: [`core/security/execution.py`](core/security/execution.py)

## Development

Code style and lint
- Ruff (lint, import sort):
  - Check: `pixi run lint-ruff`
  - Fix: `pixi run ruff-fix`
- Black + isort (format): `pixi run format`
- Type-check: `pixi run type-check`
- Tests: `pixi run test`

Repo cleanup utility (maintainers)
- Script: [`scripts/cleanup_repo.py`](scripts/cleanup_repo.py)
- Policy: internal docstrings removed; prints standardized to logging; commented-out code removed.
- Dry-run: `python scripts/cleanup_repo.py --dry-run`
- Apply: `python scripts/cleanup_repo.py --apply`

## Project structure (high level)

```
tele_garmin/
├── bot/                     # Telegram handlers and runtime
├── core/security/           # Encrypted storage & execution limits
├── services/
│   ├── garmin/              # Garmin client and extraction
│   ├── ai/langchain/        # AI orchestrators and chains
│   ├── report/              # Report utilities
│   └── ai/tools/plotting/   # Secure plotting tools
├── utils/                   # Logging, pace utils
├── agents_docs/             # Roadmap, tech stack, codebase summary
├── main.py                  # Entry point
├── pixi.toml                # Tasks & dependencies
└── pyproject.toml           # Tooling config (ruff, black)
```

## Contributing

- Use conventional commits (e.g., `chore(cleanup): remove internal docstrings`)
- Run `pixi run ruff-fix` and `pixi run format` before pushing
- Keep logs structured and free of secrets

## License

MIT — see [`LICENSE`](LICENSE)

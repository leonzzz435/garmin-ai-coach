# Tele Garmin — AI Triathlon Coach

Minimal, fast, production-ready coaching stack that analyzes your Garmin Connect data with AI. Use either:
- Telegram front-end for a chat UX, or
- Headless CLI to run an analysis/planning job from a config file.

Credentials are encrypted locally. Outputs include clear training analysis and a weekly plan.

What's new
- Headless CLI mode with config-driven runs
- AI modes for cost vs. quality tradeoffs
- Multi-provider LLMs (Anthropic, OpenAI, OpenRouter/DeepSeek)

References
- Entry: [main.py](main.py)
- Telegram runtime: [bot/bot.py](bot/bot.py), [python.create_bot()](bot/bot.py:76)
- Config/env: [core/config.py](core/config.py), [python.AIMode()](core/config.py:15), [python.Config.from_env()](core/config.py:35)
- AI settings: [services/ai/ai_settings.py](services/ai/ai_settings.py), [python.AISettings.load_settings()](services/ai/ai_settings.py:45)
- Model selection: [services/ai/model_config.py](services/ai/model_config.py), [python.ModelSelector.get_llm()](services/ai/model_config.py:60)
- CLI: [cli/tele_garmin_cli.py](cli/tele_garmin_cli.py), [python.run_analysis_from_config()](cli/tele_garmin_cli.py:109)

## Setup

Using Pixi (recommended)

1) Create env file
```bash
# .env.dev
# Required
TELE_BOT_KEY=123456789:your_telegram_bot_token   # format: <bot_id>:<token>
ANTHROPIC_API_KEY=sk-ant-api03-...               # must start with sk-ant- or sk-ant-api03-

# Optional (enable other providers and tracing)
OPENAI_API_KEY=sk-...
OPENROUTER_API_KEY=...
DEEPSEEK_API_KEY=...    # optional, often via OpenRouter
LANGSMITH_API_KEY=lsv2_...   # optional, enables LangSmith tracing

# AI mode: standard | development | cost_effective (see “AI mode & LLMs”)
AI_MODE=development
```

2) Install and run
```bash
pixi run start-dev     # dev
# or
pixi run start-prod    # expects .env
```

Alternative (plain Python)

```bash
pip install -r requirements.txt
python main.py
```

## Two ways to run

A) Telegram front‑end (chat UX)
- Start bot:
  ```bash
  pixi run start-dev
  ```
- Commands:
  - /start — bootstraps the UI
  - /login — secure Garmin login (encrypted locally)
  - /coach — analysis + weekly planning
  - /races — manage competitions
  - /help — quick overview

Runtime entry point: [python.main()](main.py:19) → [python.create_bot()](bot/bot.py:76)

B) CLI (headless, config‑driven)
- Create a config template:
  ```bash
  pixi run coach-init my_config.yaml
  ```
- Edit the file (email, context, competitions, output, ai_mode). See example: [cli/README.md](cli/README.md)
- Run:
  ```bash
  pixi run coach-cli --config my_config.yaml
  ```
- Password input
  - Either leave credentials.password empty to be prompted securely
  - Or provide it in the config file (not recommended for shared systems)
- Outputs (in output.directory):
  - analysis.html
  - planning.html
  - summary.json (metadata + costs)

Note: The CLI sets AI_MODE from your config at runtime in [python.run_analysis_from_config()](cli/tele_garmin_cli.py:109) (see env override around line 124).

## AI mode & LLMs

AI modes (set via AI_MODE or per-run in CLI config under extraction.ai_mode)
- development — fast, cheap experiments
- standard — comprehensive analysis
- cost_effective — balanced costs

Where it’s read and used
- Env parsing: [python.Config.from_env()](core/config.py:35) reads AI_MODE
- App-wide settings: [python.AISettings.load_settings()](services/ai/ai_settings.py:45)
- Mode → default model mapping lives in AI settings (stage_models)

Choosing your model/provider
- Default provider is Anthropic (Claude). To switch, change the stage_models mapping in [services/ai/ai_settings.py](services/ai/ai_settings.py).
  - Example keys (see [python.ModelSelector.CONFIGURATIONS](services/ai/model_config.py:22)):
    - Anthropic: "claude-4", "claude-4-thinking", "claude-opus", "claude-opus-thinking", "claude-3-haiku"
    - OpenAI: "gpt-4o", "gpt-4.1", "gpt-4.5", "gpt-4o-mini", "o3", "o3-mini", "o4-mini"
    - OpenRouter/DeepSeek: "deepseek-chat", "deepseek-reasoner"
- Required API keys per provider (configure in your .env):
  - Anthropic → ANTHROPIC_API_KEY
  - OpenAI → OPENAI_API_KEY
  - OpenRouter/DeepSeek → OPENROUTER_API_KEY (and optionally DEEPSEEK_API_KEY)
- Model creation/selection is centralized in [python.ModelSelector.get_llm()](services/ai/model_config.py:60)

Minimal example to switch models by mode
- Edit the stage_models mapping in [services/ai/ai_settings.py](services/ai/ai_settings.py) so that:
  - standard → "claude-opus-thinking" (quality)
  - development → "gpt-4o" (iteration on OpenAI)
  - cost_effective → "claude-3-haiku" (budget)

## Security

- Credentials encrypted at rest (per-user keys) in ~/.garmin_bot
- Strict file permissions; no secrets in logs
- Relevant modules:
  - Secure storage: [core/security/base.py](core/security/base.py)
  - Credentials & reports: [core/security/credentials.py](core/security/credentials.py), [core/security/reports.py](core/security/reports.py)
  - Execution safety: [core/security/execution.py](core/security/execution.py)

## Project structure (high level)

```
tele_garmin/
├── bot/                     # Telegram handlers and runtime
├── core/security/           # Encrypted storage & execution limits
├── services/
│   ├── garmin/              # Garmin client and extraction
│   ├── ai/langgraph/        # Graph-based analysis & planning
│   └── ai/tools/plotting/   # Secure plotting tools
├── agents_docs/             # Roadmap, tech stack, codebase summary
├── cli/                     # Headless interface and templates
├── main.py                  # Entry point
├── pixi.toml                # Tasks & dependencies
└── pyproject.toml           # Tooling config
```

## Development

- Lint (ruff): `pixi run lint-ruff` (fix: `pixi run ruff-fix`)
- Format: `pixi run format`
- Type-check: `pixi run type-check`
- Tests: `pixi run test`

## License

MIT — see [LICENSE](LICENSE)

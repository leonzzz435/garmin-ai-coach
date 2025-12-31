# AGENTS.md

Purpose: give agentic contributors the commands, constraints, and style rules required to work safely in this repository.

## Scope & Expectations
- After completing and testing changes, remove stub or AI-generated comments from code you touched in this work.
- Applies repo-wide; nested AGENTS do not currently exist.
- Default shell is Pixi-managed Python 3.13; assume macOS/Linux parity.
- Treat Garmin user data, credentials, and LangSmith tokens as sensitive.
- Prefer additive, traceable changes; keep diffs focused on the user request.

## Repo Map (orientation only)
- `cli/`: entrypoints, CLI UX (`garmin_ai_coach_cli.py`, `rich_workflow.py`).
- `core/`: shared config/globals (dataclasses, enums, .env loading).
- `services/ai/langgraph/`: nodes, workflows, cost tracking utilities.
- `services/ai/tools/`: plotting + HITL helpers.
- `services/garmin/`: API clients, caching, extractors.
- `services/outside/`: competition ingestion.
- `tests/`: pytest suite with unit + integration markers.
- `docs/` & `agents_docs/`: screenshots, architecture notes.

## Environment Setup
- Install Pixi once: `pixi install` (reads `pixi.toml` / `pixi.lock`).
- Python must be `>=3.13,<3.14` to match lockfile.
- Copy `.env.example` → `.env`; export `AI_MODE`, provider API keys, optional `LANGSMITH_API_KEY`.
- **All repository commands that rely on the app environment must be executed through Pixi** (`pixi run <task>` or within `pixi shell`); do not bypass Pixi with raw `python`, `pip`, or tooling binaries.
- CLI entrypoints are exposed as Pixi tasks; invoke them with `pixi run …` (or from inside `pixi shell`) instead of bare `python`.
- Avoid global `pip install`; rely on Pixi to keep deps reproducible.

## Secrets & Configuration
- Never commit `.env` or generated config files with credentials.
- Use `Config.from_env()` (see `core/config.py`) to read keys; never roll your own `.env` loader.
- Validate API keys (OpenAI `sk-`, Anthropic `sk-ant-`), mirroring existing guardrails.
- Keep `AI_MODE` synchronized with CLI configs and `services/ai/ai_settings.py` stage mappings.
- Garmin passwords are requested interactively; do not log them.

## Command Cheat Sheet
- `pixi run dev`: show CLI help to validate entrypoint wiring.
- `pixi run coach-cli -- --config path.yaml`: run full workflow (respect user secrets!).
- `pixi run test`: complete pytest suite with coverage (`-v --cov=. --cov-report=term-missing`).
- `pixi run test-cov`: same + HTML report in `htmlcov/`.
- `pixi run lint-ruff`: static analysis (E,F,I,UP,B,PL)
- `pixi run ruff-fix`: auto-fix safe Ruff rules.
- `pixi run format`: `black .` (line-length 100) then `isort .`.
- `pixi run type-check`: MyPy over entire repo.
- `pixi run dead-code`: Vulture scan (requires `vulture.toml` defaults baked into command).

## Running Single Tests Quickly
- Base command: `pixi run test -- tests/test_cache_client.py::test_get_user_profile_cache_hit`.
- Filter by keyword: `pixi run test -- -k "cache and not integration"`.
- Run by marker: `pixi run test -- -m unit` (marks defined in `pytest.ini`).
- Direct pytest invocation inside Pixi shell is acceptable (`pytest tests/...`).
- Prefer `pytest -vv` only when chasing flaky async workflows; otherwise keep default verbosity.

## Lint / Format / Type Discipline
- Black enforces line length 100; Ruff tolerates 120 but stay ≤100 unless CLI tables require more.
- Ruff handles import ordering (`ruff check --select I`); no manual sorting needed post-format.
- MyPy must pass with `python>=3.10` typing (`from __future__ import annotations` optional but encouraged).
- Treat Ruff warnings (UP/B/PL) as actionable unless explicitly ignored in `pyproject.toml`.
- Run `pre-commit run --all-files` before submitting patches; hooks: black, ruff (with `--fix`), end-of-file-fixer, trailing-whitespace, YAML/TOML validators.

## CI Awareness
- GitHub Actions workflow: `.github/workflows/ci.yml` (lint + tests); keep steps green locally.
- Ensure new commands integrate with Pixi tasks so CI remains consistent.
- Avoid adding new system-level dependencies; prefer Python packages already whitelisted.

## General Code Style
- Prefer standard library + typed helpers before adding third-party libs.
- Use `Path` objects over `os.path` for filesystem work (see CLI module patterns).
- Guard `if __name__ == "__main__"` entrypoints with minimal logic; route to dedicated functions.
- Keep functions small; when branching grows, extract helper utilities (compare Garmin cache client tests).
- F-strings are preferred for string formatting/logging.
- Avoid inline lambdas in complex logic; named helpers ease testing.

## Imports & Module Boundaries
- Group imports: stdlib, third-party, local; blank line between groups.
- Avoid wildcard imports; explicit is required for clarity.
- Put optional heavyweight imports inside functions when they incur cost or introduce optional dependencies (pattern used in CLI when loading LangGraph components).
- Keep `sys.path` mutations contained to CLI entrypoints; do not scatter them elsewhere.

## Typing & Data Modeling
- Use modern union syntax (`str | None`) as seen in `core/config.py`.
- Dataclasses for simple containers (config, model descriptors); Pydantic or LangGraph state classes for validated payloads.
- Type annotate every public function/method, including async ones.
- When returning dicts, prefer `dict[str, Any]` with clear contracts documented in docstrings or section comments.
- Keep default mutables immutable by using `field(default_factory=...)` or new lists/dicts per call (see test fakes).

## Async, CLI, and Workflow Guidelines
- CLI uses `asyncio.run`; keep blocking IO outside async sections.
- Workflow steps should remain cancellable; respect `GraphInterrupt` exceptions when using LangGraph.
- Interactions with `WorkflowUI` must stream meaningful progress (headers, banners, progress bars) but avoid log spam.
- Keep CLI flags mirrored in both `argparse` and Pixi tasks so automation stays aligned.

## LangGraph Nodes & Tools
- Nodes live under `services/ai/langgraph/nodes`; follow patterns in `node_base.py` for tool wiring and cost/logging helpers.
- Always route tool creation through `configure_node_tools` to inherit plotting + HITL behavior.
- Summaries and HTML blocks belong in the `TrainingAnalysisState`; update keys atomically to keep reducers coherent.
- Use `WorkflowCostTracker` or `ProgressIntegratedCostTracker` when adding new workflows to retain cost telemetry.
- When exposing new tools, ensure LangSmith metadata (`thread_id`, `user_id`) propagates via workflow config objects.

## Logging & Error Handling
- Use module-level loggers (`logging.getLogger(__name__)`) and never `print` for operational info.
- Catch `GraphInterrupt` explicitly and re-raise; generic `Exception` handlers should log `exc_info=True` and return structured error dictionaries (`{"errors": [...]}`) for the state reducers.
- Provide actionable error prefixes; mirror `execute_node_with_error_handling` semantics.
- For retries, prefer wrapping logic in dedicated helpers instead of broad try/except blocks.
- Never swallow exceptions silently; at minimum log at DEBUG when intentionally ignoring network errors during caching.

## Testing Guidance
- Default tests are unit tests; mark slow/networking specs with `@pytest.mark.integration` or `@pytest.mark.garmin`.
- Use pytest fixtures (`tmp_path`, `caplog`) for isolation; do not rely on actual Garmin APIs.
- Maintain deterministic data builders (see `tests/test_cache_client.py` fake clients).
- Keep assertions focused on behavior, not implementation details.
- When adding async tests, use `pytest.mark.asyncio` and await tasks directly.

## Data Handling & Persistence
- Cache writes must go through provided cache clients; ensure directories are created with `Path.mkdir(parents=True, exist_ok=True)`.
- Avoid storing large blobs in git; write artifacts to `./data` or user-provided `output.directory`.
- When manipulating JSON, read/write with `Path.read_text` / `write_text(..., encoding="utf-8")`.
- Respect `GARMIN_CACHE_DIR` overrides and never hardcode OS-specific paths.

## Observability & Cost Tracking
- Enable LangSmith by setting `LANGSMITH_API_KEY`; `LangSmithConfig.setup_langsmith` manages env vars.
- Tag runs with `thread_id` / `user_id` to keep cost reports meaningful.
- When extending cost tracking, surface totals via `WorkflowCostSummary` so UI dashboards stay in sync.
- Cost trackers log HTML length deltas; preserve that behavior for incremental UI updates.

## Docs & Reporting
- Screenshots live in `docs/screenshots/`; keep binary assets out of code reviews unless necessary.
- Architecture docs sit under `agents_docs/`; update there when altering LangGraph topology.
- CLI README is canonical for user-facing steps; sync any new flags/options there.

## Cursor / Copilot Rules
- No `.cursor/rules`, `.cursorrules`, or `.github/copilot-instructions.md` files exist; this AGENTS.md is the single source of truth.

## Pull Request Expectations
- Provide concise descriptions (what/why) referencing relevant Pixi commands executed.
- Include test evidence for affected areas (command + short outcome summary).
- Keep commits logically scoped; avoid mixing formatting-only changes with logic updates.

## Performance & Resource Tips
- Resist hitting live Garmin unless absolutely required; rely on caches/mocks.
- Keep plots + HTML outputs under review-friendly sizes; link to artifacts instead of inlining base64 blobs.
- Prefer incremental state updates rather than recomputing entire LangGraph state for small changes.
- When profiling, isolate heavy operations behind feature flags to avoid slowing default runs.
- Clean up temporary files in `./data/tmp` or test-specific dirs once assertions complete.

## Release Readiness
- Update `CHANGELOG.md` for user-facing behavior or CLI flags.
- Sync new Pixi tasks with README so contributors discover them.
- Ensure `pixi run type-check` and `pixi run lint-ruff` are clean before requesting review.
- Verify generated HTML opens locally when modifying analysis/planning renderers.
- Capture known limitations or follow-ups in the PR description for transparency.

## Support & Escalation
- Tag maintainers when touching Garmin auth flows, LangGraph configs, or pricing logic.
- Surface flaky tests or infra gaps in the PR body so CI owners can triage.
- Unknown conventions? Ask in the issue/PR thread before assuming—consistency beats novelty.

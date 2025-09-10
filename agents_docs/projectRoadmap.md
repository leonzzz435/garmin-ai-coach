# Project Roadmap

This roadmap captures the minimal, high-impact cleanup plan tailored to this repository to make it reliable, easy to contribute to, and safe to ship incrementally.

## High-Level Goals
- Consistent environment via Pixi with one-command linting and testing.
- Always-green CI on pull requests and main.
- Enforced code quality (ruff, black) and type-safety baseline (optional mypy).
- Clear contributor docs for setup, run, lint, and test.
- Sensible repo hygiene (editor config, ignore rules, pre-commit).

Key configs: [pixi.toml](../pixi.toml), [pyproject.toml](../pyproject.toml), [pytest.ini](../pytest.ini), [README.md](../README.md)

## Minimal, High-Impact Cleanup Priorities (extracted for this repo)

1) Guardrails and CI
- Protect main with required reviews.
- Baseline green CI that runs lint and tests via Pixi.
- Add fast feedback (fail early on lint).

2) Repo hygiene
- Add .editorconfig for cross-IDE consistency.
- Review and keep .gitignore aligned (already solid for this project).

3) Formatting, linting, types
- Python: ruff (lint and import sort), black (format), isort via ruff rules.
- Optional: mypy type checking when ready (Pixi task exists).

4) Secrets scanning (fast pass)
- Add gitleaks as a CI job (can be non-blocking initially; make blocking once baseline is clean).
- Provide .env.example for local usage (no real secrets committed).

5) Tests and coverage
- Run pytest in CI.
- Keep coverage reporting; enforce thresholds later once stable.

6) Dependencies and environment
- Use Pixi as the single source for dependencies and tasks.
- Consolidate commands to Pixi tasks (already present for test/lint/format).

7) Docs that unblock contributors
- README: how to install/run with Pixi, how to lint/test (already present).
- Add CONTRIBUTING.md later (branching, commit style, PR checks).

## Completion Criteria
- CI runs on PR and main to execute lint and tests via Pixi.
- Lint and tests pass consistently on a clean checkout.
- Style is enforced locally (pre-commit) and in CI (ruff/black).
- Secret scanning job exists in CI (initially optional), with a plan to enforce.
- Documentation clearly explains setup, linting, testing, and running.

## Progress Tracker

- [x] Add GitHub Actions CI using Pixi for lint and tests
  - Workflow: [ci.yml](../.github/workflows/ci.yml)
- [ ] Introduce pre-commit with ruff (—fix), black, and basic whitespace fixes
- [ ] Provide .env.example (document required variables) and ensure .env is ignored
- [ ] Add CONTRIBUTING.md (branching, conventional commits, local checks)
- [ ] Consider CODEOWNERS (clear review responsibility)

## Completed Tasks
- CI pipeline created to:
  - Install Pixi.
  - Sync environment.
  - Run ruff lint: `pixi run lint-ruff`.
  - Run tests: `pixi run test`.
  - File: [ci.yml](../.github/workflows/ci.yml)

## Notes and References
- Primary developer commands live in [pixi.toml](../pixi.toml):
  - `lint-ruff`, `ruff-fix`, `format`, `test`, `type-check`.
- Lint/format configuration centralized in [pyproject.toml](../pyproject.toml).
- Test configuration in [pytest.ini](../pytest.ini).
- Contributor-facing usage documented in [README.md](../README.md).
# Garmin AI Coach CLI (primary interface)

Command-line interface for the AI triathlon coach. Uses a YAML or JSON config file to extract your Garmin data, run multi-agent AI analysis and planning, and save HTML reports.

- CLI script: [cli/garmin_ai_coach_cli.py](cli/garmin_ai_coach_cli.py)
- Config template: [cli/coach_config_template.yaml](cli/coach_config_template.yaml)
- Pixi tasks: [pixi.toml](../pixi.toml)

## Quick Start

Using Pixi (recommended):
```bash
# 1) Create a config template
pixi run coach-init my_config.yaml

# 2) Edit the file with your details (athlete.email, context, etc.)

# 3) Run the analysis and planning
pixi run coach-cli --config my_config.yaml
```

Using Python directly:
```bash
python cli/garmin_ai_coach_cli.py --init-config my_config.yaml
python cli/garmin_ai_coach_cli.py --config my_config.yaml [--output-dir ./data]
```

## Command reference

```bash
python cli/garmin_ai_coach_cli.py --config PATH [--output-dir PATH]
python cli/garmin_ai_coach_cli.py --init-config PATH
```

Options:
- --config PATH        Path to YAML or JSON config (mutually exclusive with --init-config)
- --init-config PATH   Write a config template to PATH and exit
- --output-dir PATH    Override the output.directory specified in the config

Notes:
- If `credentials.password` is not provided in the config, you will be securely prompted at runtime.
- The CLI sets AI_MODE from `extraction.ai_mode` automatically for downstream components.

## Configuration

Top-level keys:
- athlete: name, email
- context: analysis, planning (freeform text; the AI will follow these constraints)
- extraction: activities_days, metrics_days, ai_mode ("development" | "standard" | "cost_effective")
- competitions: list of {name, date (YYYY-MM-DD), race_type, priority (A/B/C), target_time (HH:MM:SS)}
- output: directory
- credentials: password (optional; leave empty for interactive prompt)

Minimal example:
```yaml
athlete:
  name: "Your Name"
  email: "you@example.com"

context:
  analysis: "Recovering from injury; focus on base building"
  planning: "Olympic triathlon in 12 weeks; build aerobic base"

extraction:
  activities_days: 7
  metrics_days: 14
  ai_mode: "development"

competitions:
  - name: "Target Race"
    date: "2026-04-15"
    race_type: "Olympic"
    priority: "A"

output:
  directory: "./data"

credentials:
  password: ""   # leave empty to be prompted
```

Advanced example (derived from real usage):
```yaml
athlete:
  name: "Athlete Name"
  email: "you@example.com"

context:
  analysis: |
    Completed my first 70.3 recently. Great result but exposed durability gaps
    due to last-minute shoe change. Analyze this multisport activity in detail.

  planning: |
    ## Start Date
    Plan should start on **Monday, xxxx-xx-xx**.

    ## Important Needs
    - Functional Strength, Durability & Triathlon Transfer
      Integrate explicit daily micro-workouts (5–10 min).
      Goals: run economy & lower-leg robustness; bike posture & core transfer; durability & recovery.

    - Shoe Adaptation & Running Technique
      Get used to carbon plate shoes (front-foot style) with targeted technique/strength.

    ## Session Constraints (Shoes)
    - Per-session shoe exclusivity: every run is tagged either `carbon` or `non-carbon`.

    ## Training Preferences
    - No indoor bike trainer available.
    - No swimming for now.

    ## Training Zones
    | Discipline | Base Metric                  |
    |------------|------------------------------|
    | Running    | LTHR ≈ 173 bpm / 4:35 min/km |
    | Cycling    | FTP ≈ 271W                   |
    | Heart Rate | Max HR ≈ 193 bpm             |

    ## Closing
    Provide structured daily checklists to support both athletic and personal goals.

extraction:
  activities_days: 21
  metrics_days: 56
  ai_mode: "standard"

competitions:
  - name: "Franklin Meilenlauf"
    date: "2025-10-12"
    race_type: "Half Marathon"
    priority: "A"
    target_time: "01:40:00"

output:
  directory: "./data"

credentials:
  password: ""  # leave empty for secure interactive input
```

Validation tips:
- Date format must be ISO `YYYY-MM-DD` for competitions.
- `athlete.email` is required; the run will fail if missing.

## Outputs

Generated files (in output.directory, default `./data`):
- analysis.html — Comprehensive performance analysis
- planning.html — Detailed weekly training plan
- metrics_result.md, activity_result.md, physiology_result.md, season_plan.md — Intermediate artifacts
- summary.json — Metadata and cost tracking with fields:
  - athlete, analysis_date, competitions
  - total_cost_usd, total_tokens
  - execution_id, trace_id, root_run_id
  - files_generated

## Environment

Set at least one provider API key in your environment (e.g., `.env`):
- OPENAI_API_KEY=...
- ANTHROPIC_API_KEY=...
- OPENROUTER_API_KEY=...
- Optional: LANGSMITH_API_KEY=... for observability

The CLI will set `AI_MODE` from your config’s `extraction.ai_mode` (see [`python.run_analysis_from_config()`](../cli/garmin_ai_coach_cli.py:110) where `AI_MODE` is exported at [`os.environ['AI_MODE'] = ai_mode`](../cli/garmin_ai_coach_cli.py:125)).

Provider selection depends on AI mode mapping:
- Default mapping in [`services/ai/ai_settings.py`](../services/ai/ai_settings.py:24) within [`python.AISettings()`](../services/ai/ai_settings.py:19):
  - `standard` → `gpt-5` (OpenAI)
  - `development` → `claude-4` (Anthropic)
  - `cost_effective` → `claude-3-haiku` (Anthropic)
- Model IDs and providers are declared in [`python.ModelSelector.CONFIGURATIONS`](../services/ai/model_config.py:22), and the provider API key is auto-selected in [`python.ModelSelector.get_llm()`](../services/ai/model_config.py:61).

Practical guidance:
- If you ONLY set `OPENAI_API_KEY`, set `extraction.ai_mode: "standard"` (maps to OpenAI by default), or edit `stage_models` in [`services/ai/ai_settings.py`](../services/ai/ai_settings.py:24) to assign an OpenAI model (e.g., `gpt-4o`, `gpt-5-mini`) to your preferred mode.
- If you ONLY set `ANTHROPIC_API_KEY`, use `extraction.ai_mode: "development"` or `"cost_effective"` (default Anthropic mapping), or update the mapping accordingly.
- For OpenRouter/DeepSeek, map your chosen mode to a model key defined in [`python.ModelSelector.CONFIGURATIONS`](../services/ai/model_config.py:22).

## Migration from Telegram bot

The Telegram chat interface is deprecated. Mappings:
- `/login` → Provide `athlete.email` and enter password at CLI prompt (or set `credentials.password`).
- `/coach` → `pixi run coach-cli --config my_config.yaml`
- `/races` → Add items under `competitions` in your config
- `/help` → `python cli/garmin_ai_coach_cli.py -h`

See the root [README.md](../README.md) for details.

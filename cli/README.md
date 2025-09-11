# Garmin AI CLI

AI triathlon coach - command-line interface.

## Quick Start

```bash
# 1. Create config template
pixi run coach-init my_config.yaml

# 2. Edit config with your Garmin email and training context

# 3. Run analysis
pixi run coach-cli --config my_config.yaml
```

## Config File Example

```yaml
athlete:
  name: "John Doe"
  email: "john@example.com"

context:
  analysis: "Recovering from injury, focusing on base building"
  planning: "Preparing for Olympic triathlon in 12 weeks"

extraction:
  activities_days: 7
  metrics_days: 14
  ai_mode: "development"  # "development" or "standard" or "cost_effective"

competitions:
  - name: "Target Race"
    date: "2026-04-15"
    race_type: "Olympic"
    priority: "A"
    target_time: "02:30:00"

output:
  directory: "./data"
```

## Output

- `analysis.html` - AI training analysis
- `planning.html` - Weekly training plan
- `summary.json` - Metadata and costs

## AI Mode Options

- **`development`**: Faster, cheaper analysis (7-14 days of data)
- **`standard`**: Comprehensive analysis (21-56 days of data)
- **`cost_effective`**: Balanced analysis for budget-conscious users

## Requirements

- Garmin Connect account
- `ANTHROPIC_API_KEY` in `.env` file

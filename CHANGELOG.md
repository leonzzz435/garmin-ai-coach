# Changelog

All notable changes to this project will be documented in this file.

## [2.2.0] - 2026-01-25

### Added

#### Model Support
- **GPT-5.2 Pro**: Added Responses API configuration with `xhigh` reasoning effort (available for future assignment).

#### Expert Output Structure
- **Structured receiver payloads**: Experts now return per-receiver fields as typed `signals`, `evidence`, `implications`, `uncertainty` payloads (instead of free-form strings).
- **Prompt-ready rendering**: Structured payloads are rendered into consistent markdown sections for downstream planners/synthesis.

### Improved

#### Prompt Information Flow
- Summarizer prompts now allow transparent compression (coverage headers, core tables, change points, data quality notes) to reduce noise while preserving decision-relevant metrics.
- Expert prompts enforce a common internal layout (Signals/Evidence/Implications/Uncertainty) and reordered prompt components for better salience and fewer contradictions.
- HITL instructions now reference the correct `output` schema for questions.

#### Web Search Capabilities
- **New `gpt-5-search` model**: GPT-5.2 with OpenAI's hosted web search tool for real-time information retrieval
- Web search runs during the model's reasoning chain-of-thought (agentic search)
- Sources automatically included via `include: ["web_search_call.action.sources"]`
- Fully compatible with structured JSON output and Pydantic models
- Enabled for expert nodes (Metrics, Physiology, Activity) and planners (Workout, Season) in STANDARD mode

#### Long-Term Fitness Trends
- **Long-term VO2 max tracking**: Weekly sampling over 360 days to capture year-long fitness evolution
- **Long-term chronic training load**: Historical training load trend at configurable intervals
- New `ExtractionConfig` options: `include_long_term_trends`, `long_term_range`, `long_term_interval`
- AI metrics summarizer now receives long-term trend data for deeper analysis

#### ACWR v2 Implementation
- **Enhanced Load Calculation**: Replaced basic Garmin metrics with a robust **Acute:Chronic Workload Ratio (v2)** model
- **Multiple Interpretations**:
  - **EWMA (Scientific)**: Exponentially Weighted Moving Average (7d/28d) for physiological accuracy
  - **Rolling Sum (Garmin-like)**: 7-day rolling sums for direct comparison with Garmin reports
- **Uncoupled Chronic Load**: Chronic load calculation excluding the acute period (t-7) to prevent "mathematically coupled" spike masking
- **Advanced Physiological Signals**:
  - **Ramp Rate**: 7-day change in chronic load
  - **Monotony & Strain**: Variation and stress indices to detectstaleness/overtraining
  - **TSB (Training Stress Balance)**: Form measurement (chronic - acute)
- **Robustness**: Timezone-aware date parsing (UTC) and multisport double-counting prevention

#### Codebase Health
- **Strict Type Checking**: Achieved 100% `mypy` compliance (0 errors) across the entire codebase.
    - Added comprehensive type annotations to `GarminConnectClient` and `DataExtractor`.
    - Resolved `MutableMapping` vs `Mapping` conflicts in orchestration layers.
    - Enforced `None` safety checks for all optional API responses.
- **Linting & Code Style**: Enforced strict `ruff` linting rules, removing unused code, dead branches, and unsafe global variables.
- **Test Stability**:
    - Fixed flaky tests in `test_data_extractor` and `outside_client`.
    - Added strict type assertions to test suites to catch regression errors early.
- **CI/CD**: Added mandatory type checking (`pixi run type-check`) to CI pipeline.

---

## [2.1.0] - 2025-11-22

### Added

#### Orchestrator & Workflow
- **Master Orchestrator Node**: Centralized routing logic that manages stage transitions (Analysis → Season Planning → Weekly Planning) and HITL interactions.
- **Plan Persistence**: New `FilePlanStorage` allows season plans to be saved and reloaded in subsequent runs, enabling iterative weekly planning without re-generating the season plan.
- **Extended Planning Horizon**: Weekly planner now generates a **28-day (4-week)** plan instead of 14 days, providing better visibility.
- **Skip Synthesis Option**: New `skip_synthesis` configuration to bypass the synthesis stage when only planning updates are needed.

#### Structured Outputs
- **Pydantic Models**: Expert agents (`MetricsExpert`, `ActivityExpert`, `PhysiologyExpert`) now return strictly typed `Pydantic` models.
- **Targeted Insights**: Expert outputs are split into specific sections for different consumers (`for_synthesis`, `for_season_planner`, `for_weekly_planner`).

### Improved

#### Code Quality & Refactoring
- **Decoupled I/O**: Orchestrator interaction logic separated from core node logic using `InteractionProvider` pattern.
- **Shared Utilities**: Created `output_helper.py` to centralize output extraction and reduce duplication across planner nodes.
- **Prompt Engineering**: Significantly refined system and user prompts for all agents to be more concise, direct, and effective.
- **Error Handling**: Improved error catching and logging in `PlanStorage`.

### Fixed
- **Test Stability**: Resolved issues with test hangs by improving mocking strategies.

---

## [2.0.0] - 2025-11-02

### 🚨 Breaking Changes

#### Agent Architecture Redesign
- Implemented 2-stage analysis pipeline: **Data Summarization → Expert Analysis**
- All analysis nodes renamed (e.g., `metrics_node` → `metrics_expert_node`)
- HITL tool renamed: `ask_human` → `communicate_with_human` with new `message_type` parameter
- New state fields: `metrics_summary`, `physiology_summary`

#### AgentRole Enum Changes
```python
# Old → New
AgentRole.METRICS → AgentRole.METRICS_EXPERT
AgentRole.PHYSIO → AgentRole.PHYSIOLOGY_EXPERT
AgentRole.ACTIVITY_DATA → AgentRole.SUMMARIZER
AgentRole.ACTIVITY_INTERPRETER → AgentRole.ACTIVITY_EXPERT
```

### Added

#### 2-Stage Agent Pipeline
- **Stage 1 (Summarizers)**: 3 parallel nodes organize raw data without interpretation
  - `metrics_summarizer_node`, `physiology_summarizer_node`, `activity_summarizer_node`
  - Run in parallel from START, no tool access for maximum efficiency
- **Stage 2 (Experts)**: 3 parallel nodes interpret structured summaries
  - `metrics_expert_node`, `physiology_expert_node`, `activity_expert_node`
  - Full tool access (plotting + HITL) for deep analysis

#### Generic Summarization Framework
- New `create_data_summarizer_node()` factory for consistent data processing
- Universal summarization prompt: preserves all numeric values, uses tables extensively
- Easy to extend for new data types

#### Enhanced HITL System
- Message types: `question`, `observation`, `suggestion`, `clarification`
- Selective usage guidelines to prevent workflow interruption
- Richer agent-human interaction paradigm

#### New Model Support
- `deepseek-v3.2-exp` with reasoning support
- `gemini-2.5-pro` via OpenRouter
- `grok-4` via OpenRouter
- Updated `claude-4` to latest `claude-sonnet-4-5-20250929`

### Changed

- **Per-role model assignments**: Different models for summarizers, experts, formatters
- **Season planner**: Now context-free, creates strategic plans based only on competition schedule
- **Planning workflow**: Dual-branch architecture with deferred finalize node
- **Documentation**: Updated architecture diagrams and tech stack docs for 2-stage design

### Benefits

- 🎯 **Clarity**: Summarizers organize, experts interpret - clear separation of concerns
- 🚀 **Performance**: Parallel Stage 1 + Parallel Stage 2, no tool overhead in summarizers
- 💰 **Cost Efficiency**: Use cost-effective models for summarization, powerful models for analysis
- 🧪 **Maintainability**: Generic factory pattern, consistent testing boundaries

---

## [1.1.0] - 2025-10-17

### Added

#### Configurable Plot Generation
- **New `enable_plotting` config option** to control AI-generated interactive plots
- Defaults to `false` due to plotting reliability issues with non-state-of-the-art reasoning models
- When enabled, provides visual insights with interactive Plotly charts
- Saves ~30-40% in LLM costs when disabled

**Enable in your config:**
```yaml
extraction:
  enable_plotting: true  # Set to true for visual insights
```

**Why disabled by default?**
Plot generation requires advanced reasoning capabilities. Non-frontier models often struggle with:
- Proper plot reference formatting
- Avoiding duplicate plot IDs
- Complex data visualization logic

For reliable plot generation, use with state-of-the-art models like GPT-5, Claude Opus, or Claude 4.5 Sonnet.

#### Claude 4.5 Sonnet Support
- Added support for Claude 4.5 Sonnet (`claude-sonnet-4-5-20250929`)
- Available as `claude-4-thinking` in model configuration
- Provides extended thinking capabilities with 64K max tokens

### Improved

#### Plot System Enhancements
- Implemented plot deduplication logic to prevent duplicate HTML elements
- Enhanced plot resolution with better error handling and fallback messages
- Conditional plotting instructions - agents only receive plotting tools when enabled
- Improved validation and logging for plot references

#### Code Quality & Refactoring
- Extensive refactoring across all LangGraph nodes (21 files, -146 net lines)
- Improved code readability with better formatting and reduced nesting
- Optimized data structures using comprehensions and modern Python patterns
- Consistent error handling with unified return type annotations
- Streamlined message construction and LLM invocation patterns

#### Model Configuration
- Simplified model selection logic with cleaner configuration mapping
- Streamlined LLM initialization with unified parameter handling
- Better API key mapping for multiple providers

### Fixed
- Whitespace inconsistencies in HTML output
- Duplicate plot references causing broken final reports
- Missing plot metadata edge cases

### Performance
- ~30-40% cost reduction when plotting is disabled
- Faster execution time without plot generation overhead
- Reduced token usage in agent prompts when plotting disabled

---

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

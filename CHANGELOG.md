# Changelog

All notable changes to this project will be documented in this file.

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
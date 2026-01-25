# Technology Stack

## Core Python Framework

- **Python 3.13** - Main programming language
- **Pixi** - Package management and environment handling
- **Pydantic v2** - Data validation and settings management

## AI & LLM Providers

### Supported Models
- **Anthropic Claude** - claude-sonnet-4, claude-opus-4, claude-3-haiku (with extended thinking support)
- **OpenAI** - gpt-5, gpt-5.2-pro, gpt-5-mini, gpt-5-search, gpt-5.2-pro-search (with web search), gpt-4o, o1, o3, o4-mini
- **OpenRouter/DeepSeek** - deepseek-chat, deepseek-r1, deepseek-v3.2-exp (with reasoning support)

### Model Assignment Strategy

The system uses a **role-based model assignment strategy** that optimizes model selection based on task requirements. Specific models can be configured based on the desired mode of operation.

**Key Roles & Capabilities:**

- **Data Summarization Nodes**: Uses models with **extended reasoning capabilities** (e.g., "thinking" models) for complex data structuring and pattern recognition.
  - Metrics, Physiology, and Activity Summarizers
- **HTML Formatters**: Uses **high-speed, efficient models** for clean HTML generation without the overhead of extended reasoning.
  - Analysis and Planning Formatters
- **Expert Nodes**: Uses **advanced reasoning models**, often equipped with **web search capabilities**, to provide deep, grounded analysis.
  - Metrics, Physiology, and Activity Experts
- **Planning Nodes**: Uses **research-capable models** with access to the latest methodologies via web search to generate actionable training plans.
  - Workout and Season Planners
- **Synthesis & Coordination**: Uses **high-fidelity models** to ensure consistent, high-quality final outputs.

**Operation Modes:**
- **STANDARD (Production)**: Balances reasoning depth with performance, utilizing "thinking" models for complex tasks and faster models for formatting.
- **COST_EFFECTIVE**: Prioritizes budget-friendly models (e.g., smaller, faster variants) across all nodes.
- **DEVELOPMENT**: optimized for fast iteration and testing cycles.
- **PRO**: Maximum performance mode using GPT-5.2 Pro with web search for expert nodes (metrics, physiology, activity) and planners (season, weekly), with standard GPT-5.2 for other nodes. ⚠️ **High cost mode** (>$10 per run depending on data volume).

### AI Orchestration & Observability
- **LangGraph 1.0+** - State-based workflow orchestration ✅ **ACTIVE**
- **LangSmith 0.4.37+** - AI observability and cost tracking ✅ **ACTIVE**
- **LangChain 1.0+** - LLM framework and tool integrations
- **LangChain-Anthropic 1.0+** - Anthropic Claude integration
- **LangChain-OpenAI 1.0+** - OpenAI integration
- **LangChain-Community 0.4+** - Community tools and integrations

## Core Dependencies

### Data Processing
- **garminconnect 0.2.30+** - Garmin Connect API client
- **Pandas 2.3.3+** - Data manipulation and analysis
- **NumPy 2.3.4+** - Numerical computing

### Visualization
- **Plotly 6.3.1+** - Interactive charts and visualizations

### Configuration & Environment
- **python-dotenv 1.1.1+** - Environment variable management
- **pydantic-settings 2.0+** - Settings management

## Development & Testing

### Code Quality
- **Ruff 0.14.1+** - Fast Python linter
  - Lint: `pixi run lint-ruff`
  - Auto-fix: `pixi run ruff-fix`
- **Black 25.9.0+** - Code formatter
- **isort 7.0.0+** - Import sorting
- **MyPy 1.18.2+** - Static type checking
  - Type check: `pixi run type-check`

### Testing
- **pytest 8.4.2+** - Testing framework
  - Run tests: `pixi run test`
- **pytest-cov 7.0.0+** - Coverage reporting
  - Coverage: `pixi run test-cov`
- **pytest-asyncio 1.2.0+** - Async test support

### Code Analysis
- **Vulture 2.14+** - Dead code detection
  - Detect: `pixi run dead-code`
- **Flake8 7.3.0+** - Style guide enforcement

## Current Architecture

### Data Flow
```
CLI -> StateGraph Workflow -> Garmin Connect -> AI Nodes -> HTML Reports
      (services/ai/langgraph/ - ACTIVE)
```

### LangGraph Workflow System

**State-based orchestration with typed schemas:**

```python
class TrainingAnalysisState(TypedDict):
    user_id: str
    athlete_name: str
    garmin_data: Dict[str, Any]
    hitl_enabled: bool
    
    metrics_result: Optional[str]
    physiology_result: Optional[str]
    plots: Annotated[List[Dict], lambda x, y: x + y]
```

**Parallel Execution:**
- Metrics + Physiology + Activity summarizers run simultaneously
- Each Summarizer → Expert (sequential dependency for each domain)
- State reducers handle automatic result aggregation

## Key Features

### Human-in-the-Loop (HITL) ✅ **NEW**
- **Mechanism**: LangGraph GraphInterrupt with ask_human_tool
- **Coverage**: All analysis and planning nodes
- **Configuration**: `hitl_enabled: true` (default) or `false` for automation
- **Implementation**: Terminal-based prompts, structured workflow interrupts

### Plotting System
- **Secure Execution**: Sandboxed Python code execution
- **Storage**: Plot metadata and HTML content
- **Reference System**: `[PLOT:plot_id]` for embedding in reports

### Cost Tracking
- **LangSmith Integration**: Automatic token and cost tracking
- **Per-workflow Monitoring**: Detailed cost breakdowns
- **Transparent Reporting**: Cost summaries in output

### Security & Privacy
- **Local Credentials**: Configuration file storage
- **Local Data**: No cloud persistence of personal data
- **Direct API Calls**: Secure LLM provider communication

## Observability

- **LangSmith Dashboards**: Professional workflow monitoring
- **Graph Visualization**: LangGraph Studio debugging
- **Streaming Updates**: Real-time progress tracking
- **Cost Analytics**: Per-agent and per-workflow cost analysis

## CLI Interface

```bash
# Initialize config
pixi run coach-init my_training_config.yaml

# Run analysis
pixi run coach-cli --config my_training_config.yaml
```

## Development Commands

```bash
# Code Quality
pixi run lint-ruff      # Lint with Ruff
pixi run ruff-fix       # Auto-fix issues
pixi run format         # Format with Black + isort
pixi run type-check     # Type check with MyPy

# Testing
pixi run test           # Run test suite
pixi run test-cov       # Run with coverage

# Analysis
pixi run dead-code      # Detect unused code
```

## Package Management

All dependencies managed via Pixi (see [`pixi.toml`](../pixi.toml)):
- Consistent environments across platforms
- Automatic dependency resolution
- Fast installation and caching

## Security Practices

- **Encrypted Storage**: Local credential encryption
- **Secure Communication**: HTTPS for all API calls
- **No Cloud Storage**: Personal data stays local
- **API Key Management**: Environment-based configuration

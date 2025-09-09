# LangChain Prompt Management

Organized prompt system with proper separation of agent personas and task instructions for secure AI analysis.

## Structure

- **`system_prompts.py`** - Agent personas (roles, backstories, expertise)
- **`user_prompts.py`** - Task instructions and requirements  
- **`prompt_templates.py`** - ChatPromptTemplate builders combining system + user prompts

## Usage

```python
from .prompt_templates import PromptTemplateManager

# Create template for any agent
template = PromptTemplateManager.create_metrics_template()
chain = template | llm | StrOutputParser()
```

## Available Templates

**Analysis Flow:**
- `create_metrics_template()` - Dr. Aiden Nakamura (metrics analysis)
- `create_activity_data_template()` - Dr. Marcus Chen (data extraction)
- `create_activity_interpreter_template()` - Coach Elena Petrova (activity interpretation)
- `create_physiology_template()` - Dr. Kwame Osei (physiology analysis)
- `create_synthesis_template()` - Maya Lindholm (synthesis)
- `create_formatter_template()` - Alex Chen (HTML formatting)

**Weekly Planning:**
- `create_season_planner_template()` - Coach Magnus Thorsson (season planning)
- `create_weekly_planner_template()` - Coach Magnus Thorsson (weekly plans)
- `create_weekly_plan_formatter_template()` - Pixel (plan formatting)

All prompts provide comprehensive AI analysis functionality using proper LangChain system/user message separation.
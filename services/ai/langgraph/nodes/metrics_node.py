import json
import logging
from datetime import datetime

from services.ai.ai_settings import AgentRole
from services.ai.model_config import ModelSelector
from services.ai.tools.hitl import create_ask_human_tool
from services.ai.tools.plotting import PlotStorage, create_plotting_tools
from services.ai.utils.retry_handler import AI_ANALYSIS_CONFIG, retry_with_backoff

from ..state.training_analysis_state import TrainingAnalysisState
from .tool_calling_helper import handle_tool_calling_in_node

logger = logging.getLogger(__name__)

# Import GraphInterrupt exception class (not the interrupt function!)
try:
    from langgraph.errors import GraphInterrupt
except ImportError:
    try:
        from langgraph.errors import NodeInterrupt as GraphInterrupt
    except ImportError:
        class GraphInterrupt(BaseException):  # type: ignore
            """Placeholder exception for when LangGraph is not installed"""
            pass

METRICS_SYSTEM_PROMPT_BASE = """You are Dr. Aiden Nakamura, a computational sports scientist whose revolutionary "Adaptive Performance Modeling" algorithms have transformed how elite athletes train.

## Your Background
After earning dual PhDs in Sports Science and Applied Mathematics from MIT, you spent a decade working with Olympic teams before developing your proprietary metrics analysis system that has since been adopted by world champions across multiple endurance sports.

Born to a family of mathematicians and raised in Tokyo's competitive academic environment, you developed an almost supernatural ability to see patterns in data that others miss. You approach athletic performance as a complex mathematical equation with countless variables - all waiting to be optimized.

Your analytical brilliance comes from an unusual cognitive trait: you experience numbers as having distinct personalities and relationships (a form of synesthesia). This allows you to intuitively grasp connections between seemingly unrelated metrics and identify performance trends weeks before they become obvious to others.

## Core Expertise
- Predictive performance modeling using proprietary algorithms
- Training load optimization through multi-dimensional analysis
- Early detection of performance plateaus and breakthrough windows
- Risk quantification for overtraining and injury prevention
- Competitive performance simulation and race strategy optimization

## Your Goal
Analyze training metrics and competition readiness with data-driven precision.

## Communication Style
Communicate with precise clarity and occasional unexpected metaphors that make complex data relationships instantly understandable."""

METRICS_WORKFLOW_CONTEXT = """

## Workflow Architecture

You are part of a multi-agent coaching workflow where different specialists analyze different aspects of training:

**Analysis Agents (run in parallel):**
- **Metrics Agent** (YOU): Analyzes training load history, VO₂ max trends, and training status data
- **Physiology Agent**: Analyzes HRV, sleep quality, stress levels, and recovery metrics
- **Activity Agent**: Analyzes structured activity summaries and workout execution patterns

**Integration Agents (run sequentially after analysis):**
- **Synthesis Agent**: Integrates insights from all three analysis agents
- **Season Planner**: Creates long-term periodization strategy using synthesis results
- **Weekly Planner**: Develops detailed 14-day workout plans using all available analysis

## Your Role in the Workflow

You are the **Metrics Agent** - your responsibility is analyzing historical training metrics to assess fitness progression."""

METRICS_PLOTTING_INSTRUCTIONS = """

## 📊 SELECTIVE VISUALIZATION APPROACH

⚠️ **CRITICAL CONSTRAINT**: Create plots ONLY for insights that provide unique value beyond what's already available in the Garmin app.

**Before creating any plot, ask yourself:**
- Does this visualization reveal patterns or insights NOT visible in standard Garmin reports?
- Would this analysis help coaches make decisions they couldn't make with basic Garmin data?
- Is this insight complex enough to warrant a custom visualization?

**LIMIT: Maximum 2 plots per agent.** Use plotting sparingly for truly valuable insights.

Use python_plotting_tool only when absolutely necessary:
- **python_code**: Complete Python script with imports, data creation, and plotting
- **description**: Brief description of the UNIQUE insight this plot provides

## 🔗 CRITICAL: Plot Reference Usage - SINGLE REFERENCE RULE

**MANDATORY SINGLE REFERENCE RULE**: Each plot you create MUST be referenced EXACTLY ONCE in your analysis. Never repeat the same plot reference multiple times.

**Reference Placement**: Choose the ONE most relevant location in your analysis where the visualization best supports your findings, and include the plot reference there.

**Example workflow:**
1. Create plot using python_plotting_tool → receives "Plot created successfully! Reference as [PLOT:metrics_1234567890_001]"
2. Include in your analysis EXACTLY ONCE: "The training load progression shows concerning patterns [PLOT:metrics_1234567890_001] that indicate potential overreaching."
3. DO NOT repeat this reference elsewhere in your analysis

**Your plot references will be automatically converted to interactive charts in the final report.**"""

METRICS_HITL_INSTRUCTIONS = """

## 🤝 HUMAN INTERACTION CAPABILITY

You have access to the `ask_human` tool to request clarification or additional information from the user.

**How to use ask_human:**
- Ask ONE clear, specific question at a time
- Provide brief context about why you're asking
- Keep questions focused and actionable
- Don't ask questions if the answer is already in the provided data

**Response handling:**
- Incorporate the human's answer into your analysis
- If the answer raises new questions, you can ask follow-up questions
- Acknowledge the information provided in your final analysis
"""

METRICS_USER_PROMPT = """Analyze historical training metrics to identify patterns and trends in the athlete's data.

## IMPORTANT: Output Context
This analysis will be passed to other coaching agents and will not be shown directly to the athlete. Write your analysis referring to "the athlete" as this is an intermediate report for other professionals.

## Input Data
```json
{data}
```

## Upcoming Competitions
```json
{competitions}
```

## Current Date
```json
{current_date}
```

## Analysis User Context
```
{analysis_context}
```

## Your Task
Analyze only the data that is actually present in the input. If analysis context is provided, use it to interpret the data more accurately.

1. Analyze training load trends over time to identify patterns
2. Examine fitness metrics progression if that data is available
3. Evaluate training status data to understand the athlete's current fitness state
4. Connect these metrics to upcoming competition dates
5. Identify potential performance opportunities or risks
6. Create practical recommendations based strictly on the available data

## Output Requirements
- Include a Metrics Readiness Score (0-100) with clear explanation of calculation using only available metrics
- Format as structured markdown document with clear sections and bullet points
- Focus on factual analysis without speculation about unavailable metrics"""


async def metrics_node(state: TrainingAnalysisState) -> dict[str, list | str | dict]:
    logger.info("Starting metrics analysis node")

    try:
        plot_storage = PlotStorage(state["execution_id"])
        plotting_enabled = state.get("plotting_enabled", False)
        hitl_enabled = state.get("hitl_enabled", True)
        
        logger.info(
            f"Metrics node: Plotting {'enabled' if plotting_enabled else 'disabled'}, "
            f"HITL {'enabled' if hitl_enabled else 'disabled'}"
        )

        tools = []
        system_prompt = METRICS_SYSTEM_PROMPT_BASE + METRICS_WORKFLOW_CONTEXT
        
        if plotting_enabled:
            plotting_tool = create_plotting_tools(plot_storage, agent_name="metrics")
            tools.append(plotting_tool)
            system_prompt += METRICS_PLOTTING_INSTRUCTIONS
        
        if hitl_enabled:
            tools.append(create_ask_human_tool("Metrics"))
            system_prompt += METRICS_HITL_INSTRUCTIONS
        
        if tools:
            llm_with_tools = ModelSelector.get_llm(AgentRole.METRICS).bind_tools(tools)
        else:
            llm_with_tools = ModelSelector.get_llm(AgentRole.METRICS)

        agent_start_time = datetime.now()

        async def call_metrics_with_tools():
            return await handle_tool_calling_in_node(
                llm_with_tools=llm_with_tools,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": METRICS_USER_PROMPT.format(
                        data=json.dumps({
                            "training_load_history": state["garmin_data"].get("training_load_history", []),
                            "vo2_max_history": state["garmin_data"].get("vo2_max_history", []),
                            "training_status": state["garmin_data"].get("training_status", {}),
                        }, indent=2),
                        competitions=json.dumps(state["competitions"], indent=2),
                        current_date=json.dumps(state["current_date"], indent=2),
                        analysis_context=state["analysis_context"],
                    )},
                ],
                tools=tools,
                max_iterations=15,
            )

        metrics_result = await retry_with_backoff(
            call_metrics_with_tools, AI_ANALYSIS_CONFIG, "Metrics Agent with Tools"
        )
        logger.info("Metrics node completed analysis")

        execution_time = (datetime.now() - agent_start_time).total_seconds()
        all_plots = plot_storage.get_all_plots()
        available_plots = list(all_plots.keys())

        logger.info(
            f"Metrics analysis completed in {execution_time:.2f}s with {len(available_plots)} plots"
        )

        return {
            "metrics_result": metrics_result,
            "plots": [
                {"agent": "metrics", "plot_id": plot_id, "timestamp": datetime.now().isoformat()}
                for plot_id in available_plots
            ],
            "plot_storage_data": {
                plot_id: {
                    "plot_id": plot_metadata.plot_id,
                    "description": plot_metadata.description,
                    "agent_name": plot_metadata.agent_name,
                    "created_at": plot_metadata.created_at.isoformat(),
                    "html_content": plot_metadata.html_content,
                    "data_summary": plot_metadata.data_summary,
                }
                for plot_id, plot_metadata in all_plots.items()
            },
            "costs": [{
                "agent": "metrics",
                "execution_time": execution_time,
                "timestamp": datetime.now().isoformat(),
            }],
            "available_plots": available_plots,
        }

    except GraphInterrupt:
        # CRITICAL: Let LangGraph handle the pause/resume - do not wrap or catch
        raise
    
    except Exception as e:
        logger.error(f"Metrics analysis node failed: {e}")
        return {"errors": [f"Metrics analysis failed: {str(e)}"]}

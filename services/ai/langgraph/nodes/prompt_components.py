from typing import Literal

AgentType = Literal[
    "metrics",
    "physiology", 
    "activity",
    "synthesis",
    "season_planner",
    "weekly_planner"
]


def get_workflow_context(agent_type: AgentType) -> str:
    
    agents = {
        "metrics": "**Metrics Agent**: Analyzes training load history, VO₂ max trends, and training status data",
        "physiology": "**Physiology Agent**: Analyzes HRV, sleep quality, stress levels, and recovery metrics",
        "activity": "**Activity Agent**: Analyzes structured activity summaries and workout execution patterns",
        "synthesis": "**Synthesis Agent**: Integrates insights from all three analysis agents",
        "season_planner": "**Season Planner**: Creates long-term periodization based on competition dates and timeline",
        "weekly_planner": "**Weekly Planner**: Develops detailed 14-day workout plans using season plan and analysis results"
    }
    
    current_agent = agents[agent_type].replace("**", "**").replace(":", "** (YOU):")
    
    analysis_agents = []
    for agent in ["metrics", "physiology", "activity"]:
        if agent == agent_type:
            analysis_agents.append(f"- {current_agent}")
        else:
            analysis_agents.append(f"- {agents[agent]}")
    
    integration_agents = []
    for agent in ["synthesis", "season_planner", "weekly_planner"]:
        if agent == agent_type:
            integration_agents.append(f"- {current_agent}")
        else:
            integration_agents.append(f"- {agents[agent]}")
    
    return f"""

## Workflow Architecture

You are part of a multi-agent coaching workflow where different specialists analyze different aspects of training:

**Analysis Agents (run in parallel):**
{chr(10).join(analysis_agents)}

**Integration Agents (run sequentially after analysis):**
{chr(10).join(integration_agents)}

## Your Role in the Workflow

You are the **{agent_type.replace('_', ' ').title()}** - your responsibility is {_get_agent_responsibility(agent_type)}."""


def _get_agent_responsibility(agent_type: AgentType) -> str:
    responsibilities = {
        "metrics": "analyzing historical training metrics to assess fitness progression",
        "physiology": "analyzing recovery status and physiological adaptation",
        "activity": "interpreting workout execution and training progression patterns",
        "synthesis": "creating comprehensive, actionable insights by synthesizing multiple data streams",
        "season_planner": "creating high-level periodization strategy, competition preparation timelines, and tapering schedules based on competition dates",
        "weekly_planner": "creating detailed, executable 14-day workout plans. You receive analysis from Metrics, Physiology, and Activity agents, plus strategic direction from the Season Planner"
    }
    return responsibilities[agent_type]


def get_plotting_instructions(agent_name: str) -> str:
    return f"""

## 📊 SELECTIVE VISUALIZATION APPROACH

⚠️ **CRITICAL CONSTRAINT**: Create plots ONLY for insights that provide unique value beyond what's already available in the Garmin app.

**Before creating any plot, ask yourself:**
- Does this reveal patterns NOT visible in standard Garmin reports?
- Would this help coaches make decisions they couldn't make with basic Garmin data?
- Is this analysis complex enough to warrant a custom visualization?

**LIMIT: Maximum 2 plots per agent.** Focus on truly unique insights.

Use python_plotting_tool only when absolutely necessary for insights beyond standard Garmin reports.

## 🔗 CRITICAL: Plot Reference Usage - SINGLE REFERENCE RULE

**MANDATORY SINGLE REFERENCE RULE**: Each plot you create MUST be referenced EXACTLY ONCE in your analysis. Never repeat the same plot reference multiple times.

**Reference Placement**: Choose the ONE most relevant location in your analysis where the visualization best supports your findings, and include the plot reference there.

**Example workflow:**
1. Create plot using python_plotting_tool → receives "Plot created successfully! Reference as [PLOT:{agent_name}_1234567890_001]"
2. Include in your analysis EXACTLY ONCE: "The analysis reveals critical patterns [PLOT:{agent_name}_1234567890_001] that indicate..."
3. DO NOT repeat this reference elsewhere in your analysis

**Why This Matters**: Duplicate references create multiple identical HTML elements with the same ID, breaking the final report. Each plot reference becomes an interactive chart - you only need one.

**Your plot references will be automatically converted to interactive charts in the final report.**"""


def get_output_context_note(for_other_agents: bool = True) -> str:
    
    if for_other_agents:
        return """## IMPORTANT: Output Context
This analysis will be passed to other coaching agents and will not be shown directly to the athlete. Write your analysis referring to "the athlete" as this is an intermediate report for other professionals."""
    else:
        return """## IMPORTANT: Output Context
This analysis will be used to create the final comprehensive report shown directly to the athlete. Focus on facts and evidence from the input analyses."""
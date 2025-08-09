
import logging
from typing import Dict, Any
from datetime import datetime, timedelta

from langchain_core.output_parsers import StrOutputParser

from ..model_config import ModelSelector
from ..ai_settings import AgentRole
from .prompts.prompt_templates import PromptTemplateManager

logger = logging.getLogger(__name__)

class WeeklyPlanChains:
    
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.execution_id = f"{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        logger.info(f"Initialized weekly planning chains for execution {self.execution_id}")
    
    def create_season_planner_chain(self):
        season_planner_prompt = PromptTemplateManager.create_season_planner_template()
        llm = ModelSelector.get_llm(AgentRole.SEASON_PLANNER)
        
        return (
            season_planner_prompt
            | llm
            | StrOutputParser()
        ).with_config({"run_name": f"season_planner_{self.execution_id}"})
    
    def create_weekly_planner_chain(self):
        weekly_planner_prompt = PromptTemplateManager.create_weekly_planner_template()
        llm = ModelSelector.get_llm(AgentRole.WORKOUT)
        
        return (
            weekly_planner_prompt
            | llm
            | StrOutputParser()
        ).with_config({"run_name": f"weekly_planner_{self.execution_id}"})
    
    def create_weekly_plan_formatter_chain(self):
        formatter_prompt = PromptTemplateManager.create_weekly_plan_formatter_template()
        llm = ModelSelector.get_llm(AgentRole.FORMATTER)
        
        return (
            formatter_prompt
            | llm
            | StrOutputParser()
        ).with_config({"run_name": f"weekly_plan_formatter_{self.execution_id}"})
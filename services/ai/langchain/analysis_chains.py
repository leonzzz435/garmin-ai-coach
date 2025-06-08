"""LangChain analysis chains for AI-powered training analysis."""

import logging
from typing import Dict, Any, List
from datetime import datetime

from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableLambda, RunnablePassthrough

from ..model_config import ModelSelector
from ..ai_settings import AgentRole
from .prompts.prompt_templates import PromptTemplateManager

logger = logging.getLogger(__name__)

class AnalysisChains:
    """LangChain implementation of analysis flows with no shared storage."""
    
    def __init__(self, user_id: str):
        """Initialize analysis chains for a specific user execution.
        
        Args:
            user_id: User identifier (for logging/context only, no persistence)
        """
        self.user_id = user_id
        self.execution_id = f"{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        logger.info(f"Initialized analysis chains for execution {self.execution_id}")
    
    def create_metrics_chain(self):
        """Create metrics analysis chain (replaces metrics_agent)."""
        metrics_prompt = PromptTemplateManager.create_metrics_template()
        llm = ModelSelector.get_llm(AgentRole.METRICS)
        
        return (
            metrics_prompt
            | llm
            | StrOutputParser()
        ).with_config({"run_name": f"metrics_analysis_{self.execution_id}"})
    
    def create_activity_data_chain(self):
        """Create activity data extraction chain (replaces activity_data_agent)."""
        activity_data_prompt = PromptTemplateManager.create_activity_data_template()
        llm = ModelSelector.get_llm(AgentRole.ACTIVITY_DATA)
        
        return (
            activity_data_prompt
            | llm
            | StrOutputParser()
        ).with_config({"run_name": f"activity_data_{self.execution_id}"})
    
    def create_activity_interpreter_chain(self):
        """Create activity interpretation chain (replaces activity_interpreter_agent)."""
        activity_interpreter_prompt = PromptTemplateManager.create_activity_interpreter_template()
        llm = ModelSelector.get_llm(AgentRole.ACTIVITY_INTERPRETER)
        
        return (
            activity_interpreter_prompt
            | llm
            | StrOutputParser()
        ).with_config({"run_name": f"activity_interpreter_{self.execution_id}"})
    
    def create_physiology_chain(self):
        """Create physiology analysis chain (replaces physiology_agent)."""
        physiology_prompt = PromptTemplateManager.create_physiology_template()
        llm = ModelSelector.get_llm(AgentRole.PHYSIO)
        
        return (
            physiology_prompt
            | llm
            | StrOutputParser()
        ).with_config({"run_name": f"physiology_{self.execution_id}"})
    
    def create_synthesis_chain(self):
        """Create synthesis chain (replaces synthesis_agent)."""
        synthesis_prompt = PromptTemplateManager.create_synthesis_template()
        llm = ModelSelector.get_llm(AgentRole.SYNTHESIS)
        
        return (
            synthesis_prompt
            | llm
            | StrOutputParser()
        ).with_config({"run_name": f"synthesis_{self.execution_id}"})
    
    def create_formatter_chain(self):
        """Create HTML formatter chain (replaces formatter_agent)."""
        formatter_prompt = PromptTemplateManager.create_formatter_template()
        llm = ModelSelector.get_llm(AgentRole.FORMATTER)
        
        return (
            formatter_prompt
            | llm
            | StrOutputParser()
        ).with_config({"run_name": f"formatter_{self.execution_id}"})
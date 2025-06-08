"""
Prompt template manager for LangChain implementation.
Combines system and user prompts into proper ChatPromptTemplate objects.
"""

from langchain_core.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate
from .system_prompts import SystemPrompts
from .user_prompts import UserPrompts


class PromptTemplateManager:
    """Manages the creation of ChatPromptTemplate objects with proper system/user message separation."""
    
    @staticmethod
    def create_metrics_template() -> ChatPromptTemplate:
        """Create metrics analysis prompt template."""
        system_message = SystemMessagePromptTemplate.from_template(SystemPrompts.METRICS_AGENT)
        user_message = HumanMessagePromptTemplate.from_template(UserPrompts.METRICS_ANALYSIS)
        
        return ChatPromptTemplate.from_messages([
            system_message,
            user_message
        ])
    
    @staticmethod
    def create_activity_data_template() -> ChatPromptTemplate:
        """Create activity data extraction prompt template."""
        system_message = SystemMessagePromptTemplate.from_template(SystemPrompts.ACTIVITY_DATA_AGENT)
        user_message = HumanMessagePromptTemplate.from_template(UserPrompts.ACTIVITY_DATA_EXTRACTION)
        
        return ChatPromptTemplate.from_messages([
            system_message,
            user_message
        ])
    
    @staticmethod
    def create_activity_interpreter_template() -> ChatPromptTemplate:
        """Create activity interpretation prompt template."""
        system_message = SystemMessagePromptTemplate.from_template(SystemPrompts.ACTIVITY_INTERPRETER_AGENT)
        user_message = HumanMessagePromptTemplate.from_template(UserPrompts.ACTIVITY_INTERPRETATION)
        
        return ChatPromptTemplate.from_messages([
            system_message,
            user_message
        ])
    
    @staticmethod
    def create_physiology_template() -> ChatPromptTemplate:
        """Create physiology analysis prompt template."""
        system_message = SystemMessagePromptTemplate.from_template(SystemPrompts.PHYSIOLOGY_AGENT)
        user_message = HumanMessagePromptTemplate.from_template(UserPrompts.PHYSIOLOGY_ANALYSIS)
        
        return ChatPromptTemplate.from_messages([
            system_message,
            user_message
        ])
    
    @staticmethod
    def create_synthesis_template() -> ChatPromptTemplate:
        """Create synthesis prompt template."""
        system_message = SystemMessagePromptTemplate.from_template(SystemPrompts.SYNTHESIS_AGENT)
        user_message = HumanMessagePromptTemplate.from_template(UserPrompts.SYNTHESIS_ANALYSIS)
        
        return ChatPromptTemplate.from_messages([
            system_message,
            user_message
        ])
    
    @staticmethod
    def create_formatter_template() -> ChatPromptTemplate:
        """Create HTML formatter prompt template."""
        system_message = SystemMessagePromptTemplate.from_template(SystemPrompts.FORMATTER_AGENT)
        user_message = HumanMessagePromptTemplate.from_template(UserPrompts.HTML_FORMATTING)
        
        return ChatPromptTemplate.from_messages([
            system_message,
            user_message
        ])
    
    @staticmethod
    def create_season_planner_template() -> ChatPromptTemplate:
        """Create season planning prompt template."""
        system_message = SystemMessagePromptTemplate.from_template(SystemPrompts.SEASON_PLANNER_AGENT)
        user_message = HumanMessagePromptTemplate.from_template(UserPrompts.SEASON_PLANNING)
        
        return ChatPromptTemplate.from_messages([
            system_message,
            user_message
        ])
    
    @staticmethod
    def create_weekly_planner_template() -> ChatPromptTemplate:
        """Create weekly planning prompt template."""
        system_message = SystemMessagePromptTemplate.from_template(SystemPrompts.WEEKLY_PLANNER_AGENT)
        user_message = HumanMessagePromptTemplate.from_template(UserPrompts.WEEKLY_PLANNING)
        
        return ChatPromptTemplate.from_messages([
            system_message,
            user_message
        ])
    
    @staticmethod
    def create_weekly_plan_formatter_template() -> ChatPromptTemplate:
        """Create weekly plan HTML formatter prompt template."""
        system_message = SystemMessagePromptTemplate.from_template(SystemPrompts.WEEKLY_PLAN_FORMATTER_AGENT)
        user_message = HumanMessagePromptTemplate.from_template(UserPrompts.WEEKLY_PLAN_HTML_FORMATTING)
        
        return ChatPromptTemplate.from_messages([
            system_message,
            user_message
        ])


# Convenience functions for backward compatibility
def get_metrics_prompt() -> ChatPromptTemplate:
    """Get metrics analysis prompt template."""
    return PromptTemplateManager.create_metrics_template()


def get_activity_data_prompt() -> ChatPromptTemplate:
    """Get activity data extraction prompt template."""
    return PromptTemplateManager.create_activity_data_template()


def get_activity_interpreter_prompt() -> ChatPromptTemplate:
    """Get activity interpretation prompt template."""
    return PromptTemplateManager.create_activity_interpreter_template()


def get_physiology_prompt() -> ChatPromptTemplate:
    """Get physiology analysis prompt template."""
    return PromptTemplateManager.create_physiology_template()


def get_synthesis_prompt() -> ChatPromptTemplate:
    """Get synthesis prompt template."""
    return PromptTemplateManager.create_synthesis_template()


def get_formatter_prompt() -> ChatPromptTemplate:
    """Get HTML formatter prompt template."""
    return PromptTemplateManager.create_formatter_template()


def get_season_planner_prompt() -> ChatPromptTemplate:
    """Get season planning prompt template."""
    return PromptTemplateManager.create_season_planner_template()


def get_weekly_planner_prompt() -> ChatPromptTemplate:
    """Get weekly planning prompt template."""
    return PromptTemplateManager.create_weekly_planner_template()


def get_weekly_plan_formatter_prompt() -> ChatPromptTemplate:
    """Get weekly plan HTML formatter prompt template."""
    return PromptTemplateManager.create_weekly_plan_formatter_template()
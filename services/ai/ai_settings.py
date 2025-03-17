"""
Centralized AI configuration settings.
"""

from dataclasses import dataclass, field
from typing import Optional, Dict
from enum import Enum
from core.config import get_config, AIMode

class AgentRole(Enum):
    """Different roles for specialized agents."""
    METRICS = "metrics"
    ACTIVITY = "activity"
    PHYSIO = "physio"
    SYNTHESIS = "synthesis"
    WORKOUT = "workout"
    COMPETITION_PLANNER = "competition_planner"
    FORMATTER = "formatter"

@dataclass
class AISettings:
    """Global AI settings configuration."""
    mode: AIMode
    agentops_enabled: bool
    agentops_api_key: Optional[str]
    
    # Model assignments for different roles
    model_assignments: Dict[AIMode, Dict[AgentRole, str]] = field(default_factory=lambda: {
        AIMode.STANDARD: {
            AgentRole.METRICS: "claude-3-7-sonnet",
            AgentRole.ACTIVITY: "claude-3-7-sonnet",
            AgentRole.PHYSIO: "claude-3-7-sonnet", 
            AgentRole.SYNTHESIS: "claude-3-7-sonnet",
            AgentRole.WORKOUT: "claude-3-7-sonnet",
            AgentRole.COMPETITION_PLANNER: "claude-3-7-sonnet",
            AgentRole.FORMATTER: "claude-3-7-sonnet"
        },
        AIMode.COST_EFFECTIVE: {
            AgentRole.METRICS: "claude-3-haiku",
            AgentRole.ACTIVITY: "gpt-4o-mini",
            AgentRole.PHYSIO: "claude-3-haiku", 
            AgentRole.SYNTHESIS: "gpt-4o-mini",
            AgentRole.WORKOUT: "claude-3-haiku",
            AgentRole.COMPETITION_PLANNER: "claude-3-haiku",
            AgentRole.FORMATTER: "claude-3-haiku"
        },
        AIMode.DEVELOPMENT: {
            AgentRole.METRICS: "claude-3-7-sonnet",
            AgentRole.ACTIVITY: "claude-3-7-sonnet",
            AgentRole.PHYSIO: "claude-3-7-sonnet", 
            AgentRole.SYNTHESIS: "claude-3-7-sonnet",
            AgentRole.WORKOUT: "claude-3-7-sonnet",
            AgentRole.COMPETITION_PLANNER: "claude-3-7-sonnet",
            AgentRole.FORMATTER: "claude-3-7-sonnet"
        }
    })

    def get_model_for_role(self, role: AgentRole) -> str:
        """Get the appropriate model name for a given role based on current mode."""
        return self.model_assignments[self.mode][role]

    @classmethod
    def load_settings(cls) -> 'AISettings':
        """Load AI settings from configuration."""
        config = get_config()
        
        return cls(
            mode=config.ai_mode,
            agentops_enabled=config.agentops_enabled,
            agentops_api_key=config.agentops_api_key
        )

# Global settings instance
ai_settings = AISettings.load_settings()

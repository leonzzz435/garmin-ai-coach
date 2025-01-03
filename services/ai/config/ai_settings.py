"""
Centralized AI configuration settings.
"""

from dataclasses import dataclass, field
from typing import Optional, Dict
from enum import Enum
import os
from core.config import get_config, AIMode

class AgentRole(Enum):
    """Different roles for specialized agents."""
    METRICS = "metrics"
    ACTIVITY = "activity"
    PHYSIO = "physio"
    SYNTHESIS = "synthesis"
    WORKOUT = "workout"

@dataclass
class AISettings:
    """Global AI settings configuration."""
    mode: AIMode
    agentops_enabled: bool
    agentops_api_key: Optional[str]
    
    # Model assignments for different roles
    model_assignments: Dict[AIMode, Dict[AgentRole, str]] = field(default_factory=lambda: {
        AIMode.STANDARD: {
            AgentRole.METRICS: "gpt-4o",
            AgentRole.ACTIVITY: "gpt-4o",
            AgentRole.PHYSIO: "gpt-4o",  # Using GPT-4 for reasoning tasks since o1 is not available
            AgentRole.SYNTHESIS: "claude-3-5-sonnet-20241022",
            AgentRole.WORKOUT: "gpt-4o"
        },
        AIMode.COST_EFFECTIVE: {
            AgentRole.METRICS: "gpt-4o-mini",
            AgentRole.ACTIVITY: "gpt-4o-mini",
            AgentRole.PHYSIO: "gpt-4o-mini",  # Using GPT-4 mini for reasoning tasks since o1 is not available
            AgentRole.SYNTHESIS: "claude-3-haiku-20240307",
            AgentRole.WORKOUT: "gpt-4o-mini"
        },
        AIMode.DEVELOPMENT: {
            AgentRole.METRICS: "gpt-4o-mini",
            AgentRole.ACTIVITY: "gpt-4o-mini",
            AgentRole.PHYSIO: "gpt-4o-mini",  # Using GPT-4 mini for reasoning tasks since o1 is not available
            AgentRole.SYNTHESIS: "claude-3-haiku-20240307",
            AgentRole.WORKOUT: "gpt-4o-mini"
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

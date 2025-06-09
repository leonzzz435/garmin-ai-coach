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
    ACTIVITY_DATA = "activity_data"           # Data extraction agent
    ACTIVITY_INTERPRETER = "activity_interpreter"  # Interpretation agent
    PHYSIO = "physio"
    SYNTHESIS = "synthesis"
    WORKOUT = "workout"
    COMPETITION_PLANNER = "competition_planner"
    SEASON_PLANNER = "season_planner"         # Long-term seasonal planning
    FORMATTER = "formatter"

@dataclass
class AISettings:
    """Global AI settings configuration."""
    mode: AIMode
    agentops_enabled: bool
    agentops_api_key: Optional[str]
    
    # Model assignments - one model per stage for all agents
    stage_models: Dict[AIMode, str] = field(default_factory=lambda: {
        AIMode.STANDARD: "claude-4-thinking",      # Production: Best performance with reasoning
        AIMode.COST_EFFECTIVE: "claude-3-haiku",   # Budget: Fast and cost-effective
        AIMode.DEVELOPMENT: "claude-3-haiku"       # Development: Fast iteration
    })
    
    # Derived model assignments for compatibility
    model_assignments: Dict[AIMode, Dict[AgentRole, str]] = field(default_factory=lambda: {})
    
    def __post_init__(self):
        """Initialize model assignments from stage models."""
        for mode, model in self.stage_models.items():
            self.model_assignments[mode] = {
                role: model for role in AgentRole
            }

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

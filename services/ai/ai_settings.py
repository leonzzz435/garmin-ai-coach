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
    
    # Model assignments for different roles
    model_assignments: Dict[AIMode, Dict[AgentRole, str]] = field(default_factory=lambda: {
        AIMode.STANDARD: {
            # Data processing roles benefit from thinking mode
            AgentRole.METRICS: "claude-4-thinking",              # Data-intensive pattern analysis
            AgentRole.ACTIVITY_DATA: "claude-4-thinking",        # Raw data extraction and structuring
            AgentRole.PHYSIO: "claude-4-thinking",               # Complex physiological pattern analysis
            AgentRole.ACTIVITY_INTERPRETER: "claude-4-thinking", # precise interpretation of activity data
            
            # Creative roles work better with standard mode
            AgentRole.SYNTHESIS: "claude-4-thinking",            # Creative synthesis of multiple analyses
            AgentRole.WORKOUT: "claude-4-thinking",              # Domain-specific workout planning
            AgentRole.COMPETITION_PLANNER: "claude-4-thinking",  # Creative race strategy development
            AgentRole.SEASON_PLANNER: "claude-4-thinking",       # High-level season planning
            
            # Code generation role
            AgentRole.FORMATTER: "claude-4-thinking"            # HTML/CSS code generation
        },
        AIMode.COST_EFFECTIVE: {
            AgentRole.METRICS: "claude-3-haiku",
            AgentRole.ACTIVITY_DATA: "claude-3-haiku",
            AgentRole.ACTIVITY_INTERPRETER: "gpt-4o-mini",
            AgentRole.PHYSIO: "claude-3-haiku",
            AgentRole.SYNTHESIS: "gpt-4o-mini",
            AgentRole.WORKOUT: "gpt-4o-mini",
            AgentRole.COMPETITION_PLANNER: "claude-3-haiku",
            AgentRole.SEASON_PLANNER: "claude-3-haiku",
            AgentRole.FORMATTER: "claude-3-haiku"
        },
        AIMode.DEVELOPMENT: {
            # Data processing roles benefit from thinking mode
            AgentRole.METRICS: "claude-3-7-thinking",           # Data-intensive pattern analysis
            AgentRole.ACTIVITY_DATA: "claude-3-7-thinking",     # Raw data extraction and structuring
            AgentRole.PHYSIO: "claude-3-7-thinking",            # Complex physiological pattern analysis
            
            # Creative roles work better with standard mode
            AgentRole.ACTIVITY_INTERPRETER: "claude-3-7-thinking", # Creative interpretation of activity data
            AgentRole.SYNTHESIS: "claude-3-7-thinking",           # Creative synthesis of multiple analyses
            AgentRole.WORKOUT: "claude-3-7-thinking",             # Domain-specific workout planning
            AgentRole.COMPETITION_PLANNER: "claude-3-7-thinking", # Creative race strategy development
            AgentRole.SEASON_PLANNER: "claude-3-7-thinking",      # High-level season planning
            
            # Code generation role
            AgentRole.FORMATTER: "claude-3-7-thinking"            # HTML/CSS code generation
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

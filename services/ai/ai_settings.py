from dataclasses import dataclass, field
from enum import Enum

from core.config import AIMode, get_config


class AgentRole(Enum):
    METRICS = "metrics"
    ACTIVITY_DATA = "activity_data"  # Data extraction agent
    ACTIVITY_INTERPRETER = "activity_interpreter"  # Interpretation agent
    PHYSIO = "physio"
    SYNTHESIS = "synthesis"
    WORKOUT = "workout"
    COMPETITION_PLANNER = "competition_planner"
    SEASON_PLANNER = "season_planner"  # Long-term seasonal planning
    FORMATTER = "formatter"


@dataclass
class AISettings:
    mode: AIMode

    # Model assignments - one model per stage for all agents
    stage_models: dict[AIMode, str] = field(
        default_factory=lambda: {
            AIMode.STANDARD: "gpt-5",  # Production: Top-tier reasoning with GPT-5
            AIMode.COST_EFFECTIVE: "claude-3-haiku",  # Budget: Fast and cost-effective
            AIMode.DEVELOPMENT: "claude-4",  # Development: Fast iteration
        }
    )

    # Derived model assignments for compatibility
    model_assignments: dict[AIMode, dict[AgentRole, str]] = field(default_factory=lambda: {})

    def __post_init__(self):
        for mode, model in self.stage_models.items():
            self.model_assignments[mode] = {role: model for role in AgentRole}

    def get_model_for_role(self, role: AgentRole) -> str:
        return self.model_assignments[self.mode][role]

    @classmethod
    def load_settings(cls) -> "AISettings":
        return cls(mode=get_config().ai_mode)


# Global settings instance
ai_settings = AISettings.load_settings()

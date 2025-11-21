from dataclasses import dataclass, field
from enum import Enum

from core.config import AIMode, get_config


class AgentRole(Enum):
    SUMMARIZER = "summarizer"
    METRICS_EXPERT = "metrics_expert"
    PHYSIOLOGY_EXPERT = "physiology_expert"
    ACTIVITY_EXPERT = "activity_expert"
    SYNTHESIS = "synthesis"
    WORKOUT = "workout"
    SEASON_PLANNER = "season_planner"
    FORMATTER = "formatter"


@dataclass
class AISettings:
    mode: AIMode

    model_assignments: dict[AIMode, dict[AgentRole, str]] = field(
        default_factory=lambda: {
            AIMode.STANDARD: {
                AgentRole.SUMMARIZER: "claude-4-thinking",
                AgentRole.FORMATTER: "claude-4-thinking",
                AgentRole.METRICS_EXPERT: "claude-4-thinking",
                AgentRole.PHYSIOLOGY_EXPERT: "claude-4-thinking",
                AgentRole.ACTIVITY_EXPERT: "claude-4-thinking",
                AgentRole.SYNTHESIS: "claude-4-thinking",
                AgentRole.WORKOUT: "claude-4-thinking",
                AgentRole.SEASON_PLANNER: "claude-4-thinking",
            },
            AIMode.COST_EFFECTIVE: {
                AgentRole.SUMMARIZER: "claude-3-haiku",
                AgentRole.FORMATTER: "claude-3-haiku",
                AgentRole.METRICS_EXPERT: "claude-3-haiku",
                AgentRole.PHYSIOLOGY_EXPERT: "claude-3-haiku",
                AgentRole.ACTIVITY_EXPERT: "claude-3-haiku",
                AgentRole.SYNTHESIS: "claude-3-haiku",
                AgentRole.WORKOUT: "claude-3-haiku",
                AgentRole.SEASON_PLANNER: "claude-3-haiku",
            },
            AIMode.DEVELOPMENT: {
                AgentRole.SUMMARIZER: "claude-4",
                AgentRole.FORMATTER: "claude-4",
                AgentRole.METRICS_EXPERT: "claude-4",
                AgentRole.PHYSIOLOGY_EXPERT: "claude-4",
                AgentRole.ACTIVITY_EXPERT: "claude-4",
                AgentRole.SYNTHESIS: "claude-4",
                AgentRole.WORKOUT: "claude-4",
                AgentRole.SEASON_PLANNER: "claude-4",
            },
        }
    )

    def get_model_for_role(self, role: AgentRole) -> str:
        return self.model_assignments[self.mode][role]

    @classmethod
    def load_settings(cls) -> "AISettings":
        return cls(mode=get_config().ai_mode)

    def reload(self) -> None:
        """Reloads settings from current config."""
        self.mode = get_config().ai_mode


# Global settings instance
ai_settings = AISettings.load_settings()

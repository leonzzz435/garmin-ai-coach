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

    # Per-role model assignments for each AI mode
    # Data summarization uses Claude (with thinking), formatters use Claude (no thinking), experts use GPT-5
    model_assignments: dict[AIMode, dict[AgentRole, str]] = field(
        default_factory=lambda: {
            AIMode.STANDARD: {
                # Data summarization - Claude with thinking for complex data structuring
                AgentRole.ACTIVITY_DATA: "claude-4-thinking",
                # Formatters - Claude without thinking for clean HTML generation
                AgentRole.FORMATTER: "claude-4",
                # Experts - GPT-5 high for advanced reasoning
                AgentRole.METRICS: "gpt-5",
                AgentRole.PHYSIO: "gpt-5",
                # Other roles - GPT-5 for consistency
                AgentRole.ACTIVITY_INTERPRETER: "gpt-5",
                AgentRole.SYNTHESIS: "gpt-5",
                AgentRole.WORKOUT: "gpt-5",
                AgentRole.COMPETITION_PLANNER: "gpt-5",
                AgentRole.SEASON_PLANNER: "gpt-5",
            },
            AIMode.COST_EFFECTIVE: {
                # Budget mode - all use Haiku
                AgentRole.ACTIVITY_DATA: "claude-3-haiku",
                AgentRole.FORMATTER: "claude-3-haiku",
                AgentRole.METRICS: "claude-3-haiku",
                AgentRole.PHYSIO: "claude-3-haiku",
                AgentRole.ACTIVITY_INTERPRETER: "claude-3-haiku",
                AgentRole.SYNTHESIS: "claude-3-haiku",
                AgentRole.WORKOUT: "claude-3-haiku",
                AgentRole.COMPETITION_PLANNER: "claude-3-haiku",
                AgentRole.SEASON_PLANNER: "claude-3-haiku",
            },
            AIMode.DEVELOPMENT: {
                # Development mode - fast Claude 4 for all
                AgentRole.ACTIVITY_DATA: "claude-4",
                AgentRole.FORMATTER: "claude-4",
                AgentRole.METRICS: "claude-4",
                AgentRole.PHYSIO: "claude-4",
                AgentRole.ACTIVITY_INTERPRETER: "claude-4",
                AgentRole.SYNTHESIS: "claude-4",
                AgentRole.WORKOUT: "claude-4",
                AgentRole.COMPETITION_PLANNER: "claude-4",
                AgentRole.SEASON_PLANNER: "claude-4",
            },
        }
    )

    def get_model_for_role(self, role: AgentRole) -> str:
        return self.model_assignments[self.mode][role]

    @classmethod
    def load_settings(cls) -> "AISettings":
        return cls(mode=get_config().ai_mode)


# Global settings instance
ai_settings = AISettings.load_settings()

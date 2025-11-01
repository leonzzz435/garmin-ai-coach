from dataclasses import dataclass, field
from enum import Enum

from core.config import AIMode, get_config


class AgentRole(Enum):
    METRICS = "metrics"
    ACTIVITY_SUMMARIZER = "activity_summarizer"  # Data extraction/summarization agent
    ACTIVITY_EXPERT = "activity_expert"  # Expert interpretation agent
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
                AgentRole.ACTIVITY_SUMMARIZER: "claude-4-thinking",
                # Formatters - Claude without thinking for clean HTML generation
                AgentRole.FORMATTER: "claude-4-thinking",
                # Experts - GPT-5 high for advanced reasoning
                AgentRole.METRICS: "claude-4-thinking",
                AgentRole.PHYSIO: "claude-4-thinking",
                # Other roles - GPT-5 for consistency
                AgentRole.ACTIVITY_EXPERT: "claude-4-thinking",
                AgentRole.SYNTHESIS: "claude-4-thinking",
                AgentRole.WORKOUT: "claude-4-thinking",
                AgentRole.COMPETITION_PLANNER: "claude-4-thinking",
                AgentRole.SEASON_PLANNER: "claude-4-thinking",
            },
            AIMode.COST_EFFECTIVE: {
                # Budget mode - all use Haiku
                AgentRole.ACTIVITY_SUMMARIZER: "claude-3-haiku",
                AgentRole.FORMATTER: "claude-3-haiku",
                AgentRole.METRICS: "claude-3-haiku",
                AgentRole.PHYSIO: "claude-3-haiku",
                AgentRole.ACTIVITY_EXPERT: "claude-3-haiku",
                AgentRole.SYNTHESIS: "claude-3-haiku",
                AgentRole.WORKOUT: "claude-3-haiku",
                AgentRole.COMPETITION_PLANNER: "claude-3-haiku",
                AgentRole.SEASON_PLANNER: "claude-3-haiku",
            },
            AIMode.DEVELOPMENT: {
                # Development mode - fast Claude 4 for all
                AgentRole.ACTIVITY_SUMMARIZER: "claude-4",
                AgentRole.FORMATTER: "claude-4",
                AgentRole.METRICS: "claude-4",
                AgentRole.PHYSIO: "claude-4",
                AgentRole.ACTIVITY_EXPERT: "claude-4",
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

from services.ai.ai_settings import AgentRole

from ..state.training_analysis_state import TrainingAnalysisState
from .data_summarizer_node import create_data_summarizer_node


def extract_metrics_data(state: TrainingAnalysisState) -> dict:
    return {
        "training_load_history": state["garmin_data"].get("training_load_history", []),
        "vo2_max_history": state["garmin_data"].get("vo2_max_history", {}),
        "training_status": state["garmin_data"].get("training_status", {}),
    }


metrics_summarizer_node = create_data_summarizer_node(
    node_name="Metrics Summarizer",
    agent_role=AgentRole.SUMMARIZER,
    data_extractor=extract_metrics_data,
    state_output_key="metrics_summary",
)

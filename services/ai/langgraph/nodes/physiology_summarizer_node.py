from services.ai.ai_settings import AgentRole

from ..state.training_analysis_state import TrainingAnalysisState
from .data_summarizer_node import create_data_summarizer_node


def extract_physiology_data(state: TrainingAnalysisState) -> dict:
    garmin_data = state["garmin_data"]
    recovery_indicators = garmin_data.get("recovery_indicators", [])
    physiological_markers = garmin_data.get("physiological_markers", {})
    
    return {
        "hrv_data": physiological_markers.get("hrv", {}),
        "sleep_data": [ind["sleep"] for ind in recovery_indicators if ind.get("sleep")],
        "stress_data": [ind["stress"] for ind in recovery_indicators if ind.get("stress")],
        "recovery_metrics": {
            "physiological_markers": physiological_markers,
            "body_metrics": garmin_data.get("body_metrics", {}),
            "recovery_indicators": recovery_indicators,
        },
    }


physiology_summarizer_node = create_data_summarizer_node(
    node_name="Physiology Summarizer",
    agent_role=AgentRole.SUMMARIZER,
    data_extractor=extract_physiology_data,
    state_output_key="physiology_summary",
)

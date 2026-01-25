import logging
from datetime import datetime
from typing import Any

from services.ai.langgraph.state.training_analysis_state import TrainingAnalysisState

logger = logging.getLogger(__name__)


async def data_integration_node(state: TrainingAnalysisState) -> dict[str, Any]:
    logger.info("Starting data integration node")

    try:
        agent_start_time = datetime.now()

        available_data_names = [
            name
            for name, key in [
                ("metrics analysis", "metrics_outputs"),
                ("activity analysis", "activity_outputs"),
                ("physiology analysis", "physiology_outputs"),
            ]
            if state.get(key)
        ]
        available_data_str = ", ".join(available_data_names) if available_data_names else "none"
        logger.info("Data integration: Available analysis data: %s", available_data_str)

        execution_time = (datetime.now() - agent_start_time).total_seconds()
        logger.info("Data integration completed in %.2fs", execution_time)

        return {
            "season_plan_complete": True,
            "costs": [
                {
                    "agent": "data_integration",
                    "execution_time": execution_time,
                    "timestamp": datetime.now().isoformat(),
                }
            ],
        }

    except Exception as exc:
        logger.exception("Data integration node failed")
        return {"errors": [f"Data integration failed: {exc!s}"]}

import logging
from datetime import datetime

from ..state.training_analysis_state import TrainingAnalysisState

logger = logging.getLogger(__name__)


async def data_integration_node(state: TrainingAnalysisState) -> dict[str, list]:

    logger.info("Starting data integration node")

    try:
        agent_start_time = datetime.now()

        data_available = [
            name for name, key in [
                ("metrics analysis", "metrics_result"),
                ("activity analysis", "activity_result"),
                ("physiology analysis", "physiology_result")
            ] if state.get(key, "")
        ]

        logger.info(
            f"Data integration: Available analysis data: {', '.join(data_available) if data_available else 'none'}"
        )

        execution_time = (datetime.now() - agent_start_time).total_seconds()
        logger.info(f"Data integration completed in {execution_time:.2f}s")

        return {
            "season_plan_complete": True,  # Mark season planning complete for orchestrator
            "costs": [{
                "agent": "data_integration",
                "execution_time": execution_time,
                "timestamp": datetime.now().isoformat(),
            }],
        }

    except Exception as e:
        logger.error(f"Data integration node failed: {e}")
        return {"errors": [f"Data integration failed: {str(e)}"]}

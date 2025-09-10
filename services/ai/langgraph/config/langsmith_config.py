import logging
import os

logger = logging.getLogger(__name__)


class LangSmithConfig:

    @staticmethod
    def setup_langsmith(
        project_name: str = "tele_garmin_analysis", api_key: str | None = None
    ) -> bool:
        try:
            if api_key:
                os.environ["LANGSMITH_API_KEY"] = api_key

            if not os.getenv("LANGSMITH_API_KEY"):
                logger.warning("LANGSMITH_API_KEY not set - observability disabled")
                return False

            os.environ["LANGSMITH_PROJECT"] = project_name
            os.environ["LANGSMITH_TRACING"] = "true"

            logger.info(f"LangSmith observability enabled for project: {project_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to setup LangSmith: {e}")
            return False

    @staticmethod
    def get_project_name(user_id: str, analysis_type: str = "training_analysis") -> str:
        return f"tele_garmin_{analysis_type}_{str(user_id)}"

    @staticmethod
    def disable_langsmith():
        os.environ["LANGSMITH_TRACING"] = "false"
        logger.info("LangSmith observability disabled")


def configure_langsmith_for_user(user_id: str, analysis_type: str = "training_analysis") -> bool:
    project_name = LangSmithConfig.get_project_name(user_id, analysis_type)
    return LangSmithConfig.setup_langsmith(project_name)

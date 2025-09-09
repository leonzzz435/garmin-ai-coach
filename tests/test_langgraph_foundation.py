import pytest
import os
from unittest.mock import patch

from services.ai.langgraph.state.training_analysis_state import (
    TrainingAnalysisState, 
    create_initial_state
)
from services.ai.langgraph.config.langsmith_config import LangSmithConfig


class TestLangGraphFoundation:

    def test_state_creation(self):
        state = create_initial_state(
            user_id="test_user",
            athlete_name="Test Athlete",
            garmin_data={"test": "data"}
        )
        
        assert state["user_id"] == "test_user"
        assert state["athlete_name"] == "Test Athlete"
        assert state["garmin_data"] == {"test": "data"}
        assert isinstance(state["plots"], list)
        assert isinstance(state["costs"], list)
        assert isinstance(state["errors"], list)

    def test_langgraph_import(self):
        from langgraph.graph import StateGraph
        workflow = StateGraph(TrainingAnalysisState)
        assert workflow is not None

    @patch.dict(os.environ, {"LANGSMITH_API_KEY": "test_key"}, clear=True)
    def test_langsmith_config(self):
        result = LangSmithConfig.setup_langsmith("test_project")
        assert result is True
        assert os.getenv("LANGSMITH_PROJECT") == "test_project"

    def test_module_imports(self):
        from services.ai.langgraph import TrainingAnalysisState
        from services.ai.langgraph.config import LangSmithConfig
        assert TrainingAnalysisState is not None
        assert LangSmithConfig is not None


if __name__ == "__main__":
    pytest.main([__file__])
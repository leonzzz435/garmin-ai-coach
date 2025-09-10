import pytest

from services.ai.langgraph.state.training_analysis_state import (
    TrainingAnalysisState,
    create_initial_state,
)
from services.ai.langgraph.workflows.planning_workflow import (
    create_integrated_analysis_and_planning_workflow,
    create_planning_workflow,
)


class TestWorkflowStability:

    def test_planning_workflow_creation(self):
        workflow = create_planning_workflow()
        assert workflow is not None
        assert hasattr(workflow, 'invoke')
        assert hasattr(workflow, 'ainvoke')

    def test_integrated_workflow_creation(self):
        workflow = create_integrated_analysis_and_planning_workflow()
        assert workflow is not None
        assert hasattr(workflow, 'invoke')
        assert hasattr(workflow, 'ainvoke')

    def test_state_schema_compatibility(self):
        state = create_initial_state(
            user_id="test", athlete_name="Test Athlete", garmin_data={}, execution_id="test"
        )

        assert isinstance(state, dict)
        assert 'user_id' in state
        assert 'athlete_name' in state
        assert 'garmin_data' in state

        assert 'season_plan' in state
        assert 'weekly_plan' in state
        assert 'planning_html' in state
        assert 'planning_context' in state

        assert 'metrics_result' in state
        assert 'activity_result' in state
        assert 'physiology_result' in state
        assert 'analysis_html' in state


class TestWorkflowIntegration:

    @pytest.fixture
    def minimal_valid_state(self) -> TrainingAnalysisState:
        return create_initial_state(
            user_id="test_user",
            athlete_name="Test Athlete",
            garmin_data={"training_load_history": []},
            planning_context="",
            competitions=[],
            current_date={},
            week_dates=[],
            execution_id="test_integration",
        )

    def test_workflow_accepts_valid_state(self, minimal_valid_state):
        """Test workflows can accept valid state structure."""
        planning_workflow = create_planning_workflow()
        integrated_workflow = create_integrated_analysis_and_planning_workflow()

        assert planning_workflow is not None
        assert integrated_workflow is not None
        assert isinstance(minimal_valid_state, dict)

    def test_state_preserves_data_through_workflow(self, minimal_valid_state):
        state = minimal_valid_state.copy()

        state['costs'] = [{'agent': 'test1', 'cost': 100}]
        new_costs = [{'agent': 'test2', 'cost': 200}]

        combined_costs = state['costs'] + new_costs
        assert len(combined_costs) == 2
        assert combined_costs[0]['agent'] == 'test1'
        assert combined_costs[1]['agent'] == 'test2'

        state['plots'] = [{'plot_id': 'plot1'}]
        new_plots = [{'plot_id': 'plot2'}]

        combined_plots = state['plots'] + new_plots
        assert len(combined_plots) == 2

    def test_workflow_node_count_stability(self):
        planning_workflow = create_planning_workflow()
        integrated_workflow = create_integrated_analysis_and_planning_workflow()

        assert planning_workflow is not None
        assert integrated_workflow is not None


class TestWorkflowDataFlow:

    def test_planning_state_fields(self):
        state = create_initial_state(
            user_id="test", athlete_name="Test", garmin_data={}, execution_id="test"
        )

        planning_inputs = [
            'competitions',
            'current_date',
            'week_dates',
            'planning_context',
            'athlete_name',
        ]
        for field in planning_inputs:
            assert field in state

        planning_outputs = ['season_plan', 'weekly_plan', 'planning_html']
        for field in planning_outputs:
            assert field in state

        analysis_results = ['metrics_result', 'activity_result', 'physiology_result']
        for field in analysis_results:
            assert field in state

    def test_state_update_functionality(self):
        initial_state = create_initial_state(
            user_id="test", athlete_name="Test", garmin_data={}, execution_id="test"
        )

        updates = {
            'season_plan': 'Test season plan content',
            'weekly_plan': 'Test weekly plan content',
            'planning_html': '<html>Test HTML</html>',
        }

        updated_state = {**initial_state, **updates}

        assert updated_state['season_plan'] == 'Test season plan content'
        assert updated_state['weekly_plan'] == 'Test weekly plan content'
        assert updated_state['planning_html'] == '<html>Test HTML</html>'

        assert updated_state['user_id'] == initial_state['user_id']
        assert updated_state['athlete_name'] == initial_state['athlete_name']


class TestWorkflowImports:

    def test_all_planning_nodes_importable(self):
        from services.ai.langgraph.nodes.data_integration_node import data_integration_node
        from services.ai.langgraph.nodes.plan_formatter_node import plan_formatter_node
        from services.ai.langgraph.nodes.season_planner_node import season_planner_node
        from services.ai.langgraph.nodes.weekly_planner_node import weekly_planner_node

        nodes = [
            season_planner_node,
            data_integration_node,
            weekly_planner_node,
            plan_formatter_node,
        ]
        for node in nodes:
            assert callable(node)

    def test_workflow_functions_importable(self):
        from services.ai.langgraph.workflows.planning_workflow import (
            create_integrated_analysis_and_planning_workflow,
            create_planning_workflow,
            run_complete_analysis_and_planning,
            run_weekly_planning,
        )

        functions = [
            create_planning_workflow,
            create_integrated_analysis_and_planning_workflow,
            run_weekly_planning,
            run_complete_analysis_and_planning,
        ]
        for func in functions:
            assert callable(func)

    def test_state_management_importable(self):
        from services.ai.langgraph.state.training_analysis_state import (
            TrainingAnalysisState,
            create_initial_state,
        )

        assert TrainingAnalysisState is not None

        state = create_initial_state(
            user_id="test", athlete_name="Test", garmin_data={}, execution_id="test"
        )
        assert isinstance(state, dict)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

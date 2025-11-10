from unittest.mock import AsyncMock, MagicMock, Mock

import pytest
from langgraph.types import Command
from pydantic import ValidationError

from services.ai.langgraph.workflows.interactive_runner import (
    InterruptHandler,
    run_workflow_with_hitl,
)
from services.ai.tools.hitl import CommunicateWithHumanInput, create_communicate_with_human_tool


class MockInterrupt:
    def __init__(self, interrupt_id: str, value: dict):
        self.id = interrupt_id
        self.value = value


class MockTask:
    def __init__(self, task_id: str, interrupts: list[MockInterrupt] | None = None):
        self.id = task_id
        self.interrupts = interrupts or []


class MockSnapshot:
    def __init__(self, next_nodes: list[str] | None = None, tasks: list[MockTask] | None = None):
        self.next = next_nodes or []
        self.tasks = tasks or []


def create_mock_workflow_app(scenario: str = "no_interrupts", **kwargs):
    mock_app = AsyncMock()
    
    if scenario == "no_interrupts":
        final_state = kwargs.get("final_state", {"result": "success", "analysis": "Complete"})
        
        async def astream_gen(state, config, stream_mode):
            yield final_state
        
        mock_app.astream = Mock(side_effect=astream_gen)
        mock_app.get_state = Mock(return_value=MockSnapshot(next_nodes=[]))
        
    elif scenario == "single_interrupt":
        interrupt_data = kwargs.get("interrupt_data", {
            "message": "What is your goal?",
            "message_type": "question",
            "agent": "TestAgent"
        })
        interrupt_id = kwargs.get("interrupt_id", "int_1")
        interrupt_data["id"] = interrupt_id
        final_state = kwargs.get("final_state", {"result": "success", "analysis": "Complete"})
        
        call_count = [0]
        
        async def astream_gen(state, config, stream_mode):
            if call_count[0] == 0:
                yield {"partial": "state"}
            else:
                yield final_state
            call_count[0] += 1
        
        def get_state_side_effect(config):
            if call_count[0] == 1:
                return MockSnapshot(
                    next_nodes=["continue"],
                    tasks=[MockTask("task_1", [MockInterrupt(interrupt_id, interrupt_data)])]
                )
            return MockSnapshot(next_nodes=[])
        
        mock_app.astream = Mock(side_effect=astream_gen)
        mock_app.get_state = Mock(side_effect=get_state_side_effect)
        
    elif scenario == "multiple_interrupts":
        interrupts = kwargs.get("interrupts", [
            {"id": "int_1", "data": {"message": "Question 1?", "message_type": "question", "agent": "Agent1"}},
            {"id": "int_2", "data": {"message": "Question 2?", "message_type": "question", "agent": "Agent2"}}
        ])
        final_state = kwargs.get("final_state", {"result": "success"})
        
        call_count = [0]
        resolved_interrupts = []
        
        async def astream_gen(state, config, stream_mode):
            if call_count[0] < len(interrupts):
                yield {"partial": "state"}
            else:
                yield final_state
            call_count[0] += 1
        
        def get_state_side_effect(config):
            remaining_count = len(interrupts) - len(resolved_interrupts)
            if remaining_count > 0:
                mock_interrupts = []
                for i in interrupts:
                    if i["id"] not in resolved_interrupts:
                        data = i["data"].copy()
                        data["id"] = i["id"]
                        mock_interrupts.append(MockInterrupt(i["id"], data))
                        resolved_interrupts.append(i["id"])
                        break
                if mock_interrupts:
                    return MockSnapshot(
                        next_nodes=["continue"],
                        tasks=[MockTask("task_1", mock_interrupts)]
                    )
            return MockSnapshot(next_nodes=[])
        
        mock_app.astream = Mock(side_effect=astream_gen)
        mock_app.get_state = Mock(side_effect=get_state_side_effect)
    
    return mock_app


class TestCommunicateWithHumanTool:

    def test_create_communicate_with_human_tool_default_agent_name(self):
        tool = create_communicate_with_human_tool()
        assert tool.name == "communicate_with_human"
        assert "communicate" in tool.description.lower()

    def test_create_communicate_with_human_tool_custom_agent_name(self):
        tool = create_communicate_with_human_tool(agent_name="MetricsAnalyzer")
        assert tool.name == "communicate_with_human"

    def test_communicate_with_human_input_schema_required_fields(self):
        valid_input = CommunicateWithHumanInput(
            message="What is your target heart rate?",
            message_type="question"
        )
        assert valid_input.message == "What is your target heart rate?"
        assert valid_input.message_type == "question"
        assert valid_input.context == ""

    def test_communicate_with_human_input_schema_with_context(self):
        input_with_context = CommunicateWithHumanInput(
            message="What is your target heart rate?",
            message_type="question",
            context="Analyzing your recent training data"
        )
        assert input_with_context.message == "What is your target heart rate?"
        assert input_with_context.message_type == "question"
        assert input_with_context.context == "Analyzing your recent training data"

    def test_communicate_with_human_input_schema_missing_required_fields_raises_error(self):
        with pytest.raises(ValidationError):
            CommunicateWithHumanInput(message="test message")  # Missing message_type


class TestInterruptHandler:

    def test_extract_all_interrupts_empty_result(self):
        result = {}
        interrupts = InterruptHandler.extract_all_interrupts(result)
        assert interrupts == []

    def test_extract_all_interrupts_single_dict_interrupt(self):
        result = {
            "__interrupt__": [{
                "id": "int_1",
                "value": {
                    "type": "communicate_with_human",
                    "message": "Test question?",
                    "context": "Test context",
                    "agent": "TestAgent"
                }
            }]
        }
        interrupts = InterruptHandler.extract_all_interrupts(result)
        assert len(interrupts) == 1
        assert interrupts[0][0] == "int_1"
        assert interrupts[0][1]["value"]["type"] == "communicate_with_human"
        assert interrupts[0][1]["value"]["message"] == "Test question?"

    def test_extract_all_interrupts_multiple_interrupts(self):
        result = {
            "__interrupt__": [
                {
                    "id": "int_1",
                    "value": {"question": "Question 1?", "agent": "Agent1"}
                },
                {
                    "id": "int_2",
                    "value": {"question": "Question 2?", "agent": "Agent2"}
                }
            ]
        }
        interrupts = InterruptHandler.extract_all_interrupts(result)
        assert len(interrupts) == 2
        assert interrupts[0][0] == "int_1"
        assert interrupts[1][0] == "int_2"

    def test_extract_all_interrupts_object_with_attributes(self):
        mock_interrupt = MagicMock()
        mock_interrupt.interrupt_id = "int_obj_1"
        mock_interrupt.value = {"message": "Object question?", "message_type": "question", "agent": "ObjAgent"}
        
        result = {"__interrupt__": [mock_interrupt]}
        interrupts = InterruptHandler.extract_all_interrupts(result)
        
        assert len(interrupts) == 1
        assert interrupts[0][0] == "int_obj_1"
        assert interrupts[0][1]["message"] == "Object question?"

    def test_extract_all_interrupts_with_id_fallback(self):
        mock_interrupt = MagicMock()
        mock_interrupt.interrupt_id = None
        mock_interrupt.id = "fallback_id"
        mock_interrupt.value = {"message": "Fallback question?", "message_type": "question"}
        
        result = {"__interrupt__": [mock_interrupt]}
        interrupts = InterruptHandler.extract_all_interrupts(result)
        
        assert len(interrupts) == 1
        assert interrupts[0][0] == "fallback_id"

    def test_format_question_basic(self):
        formatted = InterruptHandler.format_question({
            "message": "What is your training goal?",
            "message_type": "question",
            "agent": "PlannerAgent"
        })
        
        assert "AGENT COMMUNICATION" in formatted
        assert "[PLANNERAGENT]" in formatted
        assert "What is your training goal?" in formatted

    def test_format_question_with_context(self):
        formatted = InterruptHandler.format_question({
            "message": "What is your target race?",
            "message_type": "question",
            "context": "Planning your season based on your fitness level",
            "agent": "SeasonPlanner"
        })
        
        assert "[SEASONPLANNER]" in formatted
        assert "Planning your season" in formatted
        assert "What is your target race?" in formatted

    def test_format_question_with_index(self):
        formatted = InterruptHandler.format_question({
            "message": "Question text?",
            "message_type": "question",
            "agent": "Agent1"
        }, index=2)
        
        assert "Question 2" in formatted
        assert "AGENT COMMUNICATION" not in formatted

    def test_format_question_no_agent_label(self):
        formatted = InterruptHandler.format_question({
            "message": "Generic question?",
            "message_type": "question",
            "agent": ""
        })
        
        assert "AGENT COMMUNICATION" in formatted
        assert "Generic question?" in formatted

    def test_format_question_missing_message_field(self):
        formatted = InterruptHandler.format_question({"agent": "TestAgent"})
        
        assert "Message not found" in formatted
    
    def test_format_question_with_message_type(self):
        formatted = InterruptHandler.format_question({
            "message": "I think we should add more recovery",
            "message_type": "suggestion",
            "agent": "MetricsAgent"
        })
        
        assert "[SUGGESTION]" in formatted
        assert "I think we should add more recovery" in formatted


class TestRunWorkflowWithHITL:

    @pytest.mark.asyncio
    async def test_workflow_completes_without_interrupts(self):
        mock_app = create_mock_workflow_app(
            scenario="no_interrupts",
            final_state={"result": "success", "analysis": "Complete"}
        )
        
        result = await run_workflow_with_hitl(
            workflow_app=mock_app,
            initial_state={"user_input": "test"},
            config={"configurable": {"thread_id": "test_thread"}},
            prompt_callback=lambda question: pytest.fail("Should not prompt user when no interrupts")
        )
        
        assert result["result"] == "success"
        assert "cancelled" not in result
        mock_app.astream.assert_called_once()

    @pytest.mark.asyncio
    async def test_workflow_with_single_interrupt(self):
        mock_app = create_mock_workflow_app(
            scenario="single_interrupt",
            interrupt_data={
                "message": "What is your goal?",
                "message_type": "question",
                "agent": "TestAgent"
            },
            interrupt_id="int_1",
            final_state={"result": "success", "analysis": "Complete"}
        )
        
        result = await run_workflow_with_hitl(
            workflow_app=mock_app,
            initial_state={"user_input": "test"},
            config={"configurable": {"thread_id": "test_thread"}},
            prompt_callback=lambda question: "Marathon under 3 hours"
        )
        
        assert result["result"] == "success"
        assert mock_app.astream.call_count == 2
        second_call_args = mock_app.astream.call_args_list[1][0][0]
        assert isinstance(second_call_args, Command)
        assert "int_1" in second_call_args.resume

    @pytest.mark.asyncio
    async def test_workflow_with_multiple_concurrent_interrupts(self):
        mock_app = create_mock_workflow_app(
            scenario="multiple_interrupts",
            interrupts=[
                {"id": "int_1", "data": {"message": "Question 1?", "message_type": "question", "agent": "Agent1"}},
                {"id": "int_2", "data": {"message": "Question 2?", "message_type": "question", "agent": "Agent2"}}
            ],
            final_state={"result": "success"}
        )
        
        initial_state = {"user_input": "test"}
        config = {"configurable": {"thread_id": "test_thread"}}
        
        user_responses = ["Answer 1", "Answer 2"]
        response_index = [0]
        
        def mock_prompt(question):
            response = user_responses[response_index[0]]
            response_index[0] += 1
            return response
        
        progress_messages = []
        def mock_progress(message):
            progress_messages.append(message)
        
        result = await run_workflow_with_hitl(
            workflow_app=mock_app,
            initial_state=initial_state,
            config=config,
            prompt_callback=mock_prompt,
            progress_callback=mock_progress
        )
        
        assert result["result"] == "success"
        assert mock_app.astream.call_count == 3

    @pytest.mark.asyncio
    async def test_workflow_user_cancels_with_quit(self):
        mock_app = create_mock_workflow_app(
            scenario="single_interrupt",
            interrupt_data={"message": "Continue?", "message_type": "question", "agent": "TestAgent"},
            interrupt_id="int_1"
        )
        
        initial_state = {"user_input": "test"}
        config = {"configurable": {"thread_id": "test_thread"}}
        
        def mock_prompt(question):
            return "quit"
        
        result = await run_workflow_with_hitl(
            workflow_app=mock_app,
            initial_state=initial_state,
            config=config,
            prompt_callback=mock_prompt
        )
        
        assert result.get("cancelled") is True
        assert mock_app.astream.call_count == 1

    @pytest.mark.asyncio
    async def test_workflow_user_cancels_with_exit(self):
        mock_app = create_mock_workflow_app(
            scenario="single_interrupt",
            interrupt_data={"message": "Continue?", "message_type": "question", "agent": "TestAgent"},
            interrupt_id="int_1"
        )
        
        def mock_prompt(question):
            return "EXIT"
        
        result = await run_workflow_with_hitl(
            workflow_app=mock_app,
            initial_state={},
            config={},
            prompt_callback=mock_prompt
        )
        
        assert result.get("cancelled") is True

    @pytest.mark.asyncio
    async def test_workflow_user_cancels_during_multiple_questions(self):
        mock_app = create_mock_workflow_app(
            scenario="multiple_interrupts",
            interrupts=[
                {"id": "int_1", "data": {"message": "Q1?", "message_type": "question", "agent": "A1"}},
                {"id": "int_2", "data": {"message": "Q2?", "message_type": "question", "agent": "A2"}}
            ]
        )
        
        responses = ["First answer", "cancel"]
        response_index = [0]
        
        def mock_prompt(question):
            response = responses[response_index[0]]
            response_index[0] += 1
            return response
        
        result = await run_workflow_with_hitl(
            workflow_app=mock_app,
            initial_state={},
            config={},
            prompt_callback=mock_prompt,
            progress_callback=lambda x: None
        )
        
        assert result.get("cancelled") is True

    @pytest.mark.asyncio
    async def test_workflow_handles_keyboard_interrupt(self):
        mock_app = AsyncMock()
        
        async def astream_gen(state, config, stream_mode):
            raise KeyboardInterrupt()
            yield  # pragma: no cover
        
        mock_app.astream = Mock(side_effect=astream_gen)
        
        with pytest.raises(KeyboardInterrupt):
            await run_workflow_with_hitl(
                workflow_app=mock_app,
                initial_state={},
                config={},
                prompt_callback=lambda q: "test"
            )

    @pytest.mark.asyncio
    async def test_workflow_handles_generic_exception(self):
        mock_app = AsyncMock()
        
        async def astream_gen(state, config, stream_mode):
            raise ValueError("Test error")
            yield  # pragma: no cover
        
        mock_app.astream = Mock(side_effect=astream_gen)
        
        with pytest.raises(ValueError, match="Test error"):
            await run_workflow_with_hitl(
                workflow_app=mock_app,
                initial_state={},
                config={},
                prompt_callback=lambda q: "test"
            )

    @pytest.mark.asyncio
    async def test_workflow_with_progress_callback(self):
        mock_app = create_mock_workflow_app(
            scenario="no_interrupts",
            final_state={"result": "success"}
        )
        
        progress_messages = []
        
        def mock_progress(message):
            progress_messages.append(message)
        
        await run_workflow_with_hitl(
            workflow_app=mock_app,
            initial_state={},
            config={},
            prompt_callback=lambda q: "test",
            progress_callback=mock_progress
        )
        
        assert any("completed" in msg.lower() for msg in progress_messages)

    @pytest.mark.asyncio
    async def test_workflow_resume_command_structure(self):
        mock_app = create_mock_workflow_app(
            scenario="single_interrupt",
            interrupt_data={"message": "Test?", "message_type": "question", "agent": "TestAgent"},
            interrupt_id="test_interrupt_id",
            final_state={"result": "success"}
        )
        
        await run_workflow_with_hitl(
            workflow_app=mock_app,
            initial_state={},
            config={},
            prompt_callback=lambda q: "user answer"
        )
        
        second_call_state = mock_app.astream.call_args_list[1][0][0]
        assert isinstance(second_call_state, Command)
        assert "test_interrupt_id" in second_call_state.resume
        assert second_call_state.resume["test_interrupt_id"]["content"] == "user answer"
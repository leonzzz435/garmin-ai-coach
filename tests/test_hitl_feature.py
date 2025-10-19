from unittest.mock import AsyncMock, MagicMock

import pytest
from langgraph.types import Command
from pydantic import ValidationError

from services.ai.langgraph.workflows.interactive_runner import (
    InterruptHandler,
    run_workflow_with_hitl,
)
from services.ai.tools.hitl import AskHumanInput, create_ask_human_tool


class TestAskHumanTool:

    def test_create_ask_human_tool_default_agent_name(self):
        tool = create_ask_human_tool()
        assert tool.name == "ask_human"
        assert "ask the human" in tool.description.lower()

    def test_create_ask_human_tool_custom_agent_name(self):
        tool = create_ask_human_tool(agent_name="MetricsAnalyzer")
        assert tool.name == "ask_human"

    def test_ask_human_input_schema_required_fields(self):
        valid_input = AskHumanInput(question="What is your target heart rate?")
        assert valid_input.question == "What is your target heart rate?"
        assert valid_input.context == ""

    def test_ask_human_input_schema_with_context(self):
        input_with_context = AskHumanInput(
            question="What is your target heart rate?",
            context="Analyzing your recent training data"
        )
        assert input_with_context.question == "What is your target heart rate?"
        assert input_with_context.context == "Analyzing your recent training data"

    def test_ask_human_input_schema_missing_question_raises_error(self):
        with pytest.raises(ValidationError):
            AskHumanInput()


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
                    "type": "ask_human",
                    "question": "Test question?",
                    "context": "Test context",
                    "agent": "TestAgent"
                }
            }]
        }
        interrupts = InterruptHandler.extract_all_interrupts(result)
        assert len(interrupts) == 1
        assert interrupts[0][0] == "int_1"
        assert interrupts[0][1]["value"]["type"] == "ask_human"
        assert interrupts[0][1]["value"]["question"] == "Test question?"

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
        mock_interrupt.value = {"question": "Object question?", "agent": "ObjAgent"}
        
        result = {"__interrupt__": [mock_interrupt]}
        interrupts = InterruptHandler.extract_all_interrupts(result)
        
        assert len(interrupts) == 1
        assert interrupts[0][0] == "int_obj_1"
        assert interrupts[0][1]["question"] == "Object question?"

    def test_extract_all_interrupts_with_id_fallback(self):
        mock_interrupt = MagicMock()
        mock_interrupt.interrupt_id = None
        mock_interrupt.id = "fallback_id"
        mock_interrupt.value = {"question": "Fallback question?"}
        
        result = {"__interrupt__": [mock_interrupt]}
        interrupts = InterruptHandler.extract_all_interrupts(result)
        
        assert len(interrupts) == 1
        assert interrupts[0][0] == "fallback_id"

    def test_format_question_basic(self):
        payload = {
            "question": "What is your training goal?",
            "agent": "PlannerAgent"
        }
        formatted = InterruptHandler.format_question(payload)
        
        assert "AGENT QUESTION" in formatted
        assert "[PLANNERAGENT]" in formatted
        assert "What is your training goal?" in formatted

    def test_format_question_with_context(self):
        payload = {
            "question": "What is your target race?",
            "context": "Planning your season based on your fitness level",
            "agent": "SeasonPlanner"
        }
        formatted = InterruptHandler.format_question(payload)
        
        assert "[SEASONPLANNER]" in formatted
        assert "Planning your season" in formatted
        assert "What is your target race?" in formatted

    def test_format_question_with_index(self):
        payload = {
            "question": "Question text?",
            "agent": "Agent1"
        }
        formatted = InterruptHandler.format_question(payload, index=2)
        
        assert "Question 2" in formatted
        assert "AGENT QUESTION" not in formatted

    def test_format_question_no_agent_label(self):
        payload = {"question": "Generic question?", "agent": ""}
        formatted = InterruptHandler.format_question(payload)
        
        assert "AGENT QUESTION" in formatted
        assert "Generic question?" in formatted

    def test_format_question_missing_question_field(self):
        payload = {"agent": "TestAgent"}
        formatted = InterruptHandler.format_question(payload)
        
        assert "Question not found" in formatted


class TestRunWorkflowWithHITL:

    @pytest.mark.asyncio
    async def test_workflow_completes_without_interrupts(self):
        mock_app = AsyncMock()
        mock_app.ainvoke.return_value = {
            "result": "success",
            "analysis": "Complete"
        }
        
        initial_state = {"user_input": "test"}
        config = {"configurable": {"thread_id": "test_thread"}}
        
        def mock_prompt(question):
            pytest.fail("Should not prompt user when no interrupts")
        
        result = await run_workflow_with_hitl(
            workflow_app=mock_app,
            initial_state=initial_state,
            config=config,
            prompt_callback=mock_prompt
        )
        
        assert result["result"] == "success"
        assert "cancelled" not in result

    @pytest.mark.asyncio
    async def test_workflow_with_single_interrupt(self):
        mock_app = AsyncMock()
        
        mock_app.ainvoke.side_effect = [
            {
                "__interrupt__": [{
                    "id": "int_1",
                    "value": {
                        "question": "What is your goal?",
                        "agent": "TestAgent"
                    }
                }]
            },
            {"result": "success", "analysis": "Complete"}
        ]
        
        initial_state = {"user_input": "test"}
        config = {"configurable": {"thread_id": "test_thread"}}
        
        user_responses = ["Marathon under 3 hours"]
        response_index = [0]
        
        def mock_prompt(question):
            response = user_responses[response_index[0]]
            response_index[0] += 1
            return response
        
        result = await run_workflow_with_hitl(
            workflow_app=mock_app,
            initial_state=initial_state,
            config=config,
            prompt_callback=mock_prompt
        )
        
        assert result["result"] == "success"
        assert mock_app.ainvoke.call_count == 2
        
        second_call_args = mock_app.ainvoke.call_args_list[1][0]
        assert isinstance(second_call_args[0], Command)

    @pytest.mark.asyncio
    async def test_workflow_with_multiple_concurrent_interrupts(self):
        mock_app = AsyncMock()
        
        mock_app.ainvoke.side_effect = [
            {
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
            },
            {"result": "success"}
        ]
        
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
        assert mock_app.ainvoke.call_count == 2
        
        assert any("2 AGENT QUESTIONS" in msg for msg in progress_messages)

    @pytest.mark.asyncio
    async def test_workflow_user_cancels_with_quit(self):
        mock_app = AsyncMock()
        
        mock_app.ainvoke.return_value = {
            "__interrupt__": [{
                "id": "int_1",
                "value": {"question": "Continue?", "agent": "TestAgent"}
            }]
        }
        
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
        assert mock_app.ainvoke.call_count == 1

    @pytest.mark.asyncio
    async def test_workflow_user_cancels_with_exit(self):
        mock_app = AsyncMock()
        
        mock_app.ainvoke.return_value = {
            "__interrupt__": [{
                "id": "int_1",
                "value": {"question": "Continue?", "agent": "TestAgent"}
            }]
        }
        
        def mock_prompt(question):
            return "EXIT"  # Test case-insensitive
        
        result = await run_workflow_with_hitl(
            workflow_app=mock_app,
            initial_state={},
            config={},
            prompt_callback=mock_prompt
        )
        
        assert result.get("cancelled") is True

    @pytest.mark.asyncio
    async def test_workflow_user_cancels_during_multiple_questions(self):
        mock_app = AsyncMock()
        
        mock_app.ainvoke.return_value = {
            "__interrupt__": [
                {"id": "int_1", "value": {"question": "Q1?", "agent": "A1"}},
                {"id": "int_2", "value": {"question": "Q2?", "agent": "A2"}}
            ]
        }
        
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
        mock_app.ainvoke.side_effect = KeyboardInterrupt()
        
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
        mock_app.ainvoke.side_effect = ValueError("Test error")
        
        with pytest.raises(ValueError, match="Test error"):
            await run_workflow_with_hitl(
                workflow_app=mock_app,
                initial_state={},
                config={},
                prompt_callback=lambda q: "test"
            )

    @pytest.mark.asyncio
    async def test_workflow_with_progress_callback(self):
        mock_app = AsyncMock()
        mock_app.ainvoke.return_value = {"result": "success"}
        
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
        mock_app = AsyncMock()
        
        mock_app.ainvoke.side_effect = [
            {
                "__interrupt__": [{
                    "id": "test_interrupt_id",
                    "value": {"question": "Test?", "agent": "TestAgent"}
                }]
            },
            {"result": "success"}
        ]
        
        await run_workflow_with_hitl(
            workflow_app=mock_app,
            initial_state={},
            config={},
            prompt_callback=lambda q: "user answer"
        )
        
        second_call_state = mock_app.ainvoke.call_args_list[1][0][0]
        assert isinstance(second_call_state, Command)
        assert "test_interrupt_id" in second_call_state.resume
        assert second_call_state.resume["test_interrupt_id"]["content"] == "user answer"
from unittest.mock import AsyncMock, MagicMock

import pytest
from langgraph.types import Command
from pydantic import ValidationError

from services.ai.langgraph.workflows.interactive_runner import (
    InterruptHandler,
    run_workflow_with_hitl,
)
from services.ai.tools.hitl import CommunicateWithHumanInput, create_communicate_with_human_tool


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
        mock_app = AsyncMock()
        mock_app.ainvoke.return_value = {
            "result": "success",
            "analysis": "Complete"
        }
        
        result = await run_workflow_with_hitl(
            workflow_app=mock_app,
            initial_state={"user_input": "test"},
            config={"configurable": {"thread_id": "test_thread"}},
            prompt_callback=lambda question: pytest.fail("Should not prompt user when no interrupts")
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
                        "message": "What is your goal?",
                        "message_type": "question",
                        "agent": "TestAgent"
                    }
                }]
            },
            {"result": "success", "analysis": "Complete"}
        ]
        
        result = await run_workflow_with_hitl(
            workflow_app=mock_app,
            initial_state={"user_input": "test"},
            config={"configurable": {"thread_id": "test_thread"}},
            prompt_callback=lambda question: "Marathon under 3 hours"
        )
        
        assert result["result"] == "success"
        assert mock_app.ainvoke.call_count == 2
        assert isinstance(mock_app.ainvoke.call_args_list[1][0][0], Command)

    @pytest.mark.asyncio
    async def test_workflow_with_multiple_concurrent_interrupts(self):
        mock_app = AsyncMock()
        
        mock_app.ainvoke.side_effect = [
            {
                "__interrupt__": [
                    {
                        "id": "int_1",
                        "value": {"message": "Question 1?", "message_type": "question", "agent": "Agent1"}
                    },
                    {
                        "id": "int_2",
                        "value": {"message": "Question 2?", "message_type": "question", "agent": "Agent2"}
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
        assert any("2 AGENT QUESTIONS" in message for message in progress_messages)

    @pytest.mark.asyncio
    async def test_workflow_user_cancels_with_quit(self):
        mock_app = AsyncMock()
        
        mock_app.ainvoke.return_value = {
            "__interrupt__": [{
                "id": "int_1",
                "value": {"message": "Continue?", "message_type": "question", "agent": "TestAgent"}
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
                "value": {"message": "Continue?", "message_type": "question", "agent": "TestAgent"}
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
                {"id": "int_1", "value": {"message": "Q1?", "message_type": "question", "agent": "A1"}},
                {"id": "int_2", "value": {"message": "Q2?", "message_type": "question", "agent": "A2"}}
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
                    "value": {"message": "Test?", "message_type": "question", "agent": "TestAgent"}
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
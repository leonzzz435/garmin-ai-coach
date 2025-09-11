import tempfile
from unittest.mock import AsyncMock, Mock, patch

import pytest
from telegram.constants import ParseMode
from telegram.ext import ConversationHandler

from bot.handlers.coach_handlers import (
    EXPECTING_ANALYSIS_CONTEXT,
    EXPECTING_PLANNING_CONTEXT,
    cancel_coach,
    process_analysis_context,
    process_planning_context,
    start_coach,
    user_data,
)


class TestCoachHandlersCharacterization:
    
    @pytest.fixture
    def mock_update(self):
        update = Mock()
        update.effective_user.id = 12345
        update.effective_user.full_name = "Test User"
        update.effective_chat.id = 67890
        update.message = Mock()
        return update
    
    @pytest.fixture
    def mock_context(self):
        context = Mock()
        return context
    
    @patch('bot.handlers.coach_handlers.SecureCredentialManager')
    @patch('bot.handlers.coach_handlers.ExecutionTracker')
    @pytest.mark.asyncio
    async def test_start_coach_no_credentials_returns_end(self, mock_tracker, mock_cred_manager, mock_update, mock_context):
        mock_cred_instance = Mock()
        mock_cred_instance.has_stored_credentials.return_value = False
        mock_cred_manager.return_value = mock_cred_instance
        
        mock_update.message.reply_text = AsyncMock()
        
        result = await start_coach(mock_update, mock_context)
        
        assert result == ConversationHandler.END
        mock_update.message.reply_text.assert_called_once()
        call_args = mock_update.message.reply_text.call_args
        assert "No stored credentials" in call_args[0][0]
        assert call_args[1]['parse_mode'] == ParseMode.MARKDOWN_V2
    
    @patch('bot.handlers.coach_handlers.SecureCredentialManager')
    @patch('bot.handlers.coach_handlers.ExecutionTracker')
    @pytest.mark.asyncio
    async def test_start_coach_daily_limit_reached_returns_end(self, mock_tracker, mock_cred_manager, mock_update, mock_context):
        mock_cred_instance = Mock()
        mock_cred_instance.has_stored_credentials.return_value = True
        mock_cred_manager.return_value = mock_cred_instance
        
        mock_tracker_instance = Mock()
        mock_tracker_instance.check_insights_limit.return_value = False
        mock_tracker.return_value = mock_tracker_instance
        
        mock_update.message.reply_text = AsyncMock()
        
        result = await start_coach(mock_update, mock_context)
        
        assert result == ConversationHandler.END
        mock_update.message.reply_text.assert_called_once()
        call_args = mock_update.message.reply_text.call_args
        assert "Daily insight limit reached" in call_args[0][0]
    
    @patch('bot.handlers.coach_handlers.SecureCredentialManager')
    @patch('bot.handlers.coach_handlers.ExecutionTracker')
    @pytest.mark.asyncio
    async def test_start_coach_success_initializes_user_data(self, mock_tracker, mock_cred_manager, mock_update, mock_context):
        mock_cred_instance = Mock()
        mock_cred_instance.has_stored_credentials.return_value = True
        mock_cred_manager.return_value = mock_cred_instance
        
        mock_tracker_instance = Mock()
        mock_tracker_instance.check_insights_limit.return_value = True
        mock_tracker.return_value = mock_tracker_instance
        
        mock_update.message.reply_text = AsyncMock()
        
        result = await start_coach(mock_update, mock_context)
        
        assert result == EXPECTING_ANALYSIS_CONTEXT
        assert mock_update.effective_user.id in user_data
        assert user_data[mock_update.effective_user.id] == {"analysis_context": "", "planning_context": ""}
        mock_update.message.reply_text.assert_called_once()
        call_args = mock_update.message.reply_text.call_args
        assert "Data Analysis Context" in call_args[0][0]
    
    @pytest.mark.asyncio
    async def test_process_analysis_context_skip_command(self, mock_update, mock_context):
        mock_update.message.text = "/skip"
        mock_update.message.reply_text = AsyncMock()
        user_data[mock_update.effective_user.id] = {"analysis_context": "", "planning_context": ""}
        
        result = await process_analysis_context(mock_update, mock_context)
        
        assert result == EXPECTING_PLANNING_CONTEXT
        assert user_data[mock_update.effective_user.id]["analysis_context"] == ""
        mock_update.message.reply_text.assert_called_once()
        call_args = mock_update.message.reply_text.call_args
        assert "Weekly Planning Context" in call_args[0][0]
    
    @pytest.mark.asyncio
    async def test_process_analysis_context_stores_user_input(self, mock_update, mock_context):
        mock_update.message.text = "I'm feeling tired this week"
        mock_update.message.reply_text = AsyncMock()
        user_data[mock_update.effective_user.id] = {"analysis_context": "", "planning_context": ""}
        
        result = await process_analysis_context(mock_update, mock_context)
        
        assert result == EXPECTING_PLANNING_CONTEXT
        assert user_data[mock_update.effective_user.id]["analysis_context"] == "I'm feeling tired this week"
    
    @pytest.mark.asyncio
    async def test_cancel_coach_cleans_up_user_data(self, mock_update, mock_context):
        mock_update.message.reply_text = AsyncMock()
        user_data[mock_update.effective_user.id] = {"analysis_context": "test", "planning_context": "test"}
        
        result = await cancel_coach(mock_update, mock_context)
        
        assert result == ConversationHandler.END
        assert mock_update.effective_user.id not in user_data
        mock_update.message.reply_text.assert_called_once()
        call_args = mock_update.message.reply_text.call_args
        assert "cancelled" in call_args[0][0]


class TestProcessPlanningContextCharacterization:
    
    @pytest.fixture
    def mock_update(self):
        update = Mock()
        update.effective_user.id = 12345
        update.effective_user.full_name = "Test User"
        update.effective_chat.id = 67890
        update.message = Mock()
        update.message.text = "No special planning needs"
        return update
    
    @pytest.fixture
    def mock_context(self):
        return Mock()
    
    @patch('bot.handlers.coach_handlers.AICoachDetailedProgressManager')
    @patch('bot.handlers.coach_handlers.SecureCredentialManager')
    @patch('bot.handlers.coach_handlers.SecureReportManager')
    @patch('bot.handlers.coach_handlers.SecureMetricsCache')
    @patch('bot.handlers.coach_handlers.SecureActivityCache')
    @patch('bot.handlers.coach_handlers.SecurePhysiologyCache')
    @patch('bot.handlers.coach_handlers.TriathlonCoachDataExtractor')
    @patch('bot.handlers.coach_handlers.SecureCompetitionManager')
    @patch('bot.handlers.coach_handlers.run_complete_analysis_and_planning')
    @patch('bot.handlers.coach_handlers.ExecutionTracker')
    @patch('bot.handlers.coach_handlers.FileDeliveryManager')
    @pytest.mark.asyncio
    async def test_process_planning_context_complete_workflow(self, mock_file_delivery, mock_execution_tracker, 
                                                            mock_run_analysis, mock_competition_manager,
                                                            mock_extractor, mock_physiology_cache, 
                                                            mock_activity_cache, mock_metrics_cache,
                                                            mock_report_manager, mock_cred_manager,
                                                            mock_progress_manager, mock_update, mock_context):
        
        mock_cred_instance = Mock()
        mock_cred_instance.get_credentials.return_value = ("test@example.com", "password")
        mock_cred_manager.return_value = mock_cred_instance
        
        from dataclasses import dataclass
        
        @dataclass
        class MockGarminData:
            activities: list = None
            metrics: list = None
            
        mock_extractor_instance = Mock()
        mock_extractor_instance.extract_data.return_value = MockGarminData()
        mock_extractor.return_value = mock_extractor_instance
        
        mock_comp_instance = Mock()
        mock_comp_instance.get_upcoming_competitions.return_value = []
        mock_competition_manager.return_value = mock_comp_instance
        
        mock_run_analysis.return_value = {
            'cost_summary': {'total_cost_usd': 0.25, 'total_tokens': 1000},
            'plots': [],
            'analysis_html': '<html>Analysis Result</html>',
            'planning_html': '<html>Planning Result</html>',
            'metrics_result': 'Metrics analysis content',
            'activity_result': 'Activity analysis content',
            'physiology_result': 'Physiology analysis content',
            'season_plan': 'Season planning content'
        }
        
        mock_file_delivery_instance = Mock()
        mock_file_delivery_instance.get_file_sequence.return_value = [
            {
                'type': 'summary',
                'content': 'Analysis complete!',
                'parse_mode': ParseMode.MARKDOWN_V2
            }
        ]
        mock_file_delivery.return_value = mock_file_delivery_instance
        
        mock_progress_instance = Mock()
        mock_progress_instance.start_coach_analysis = AsyncMock()
        mock_progress_instance.analysis_complete_detailed = AsyncMock()
        mock_progress_instance.analysis_stats = {}
        mock_progress_manager.return_value = mock_progress_instance
        
        for mock_cache in [mock_metrics_cache, mock_activity_cache, mock_physiology_cache]:
            cache_instance = Mock()
            cache_instance.clear = Mock()
            cache_instance.store = Mock()
            mock_cache.return_value = cache_instance
        
        mock_report_instance = Mock()
        mock_report_instance.clear_report = Mock()
        mock_report_instance.store_report = Mock()
        mock_report_manager.return_value = mock_report_instance
        
        mock_tracker_instance = Mock()
        mock_tracker_instance.reset_workout_counter = Mock()
        mock_execution_tracker.return_value = mock_tracker_instance
        
        mock_update.message.reply_text = AsyncMock()
        
        user_data[mock_update.effective_user.id] = {
            "analysis_context": "Feeling tired",
            "planning_context": "No special needs"
        }
        
        result = await process_planning_context(mock_update, mock_context)
        
        assert result == ConversationHandler.END
        
        assert mock_update.effective_user.id not in user_data
        
        mock_run_analysis.assert_called_once()
        
        for mock_cache in [mock_metrics_cache, mock_activity_cache, mock_physiology_cache]:
            cache_instance = mock_cache.return_value
            cache_instance.clear.assert_called_once()
        
        mock_report_instance.store_report.assert_called_once()
        
        mock_tracker_instance.reset_workout_counter.assert_called_once()


class TestFileDeliveryCharacterization:
    
    @pytest.mark.asyncio
    async def test_file_delivery_html_handling(self):
        mock_update = Mock()
        mock_update.message.reply_document = AsyncMock()
        
        html_content = '<html><body>Test Report</body></html>'
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as tmp:
            tmp.write(html_content)
            tmp.flush()
            tmp_name = tmp.name
            
        try:
            with open(tmp_name, 'rb') as doc:
                await mock_update.message.reply_document(
                    document=doc,
                    filename='analysis_report.html',
                    caption='📊 Analysis Report',
                    parse_mode=ParseMode.MARKDOWN_V2
                )
        finally:
            import os
            if os.path.exists(tmp_name):
                os.unlink(tmp_name)
        
        mock_update.message.reply_document.assert_called_once()


class TestErrorHandlingCharacterization:
    
    @patch('bot.handlers.coach_handlers.AICoachDetailedProgressManager')
    @patch('bot.handlers.coach_handlers.SecureCredentialManager')
    @patch('bot.handlers.coach_handlers.TriathlonCoachDataExtractor')
    @patch('bot.handlers.coach_handlers.anthropic')
    @pytest.mark.asyncio
    async def test_anthropic_error_handling_pattern(self, mock_anthropic, mock_extractor, 
                                                   mock_cred_manager, mock_progress_manager, 
                                                   mock_update, mock_context):
        from bot.handlers.coach_handlers import process_planning_context
        
        mock_update = Mock()
        mock_update.effective_user.id = 12345
        mock_update.effective_user.full_name = "Test User"
        mock_update.effective_chat.id = 67890
        mock_update.message = Mock()
        mock_update.message.text = "Test planning context"
        mock_update.message.reply_text = AsyncMock()
        
        mock_context = Mock()
        
        mock_cred_instance = Mock()
        mock_cred_instance.get_credentials.return_value = ("test@example.com", "password")
        mock_cred_manager.return_value = mock_cred_instance
        
        mock_extractor.side_effect = Exception("API Error")
        
        mock_progress_instance = Mock()
        mock_progress_instance.start_coach_analysis = AsyncMock()
        mock_progress_instance.finish = AsyncMock()
        mock_progress_manager.return_value = mock_progress_instance
        
        user_data[mock_update.effective_user.id] = {
            "analysis_context": "",
            "planning_context": ""
        }
        
        result = await process_planning_context(mock_update, mock_context)
        
        assert result == ConversationHandler.END
        mock_progress_instance.finish.assert_called_once()
        
        assert mock_update.effective_user.id not in user_data
    
    @pytest.fixture
    def mock_update(self):
        update = Mock()
        update.effective_user.id = 12345
        update.effective_user.full_name = "Test User"
        update.effective_chat.id = 67890
        update.message = Mock()
        return update
    
    @pytest.fixture
    def mock_context(self):
        return Mock()


class TestConversationStateManagement:
    
    def test_user_data_structure_consistency(self):
        user_id = 12345
        
        user_data[user_id] = {"analysis_context": "", "planning_context": ""}
        
        assert user_id in user_data
        assert "analysis_context" in user_data[user_id]
        assert "planning_context" in user_data[user_id]
        assert user_data[user_id]["analysis_context"] == ""
        assert user_data[user_id]["planning_context"] == ""
        
        user_data[user_id]["analysis_context"] = "Updated analysis context"
        user_data[user_id]["planning_context"] = "Updated planning context"
        
        assert user_data[user_id]["analysis_context"] == "Updated analysis context"
        assert user_data[user_id]["planning_context"] == "Updated planning context"
        
        del user_data[user_id]
        assert user_id not in user_data
"""Data-related command handlers for the Telegram bot."""

import logging
import datetime
import json
import tempfile
from dataclasses import asdict
from telegram import Update, CallbackQuery
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from core.security import SecureCredentialManager, SecureReportManager
from core.security.cache import SecureMetricsCache, SecureActivityCache, SecurePhysiologyCache
from core.security.execution import ExecutionTracker
from services.garmin import TriathlonCoachDataExtractor, ExtractionConfig, TimeRange, GarminData
from bot.formatters import format_and_send_report, escape_markdown

# Configure logging
logger = logging.getLogger(__name__)

async def generate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /generate command."""
    message = update.message or update.callback_query.message
    user_id = update.effective_user.id
    user_name = update.effective_user.full_name
    
    # Try to get stored credentials first
    cred_manager = SecureCredentialManager(user_id)
    stored_credentials = cred_manager.get_credentials()
    
    if not stored_credentials:
        await message.reply_text(
            "🔒 No stored credentials found\\. Use `/login` to connect your account\\!",
            parse_mode=ParseMode.MARKDOWN_V2
        )
        return
    
    email, password = stored_credentials
    
    # Inform user about processing
    await message.reply_text(
        "🔍 Starting analysis\\.\\.\\.\n" +
        "This may take a few minutes\\.",
        parse_mode=ParseMode.MARKDOWN_V2
    )

    try:
        # Check execution limits
        execution_tracker = ExecutionTracker(user_id)
        if not execution_tracker.check_insights_limit():
            remaining_time = "tomorrow"  # Resets at midnight
            await message.reply_text(
                "⚠️ Daily insight limit reached\\. Try again " + remaining_time + "\\.",
                parse_mode=ParseMode.MARKDOWN_V2
            )
            return
            
        # Clear all caches
        data_manager = SecureReportManager(user_id)
        metrics_cache = SecureMetricsCache(user_id)
        activity_cache = SecureActivityCache(user_id)
        physiology_cache = SecurePhysiologyCache(user_id)
        
        data_manager.clear_report()
        metrics_cache.clear()
        activity_cache.clear()
        physiology_cache.clear()
        
        # Get and process fresh data
        extractor = TriathlonCoachDataExtractor(email, password)
        data = extractor.extract_data(ExtractionConfig(
            activities_range=TimeRange.RECENT.value,
            metrics_range=TimeRange.EXTENDED.value,
            include_detailed_activities=True,
            include_metrics=True
        ))
        
        # Process and analyze data using Flow
        from services.ai.flows import AnalysisFlow
        athlete_name = user_name or "Athlete"
        flow = AnalysisFlow(data, str(user_id), athlete_name)
        result = await flow.kickoff_async()
        
        # Cache specialized analysis results
        metrics_cache = SecureMetricsCache(user_id)
        activity_cache = SecureActivityCache(user_id)
        physiology_cache = SecurePhysiologyCache(user_id)
        
        # Store analysis results as strings
        metrics_cache.store(str(flow.state.metrics_result))
        activity_cache.store(str(flow.state.activities_result))
        physiology_cache.store(str(flow.state.physiology_result))
        
        # Store both raw data and final synthesis result
        data_manager.store_report(json.dumps({
            'report': str(result),
            'raw_data': asdict(data)
        }))
        
        # Reset workout counter since data generation was successful
        logger.info(f"Resetting workout counter for user {user_id} after successful data generation")
        execution_tracker.reset_workout_counter()
        
        # Create a temporary file and send the HTML report
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=True) as tmp:
            tmp.write(str(result))  # result is HTML from the formatter task
            tmp.flush()
            
            # Reopen in binary mode for sending
            with open(tmp.name, 'rb') as doc:
                await message.reply_document(
                    document=doc,
                    filename=f"analysis_{datetime.datetime.now().strftime('%Y%m%d')}.html",
                    caption="📊 Your Training Analysis Report",
                    read_timeout=300, write_timeout=300, connect_timeout=300, pool_timeout=300
                )
    except Exception as e:
        logger.error(f"Error processing data: {str(e)}", exc_info=True)
        error_msg = escape_markdown(f"🔄 Connection issue: {str(e)}\n\nPlease try again\\.")
        await message.reply_text(
            error_msg,
            parse_mode=ParseMode.MARKDOWN_V2
        )

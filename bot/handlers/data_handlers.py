"""Data-related command handlers for the Telegram bot."""

import logging
import datetime
import json
from dataclasses import asdict
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from core.security import SecureCredentialManager, SecureReportManager
from services.garmin import TriathlonCoachDataExtractor, ExtractionConfig, TimeRange, GarminData
from bot.formatters import format_and_send_report, escape_markdown

# Configure logging
logger = logging.getLogger(__name__)

async def generate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /generate command."""
    user_id = update.effective_user.id
    
    # Try to get stored credentials first
    cred_manager = SecureCredentialManager(user_id)
    stored_credentials = cred_manager.get_credentials()
    
    if not stored_credentials:
        await update.message.reply_text(
            "🔒 No stored credentials found\\. Use `/login` to connect your account\\!",
            parse_mode=ParseMode.MARKDOWN_V2
        )
        return
    
    email, password = stored_credentials
    
    # Inform user about processing
    await update.message.reply_text(
        "🔍 Starting analysis\\.\\.\\.\n" +
        "This may take a few minutes\\.",
        parse_mode=ParseMode.MARKDOWN_V2
    )

    try:
        # Check for cached data
        data_manager = SecureReportManager(user_id)
        cached_data = data_manager.get_report()
        
        if cached_data:
            # Use cached data
            data, timestamp = cached_data
            # Calculate how old the report is
            age_minutes = int((datetime.datetime.now() - timestamp).total_seconds() / 60)
            await update.message.reply_text(
                "📋 Using existing data from " +
                f"{age_minutes} minutes ago\\.",
                parse_mode=ParseMode.MARKDOWN_V2
            )
            # Parse and format the data
            stored_data = json.loads(data)
            final_messages = format_and_send_report(stored_data['report'])
            for msg in final_messages:
                await update.message.reply_text(
                    msg,
                    parse_mode=ParseMode.MARKDOWN_V2
                )
            return
        else:
            # Get and process data
            from services.ai.enhanced_framework import EnhancedAnalyzer
            extractor = TriathlonCoachDataExtractor(email, password)
            data = extractor.extract_data(ExtractionConfig(
                activities_range=TimeRange.RECENT.value,
                metrics_range=TimeRange.EXTENDED.value,
                include_detailed_activities=True,
                include_metrics=True
            ))
            
            # Process and analyze data
            analyzer = EnhancedAnalyzer(data, str(user_id))
            result = analyzer.analyze()
            
            # Store both raw data and analysis result
            data_manager.store_report(json.dumps({
                'raw_data': asdict(data),
                'report': str(result)
            }))
            
            # Format and send the result
            final_messages = format_and_send_report(str(result))
        for msg in final_messages:
            await update.message.reply_text(
                msg,
                parse_mode=ParseMode.MARKDOWN_V2
            )
    except Exception as e:
        logger.error(f"Error processing data: {str(e)}", exc_info=True)
        error_msg = escape_markdown(f"🔄 Connection issue: {str(e)}\n\nPlease try again\\.")
        await update.message.reply_text(
            error_msg,
            parse_mode=ParseMode.MARKDOWN_V2
        )

async def workout(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /workout command."""
    user_id = update.effective_user.id
    
    # Check for cached data
    data_manager = SecureReportManager(user_id)
    cached_data = data_manager.get_report()
    
    if not cached_data:
        # No cached data available
        await update.message.reply_text(
            "❌ No recent data found\\.\n" +
            "Please use /generate first\\!",
            parse_mode=ParseMode.MARKDOWN_V2
        )
        return
        
    # Use cached data
    data, timestamp = cached_data
    # Calculate how old the report is
    age_minutes = int((datetime.datetime.now() - timestamp).total_seconds() / 60)
    await update.message.reply_text(
        "📋 Using existing data from " +
        f"{age_minutes} minutes ago\\.",
        parse_mode=ParseMode.MARKDOWN_V2
    )
    
    try:
        stored_data = json.loads(data)
        raw_data = GarminData(**stored_data['raw_data'])
        report = stored_data['report']
        
        # Generate workout recommendations
        from services.ai.enhanced_framework import EnhancedAnalyzer
        analyzer = EnhancedAnalyzer(raw_data, str(user_id))
        result = analyzer.generate_workouts(report)
        final_messages = format_and_send_report(str(result))
        for msg in final_messages:
            await update.message.reply_text(
                msg,
                parse_mode=ParseMode.MARKDOWN_V2
            )
    except Exception as e:
        logger.error(f"Error processing data: {str(e)}", exc_info=True)
        error_msg = escape_markdown(f"❌ Error: {str(e)}\n\nPlease try again\\.")
        await update.message.reply_text(
            error_msg,
            parse_mode=ParseMode.MARKDOWN_V2
        )

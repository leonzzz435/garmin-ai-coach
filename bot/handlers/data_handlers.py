"""Data-related command handlers for the Telegram bot."""

import logging
import datetime
import json
import anthropic
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from core.security import SecureCredentialManager, SecureReportManager
from services.garmin import (
    TriathlonCoachDataExtractor,
    ExtractionConfig,
    TimeRange,
    GarminData
)
from services.report import (
    ReportGenerator,
    summarize_activities,
    summarize_training_volume,
    summarize_training_intensity,
    summarize_recovery,
    summarize_training_load,
    summarize_vo2max_evolution,
    summarize_readiness_evolution,
    summarize_race_predictions_weekly,
    summarize_hill_score_weekly,
    summarize_endurance_score_weekly
)
from services.ai.prompts import (
    data_extraction_prompt_01,
    data_extraction_prompt_02,
    system,
    workout_system,
    workout_generation_prompt
)
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
    
    # Inform user about the process steps upfront
    await update.message.reply_text(
        "🔍 Starting your training analysis\\.\\.\\.\n" +
        "1️⃣ Connecting to Garmin\\.\\.\\.\n" +
        "2️⃣ Fetching your activities and metrics\\.\\.\\.\n" +
        "3️⃣ This process may take up to 2 minutes to ensure thorough insights\\! 💪",
        parse_mode=ParseMode.MARKDOWN_V2
    )

    try:
        # Check if we have a recent report
        report_manager = SecureReportManager(user_id)
        stored_report = report_manager.get_report()
        
        report = None
        if stored_report:
            # Use existing report
            stored_data, timestamp = stored_report
            # Calculate how old the report is
            age_minutes = int((datetime.datetime.now() - timestamp).total_seconds() / 60)
            await update.message.reply_text(
                "📋 Using your existing training report from " +
                f"{age_minutes} minutes ago\\.\n" +
                "This helps reduce API calls and processing time\\! 🚀",
                parse_mode=ParseMode.MARKDOWN_V2
            )
            # Use stored report directly - it's already the final LLM-generated report
            final_messages = format_and_send_report(stored_data)
            for msg in final_messages:
                await update.message.reply_text(
                    msg,
                    parse_mode=ParseMode.MARKDOWN_V2
                )
            return  # No need for LLM calls when using stored report
        else:
            # Generate new report
            extractor = TriathlonCoachDataExtractor(email, password)
            config = ExtractionConfig(
                activities_range=TimeRange.RECENT.value,
                metrics_range=TimeRange.EXTENDED.value,
                include_detailed_activities=True,
                include_metrics=True
            )
            data = extractor.extract_data(config)
            report = ReportGenerator(data)
            activities_report = report.generate_activities_report()
            
            await update.message.reply_text(
                "✅ Data retrieved successfully\\!\n" +
                "🔄 Processing your training data\\.\\.\\.\n" +
                "🧠 Generating personalized insights\\.\\.\\.\n" +
                "💾 Saving report for quick access to workouts\\!",
                parse_mode=ParseMode.MARKDOWN_V2
            )

        # Initialize Anthropic client with API key from bot_data
        anthropic_api_key = context.bot_data.get('anthropic_api_key')
        if not anthropic_api_key:
            logger.error("Anthropic API key not found in bot_data")
            await update.message.reply_text(
                "❌ Configuration error\\. Please contact support\\.",
                parse_mode=ParseMode.MARKDOWN_V2
            )
            return
        client = anthropic.Anthropic(api_key=anthropic_api_key)

        # Analyze activities
        prompt_1 = data_extraction_prompt_01 % activities_report
        message_pre = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=4096,
            temperature=0,
            system=system,
            messages=[
                {"role": "user", "content": prompt_1}
            ]
        )
        activity_report = message_pre.content[0].text

        # Generate comprehensive analysis with metrics
        if report:  # We have a fresh fetch with raw data
            metrics_report = report.generate_metrics_report()
            prompt_2 = data_extraction_prompt_02 % metrics_report
        else:  # Using stored data
            prompt_2 = data_extraction_prompt_02 % "Note: Using stored activities report. For detailed metrics analysis, please use /generate to fetch fresh data."

        message_pre_final = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=4096,
            temperature=0,
            system=system,
            messages=[
                {"role": "user", "content": prompt_1},
                {"role": "assistant", "content": activity_report},
                {"role": "user", "content": prompt_2}
            ]
        )
        final_report = message_pre_final.content[0].text

        # Store the final LLM-processed athlete report
        report_manager.store_report(final_report)  # This stores the formatted analysis, not raw data
        final_messages = format_and_send_report(final_report)
        for msg in final_messages:
            await update.message.reply_text(
                msg,
                parse_mode=ParseMode.MARKDOWN_V2
            )
    except Exception as e:
        logger.error(f"Error in generate command: {str(e)}", exc_info=True)
        error_msg = escape_markdown(f"🔄 Connection issue: {str(e)}\n\nPlease try again\\.")
        await update.message.reply_text(
            error_msg,
            parse_mode=ParseMode.MARKDOWN_V2
        )

async def workout(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /workout command."""
    user_id = update.effective_user.id
    
    # Check if we have a recent report
    report_manager = SecureReportManager(user_id)
    stored_report = report_manager.get_report()
    
    if not stored_report:
        # No stored report, ask user to generate first
        await update.message.reply_text(
            "❌ No recent training report found\\.\n" +
            "Please use /generate first to analyze your training data\\!",
            parse_mode=ParseMode.MARKDOWN_V2
        )
        return
        
    # Use existing report
    stored_data, timestamp = stored_report
    # Calculate how old the report is
    age_minutes = int((datetime.datetime.now() - timestamp).total_seconds() / 60)
    await update.message.reply_text(
        "📋 Using your existing training report from " +
        f"{age_minutes} minutes ago\\.\n" +
        "To get fresh insights, use /generate first, then /workout\\! 🔄",
        parse_mode=ParseMode.MARKDOWN_V2
    )
    
    # Initialize Anthropic client for workout generation
    anthropic_api_key = context.bot_data.get('anthropic_api_key')
    if not anthropic_api_key:
        logger.error("Anthropic API key not found in bot_data")
        await update.message.reply_text(
            "❌ Configuration error\\. Please contact support\\.",
            parse_mode=ParseMode.MARKDOWN_V2
        )
        return

    client = anthropic.Anthropic(api_key=anthropic_api_key)
    
    # Generate workout recommendations based on stored report
    message = client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=4096,
        temperature=0,
        system=workout_system,
        messages=[
            {"role": "user", "content": workout_generation_prompt % stored_data}
        ]
    )
    workout_plan = message.content[0].text
    
    # Format and send the workout plan
    final_messages = format_and_send_report(workout_plan)
    for msg in final_messages:
        await update.message.reply_text(
            msg,
            parse_mode=ParseMode.MARKDOWN_V2
        )

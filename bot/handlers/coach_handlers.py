import datetime
import json
import logging
import tempfile
from dataclasses import asdict

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from bot.formatters import escape_markdown
from bot.utils.enhanced_progress_manager import AICoachDetailedProgressManager
from bot.utils.message_formatter import FileDeliveryManager
from core.security import SecureCredentialManager, SecureReportManager
from core.security.cache import SecureActivityCache, SecureMetricsCache, SecurePhysiologyCache
from core.security.execution import ExecutionTracker
from services.ai.langgraph.workflows.planning_workflow import run_complete_analysis_and_planning
from services.garmin import ExtractionConfig, TimeRange, TriathlonCoachDataExtractor

logger = logging.getLogger(__name__)

# Conversation states
EXPECTING_ANALYSIS_CONTEXT = 60
EXPECTING_PLANNING_CONTEXT = 61

user_data = {}  # Structure: {user_id: {'analysis_context': str, 'planning_context': str}}


async def start_coach(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message or update.callback_query.message
    user_id = update.effective_user.id

    cred_manager = SecureCredentialManager(user_id)
    if not cred_manager.has_stored_credentials():
        await message.reply_text(
            "🔒 No stored credentials found\\. Use `/login` to connect your account\\!",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return ConversationHandler.END

    execution_tracker = ExecutionTracker(user_id)
    if not execution_tracker.check_insights_limit():
        remaining_time = "tomorrow"  # Resets at midnight
        await message.reply_text(
            "⚠️ Daily insight limit reached\\. Try again " + remaining_time + "\\.",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return ConversationHandler.END

    user_data[user_id] = {"analysis_context": "", "planning_context": ""}

    await message.reply_text(
        "**Training Analysis & Weekly Planning**\n\n"
        + "Initiating comprehensive analysis of your training data and weekly plan generation\\.\n\n"
        + "🔍 **Data Analysis Context**\n\n"
        + "Specify any factors affecting your current health or training state that should be considered during data interpretation:\n\n"
        + "• Illness or recovery status\n"
        + "• Stress factors \\(work, personal, travel\\)\n"
        + "• HRV anomalies and causes\n"
        + "• Sleep disruptions or schedule changes\n"
        + "• Medication or supplement changes\n"
        + "• Injuries or physical limitations\n\n"
        + "Use /skip if no special considerations apply\\.",
        parse_mode=ParseMode.MARKDOWN_V2,
    )
    return EXPECTING_ANALYSIS_CONTEXT


async def process_analysis_context(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message or update.callback_query.message
    user_id = update.effective_user.id

    if update.message.text != "/skip":
        user_data[user_id]["analysis_context"] = update.message.text.strip()

    await message.reply_text(
        "📅 **Weekly Planning Context**\n\n"
        + "Now, is there anything specific I should consider for your upcoming two training weeks\\?\n\n"
        + "For example:\n"
        + "• Time constraints or schedule limitations\n"
        + "• Specific focus areas \\(speed, endurance, recovery\\)\n"
        + "• Travel plans\n"
        + "• Equipment availability\n"
        + "• Training philosophy or goals\n"
        + "• Training zones or FTP or LTHR\n\n"
        + "Or use /skip if no special considerations\\.",
        parse_mode=ParseMode.MARKDOWN_V2,
    )
    return EXPECTING_PLANNING_CONTEXT


async def process_planning_context(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message or update.callback_query.message
    user_id = update.effective_user.id
    user_name = update.effective_user.full_name

    if update.message.text != "/skip":
        user_data[user_id]["planning_context"] = update.message.text.strip()

    progress_manager = AICoachDetailedProgressManager(context, update.effective_chat.id)
    await progress_manager.start_coach_analysis()

    try:
        cred_manager = SecureCredentialManager(user_id)
        stored_credentials = cred_manager.get_credentials()
        email, password = stored_credentials

        data_manager = SecureReportManager(user_id)
        metrics_cache = SecureMetricsCache(user_id)
        activity_cache = SecureActivityCache(user_id)
        physiology_cache = SecurePhysiologyCache(user_id)

        data_manager.clear_report()
        metrics_cache.clear()
        activity_cache.clear()
        physiology_cache.clear()

        extractor = TriathlonCoachDataExtractor(email, password)
        data = extractor.extract_data(
            ExtractionConfig(
                activities_range=TimeRange.RECENT.value,
                metrics_range=TimeRange.EXTENDED.value,
                include_detailed_activities=True,
                include_metrics=True,
            )
        )

        athlete_name = user_name or "Athlete"
        analysis_context = user_data[user_id].get("analysis_context", "")
        planning_context = user_data[user_id].get("planning_context", "")
        
        from core.security.competitions import SecureCompetitionManager
        competition_manager = SecureCompetitionManager(user_id)
        upcoming_competitions = competition_manager.get_upcoming_competitions()
        
        competitions_data = []
        for comp in upcoming_competitions:
            competitions_data.append({
                'name': comp.name,
                'date': comp.date.isoformat(),
                'race_type': comp.race_type,
                'priority': comp.priority.value,
                'target_time': comp.target_time,
                'location': comp.location,
                'notes': comp.notes
            })

        from datetime import datetime, timedelta
        current_date = {
            'date': datetime.now().strftime('%Y-%m-%d'),
            'day_of_week': datetime.now().strftime('%A'),
            'week_number': str(datetime.now().isocalendar()[1])
        }
        
        week_dates = []
        for i in range(14):
            date_obj = datetime.now() + timedelta(days=i)
            week_dates.append({
                'date': date_obj.strftime('%Y-%m-%d'),
                'day_of_week': date_obj.strftime('%A'),
                'week_number': str(date_obj.isocalendar()[1])
            })

        result = await run_complete_analysis_and_planning(
            user_id=str(user_id),
            athlete_name=athlete_name,
            garmin_data=asdict(data),
            analysis_context=analysis_context,
            planning_context=planning_context,
            competitions=competitions_data,
            current_date=current_date,
            week_dates=week_dates,
            progress_manager=progress_manager
        )

        
        cost_summary = result.get('cost_summary', {})
        execution_metadata = result.get('execution_metadata', {})
        
        if cost_summary.get('total_cost_usd', 0) > 0:
            progress_manager.analysis_stats['total_cost_usd'] = cost_summary['total_cost_usd']
            progress_manager.analysis_stats['total_tokens'] = cost_summary['total_tokens']
            progress_manager.analysis_stats['agents_completed'] = cost_summary.get('agent_count', 10)
            
            if 'plots' in result and result['plots']:
                progress_manager.analysis_stats['plots_created'] = len(result['plots'])
            
            logger.info(f"Final cost tracking for user {user_id}: "
                       f"${cost_summary['total_cost_usd']:.4f} "
                       f"({cost_summary['total_tokens']} tokens)")

        metrics_cache = SecureMetricsCache(user_id)
        activity_cache = SecureActivityCache(user_id)
        physiology_cache = SecurePhysiologyCache(user_id)

        metrics_cache.store(result.get('metrics_result', ''))
        activity_cache.store(result.get('activity_result', ''))
        physiology_cache.store(result.get('physiology_result', ''))

        data_manager.store_report(
            json.dumps({'report': str(result.get('analysis_html', '')), 'raw_data': asdict(data)})
        )

        logger.info(f"Resetting workout counter for user {user_id} after successful coach analysis")
        execution_tracker = ExecutionTracker(user_id)
        execution_tracker.reset_workout_counter()


        date_str = datetime.now().strftime('%Y%m%d')
        file_delivery = FileDeliveryManager(date_str)
        file_sequence = file_delivery.get_file_sequence()

        await progress_manager.analysis_complete_detailed()

        for file_info in file_sequence:
            if file_info['type'] == 'summary':
                await message.reply_text(file_info['content'], parse_mode=file_info['parse_mode'])

            elif file_info['type'] == 'analysis_html':
                with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=True) as tmp:
                    tmp.write(str(result['analysis_html']))
                    tmp.flush()

                    with open(tmp.name, 'rb') as doc:
                        await message.reply_document(
                            document=doc,
                            filename=file_info['filename'],
                            caption=file_info['caption'],
                            parse_mode=file_info['parse_mode'],
                            read_timeout=300,
                            write_timeout=300,
                            connect_timeout=300,
                            pool_timeout=300,
                        )

            elif file_info['type'] == 'weekplan_html':
                with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=True) as tmp:
                    tmp.write(str(result['planning_html']))
                    tmp.flush()

                    with open(tmp.name, 'rb') as doc:
                        await message.reply_document(
                            document=doc,
                            filename=file_info['filename'],
                            caption=file_info['caption'],
                            parse_mode=file_info['parse_mode'],
                            read_timeout=300,
                            write_timeout=300,
                            connect_timeout=300,
                            pool_timeout=300,
                        )

            elif file_info['type'] == 'metrics':
                if 'metrics_result' in result:
                    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=True) as tmp:
                        tmp.write(str(result['metrics_result']))
                        tmp.flush()

                        with open(tmp.name, 'rb') as doc:
                            await message.reply_document(
                                document=doc,
                                filename=file_info['filename'],
                                caption=file_info['caption'],
                                parse_mode=file_info['parse_mode'],
                                read_timeout=300,
                                write_timeout=300,
                                connect_timeout=300,
                                pool_timeout=300,
                            )

            elif file_info['type'] == 'activity_interpretation':
                if 'activity_result' in result:
                    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=True) as tmp:
                        tmp.write(str(result['activity_result']))
                        tmp.flush()

                        with open(tmp.name, 'rb') as doc:
                            await message.reply_document(
                                document=doc,
                                filename=file_info['filename'],
                                caption=file_info['caption'],
                                parse_mode=file_info['parse_mode'],
                                read_timeout=300,
                                write_timeout=300,
                                connect_timeout=300,
                                pool_timeout=300,
                            )

            elif file_info['type'] == 'physiology':
                if 'physiology_result' in result:
                    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=True) as tmp:
                        tmp.write(str(result['physiology_result']))
                        tmp.flush()

                        with open(tmp.name, 'rb') as doc:
                            await message.reply_document(
                                document=doc,
                                filename=file_info['filename'],
                                caption=file_info['caption'],
                                parse_mode=file_info['parse_mode'],
                                read_timeout=300,
                                write_timeout=300,
                                connect_timeout=300,
                                pool_timeout=300,
                            )

            elif file_info['type'] == 'season_plan':
                if 'season_plan' in result and result['season_plan'] is not None:
                    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=True) as tmp:
                        tmp.write(str(result['season_plan']))
                        tmp.flush()

                        with open(tmp.name, 'rb') as doc:
                            await message.reply_document(
                                document=doc,
                                filename=file_info['filename'],
                                caption=file_info['caption'],
                                parse_mode=file_info['parse_mode'],
                                read_timeout=300,
                                write_timeout=300,
                                connect_timeout=300,
                                pool_timeout=300,
                            )
                else:
                    logger.warning(f"Skipping season_plan file delivery - season_plan is None or missing")

            elif file_info['type'] == 'completion':
                await message.reply_text(file_info['content'], parse_mode=file_info['parse_mode'])

    except Exception as e:
        logger.error(f"Error processing full analysis: {str(e)}", exc_info=True)
        
        # Provide user-friendly error messages based on error type
        try:
            if isinstance(e, anthropic.APIStatusError):
                if is_anthropic_overload_error(e):
                    error_message = (
                        "🔄 The AI service is currently experiencing high demand and is temporarily overloaded\\. "
                        "The system automatically retried your request, but the service is still busy\\.\n\n"
                        "⏰ Please try again in a few minutes when the load has decreased\\."
                    )
                else:
                    error_details = get_error_details(e)
                    error_message = (
                        "⚠️ There was an issue with the AI service\\.\n\n"
                        f"Details: {escape_markdown(error_details)}\n\n"
                        "Please try again\\. If the problem persists, contact support\\."
                    )
            else:
                error_details = get_error_details(e)
                error_message = (
                    "❌ Analysis failed due to an unexpected error\\.\n\n"
                    f"Details: {escape_markdown(error_details)}\n\n"
                    "Please try again\\. If the problem persists, contact support\\."
                )
            
            await progress_manager.finish(error_message)
        except Exception:
            # Fallback to basic error message if detailed handling fails
            fallback_msg = escape_markdown(f"❌ Analysis failed: {str(e)}\n\nPlease try again\\.")
            await message.reply_text(fallback_msg, parse_mode=ParseMode.MARKDOWN_V2)

    if user_id in user_data:
        del user_data[user_id]

    return ConversationHandler.END


async def cancel_coach(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message or update.callback_query.message
    user_id = update.effective_user.id

    if user_id in user_data:
        del user_data[user_id]

    await message.reply_text("🚫 AI coach cancelled\\.", parse_mode=ParseMode.MARKDOWN_V2)
    return ConversationHandler.END


coach_handler = ConversationHandler(
    entry_points=[
        CommandHandler("coach", start_coach),
        MessageHandler(filters.Regex("^🏃‍♂️ AI Coach$"), start_coach),
        CallbackQueryHandler(start_coach, pattern="^coach$"),
    ],
    states={
        EXPECTING_ANALYSIS_CONTEXT: [
            MessageHandler(
                (filters.TEXT & ~filters.COMMAND) | filters.Regex("^/skip$"),
                process_analysis_context,
            )
        ],
        EXPECTING_PLANNING_CONTEXT: [
            MessageHandler(
                (filters.TEXT & ~filters.COMMAND) | filters.Regex("^/skip$"),
                process_planning_context,
            )
        ],
    },
    fallbacks=[CommandHandler("cancel", cancel_coach)],
)

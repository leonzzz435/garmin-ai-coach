"""Coach command handlers for the Telegram bot."""

import logging
import datetime
import json
import tempfile
from dataclasses import asdict
from telegram import Update, CallbackQuery
from telegram.constants import ParseMode
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, MessageHandler, filters, CallbackQueryHandler

from core.security import SecureCredentialManager, SecureReportManager
from core.security.cache import SecureMetricsCache, SecureActivityCache, SecurePhysiologyCache
from core.security.execution import ExecutionTracker
from services.garmin import TriathlonCoachDataExtractor, ExtractionConfig, TimeRange, GarminData
from services.ai.langchain.master_orchestrator import LangChainFullAnalysisFlow
from bot.formatters import escape_markdown
from bot.utils.enhanced_progress_manager import AICoachDetailedProgressManager
from bot.utils.message_formatter import MessageFormatter, FileDeliveryManager

# Configure logging
logger = logging.getLogger(__name__)

# Conversation states
EXPECTING_ANALYSIS_CONTEXT = 60
EXPECTING_PLANNING_CONTEXT = 61

# Initialize global user data storage
user_data = {}  # Structure: {user_id: {'analysis_context': str, 'planning_context': str}}

async def start_coach(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start the AI coach process."""
    message = update.message or update.callback_query.message
    user_id = update.effective_user.id
    
    # Check for stored credentials
    cred_manager = SecureCredentialManager(user_id)
    if not cred_manager.has_stored_credentials():
        await message.reply_text(
            "🔒 No stored credentials found\\. Use `/login` to connect your account\\!",
            parse_mode=ParseMode.MARKDOWN_V2
        )
        return ConversationHandler.END
    
    # Check execution limits
    execution_tracker = ExecutionTracker(user_id)
    if not execution_tracker.check_insights_limit():
        remaining_time = "tomorrow"  # Resets at midnight
        await message.reply_text(
            "⚠️ Daily insight limit reached\\. Try again " + remaining_time + "\\.",
            parse_mode=ParseMode.MARKDOWN_V2
        )
        return ConversationHandler.END
    
    # Initialize user data
    user_data[user_id] = {"analysis_context": "", "planning_context": ""}
    
    # Ask for analysis context first
    await message.reply_text(
        "**Training Analysis & Weekly Planning**\n\n" +
        "Initiating comprehensive analysis of your training data and weekly plan generation\\.\n\n" +
        "🔍 **Data Analysis Context**\n\n" +
        "Specify any factors affecting your current health or training state that should be considered during data interpretation:\n\n" +
        "• Illness or recovery status\n" +
        "• Stress factors \\(work, personal, travel\\)\n" +
        "• HRV anomalies and causes\n" +
        "• Sleep disruptions or schedule changes\n" +
        "• Medication or supplement changes\n" +
        "• Injuries or physical limitations\n\n" +
        "Use /skip if no special considerations apply\\.",
        parse_mode=ParseMode.MARKDOWN_V2
    )
    return EXPECTING_ANALYSIS_CONTEXT

async def process_analysis_context(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process analysis context and ask for planning context."""
    message = update.message or update.callback_query.message
    user_id = update.effective_user.id
    
    # Store analysis context if provided
    if update.message.text != "/skip":
        user_data[user_id]["analysis_context"] = update.message.text.strip()
    
    # Ask for planning context
    await message.reply_text(
        "📅 **Weekly Planning Context**\n\n" +
        "Now, is there anything specific I should consider for your upcoming two training weeks\\?\n\n" +
        "For example:\n" +
        "• Time constraints or schedule limitations\n" +
        "• Specific focus areas \\(speed, endurance, recovery\\)\n" +
        "• Travel plans\n" +
        "• Equipment availability\n" +
        "• Training philosophy or goals\n" +
        "• Training zones or FTP or LTHR\n\n" +
        "Or use /skip if no special considerations\\.",
        parse_mode=ParseMode.MARKDOWN_V2
    )
    return EXPECTING_PLANNING_CONTEXT

async def process_planning_context(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process planning context and run AI coach workflow."""
    message = update.message or update.callback_query.message
    user_id = update.effective_user.id
    user_name = update.effective_user.full_name
    
    # Store planning context if provided
    if update.message.text != "/skip":
        user_data[user_id]["planning_context"] = update.message.text.strip()
    
    # Initialize enhanced progress manager for live updates
    progress_manager = AICoachDetailedProgressManager(context, update.effective_chat.id)
    await progress_manager.start_coach_analysis()
    
    try:
        # Get stored credentials
        cred_manager = SecureCredentialManager(user_id)
        stored_credentials = cred_manager.get_credentials()
        email, password = stored_credentials
        
        # Clear all caches
        data_manager = SecureReportManager(user_id)
        metrics_cache = SecureMetricsCache(user_id)
        activity_cache = SecureActivityCache(user_id)
        physiology_cache = SecurePhysiologyCache(user_id)
        
        data_manager.clear_report()
        metrics_cache.clear()
        activity_cache.clear()
        physiology_cache.clear()
        
        # Update progress to data extraction
        await progress_manager.extracting_data_detailed()
        
        extractor = TriathlonCoachDataExtractor(email, password)
        data = extractor.extract_data(ExtractionConfig(
            activities_range=TimeRange.RECENT.value,
            metrics_range=TimeRange.EXTENDED.value,
            include_detailed_activities=True,
            include_metrics=True
        ))
        
        # Run full analysis using master orchestrator with progress manager
        athlete_name = user_name or "Athlete"
        analysis_context = user_data[user_id].get("analysis_context", "")
        planning_context = user_data[user_id].get("planning_context", "")
        
        result = await LangChainFullAnalysisFlow.run_full_analysis(
            user_id, athlete_name, data, analysis_context, planning_context,
            progress_manager=progress_manager
        )
        
        # Update progress to planning phase
        await progress_manager.planning_phase()
        
        # Cache specialized analysis results (same as current generate command)
        metrics_cache = SecureMetricsCache(user_id)
        activity_cache = SecureActivityCache(user_id)
        physiology_cache = SecurePhysiologyCache(user_id)
        
        # Store actual analysis results
        analysis_intermediates = result['analysis_intermediates']
        metrics_cache.store(analysis_intermediates['metrics_result'])
        activity_cache.store(analysis_intermediates['activity_result'])
        physiology_cache.store(analysis_intermediates['physiology_result'])
        
        # Store both raw data and final synthesis result
        data_manager.store_report(json.dumps({
            'report': str(result['analysis_html']),
            'raw_data': asdict(data)
        }))
        
        # Reset workout counter since data generation was successful
        logger.info(f"Resetting workout counter for user {user_id} after successful coach analysis")
        execution_tracker = ExecutionTracker(user_id)
        execution_tracker.reset_workout_counter()
        
        # Update progress to report preparation
        await progress_manager.preparing_reports()
        
        # Initialize file delivery manager for organized sending
        date_str = datetime.datetime.now().strftime('%Y%m%d')
        file_delivery = FileDeliveryManager(date_str)
        file_sequence = file_delivery.get_file_sequence()
        
        # Complete progress tracking
        await progress_manager.analysis_complete_detailed()
        
        # Send files in organized sequence
        for file_info in file_sequence:
            if file_info['type'] == 'summary':
                # Send grouped summary message
                await message.reply_text(
                    file_info['content'],
                    parse_mode=file_info['parse_mode']
                )
                
            elif file_info['type'] == 'analysis_html':
                # Send analysis HTML report
                with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=True) as tmp:
                    tmp.write(str(result['analysis_html']))
                    tmp.flush()
                    
                    with open(tmp.name, 'rb') as doc:
                        await message.reply_document(
                            document=doc,
                            filename=file_info['filename'],
                            caption=file_info['caption'],
                            parse_mode=file_info['parse_mode'],
                            read_timeout=300, write_timeout=300, connect_timeout=300, pool_timeout=300
                        )
                        
            elif file_info['type'] == 'weekplan_html':
                # Send weekly plan HTML report
                with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=True) as tmp:
                    tmp.write(str(result['planning_html']))
                    tmp.flush()
                    
                    with open(tmp.name, 'rb') as doc:
                        await message.reply_document(
                            document=doc,
                            filename=file_info['filename'],
                            caption=file_info['caption'],
                            parse_mode=file_info['parse_mode'],
                            read_timeout=300, write_timeout=300, connect_timeout=300, pool_timeout=300
                        )
                        
            elif file_info['type'] == 'metrics':
                # Send metrics analysis
                if 'metrics_result' in analysis_intermediates:
                    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=True) as tmp:
                        tmp.write(analysis_intermediates['metrics_result'])
                        tmp.flush()
                        
                        with open(tmp.name, 'rb') as doc:
                            await message.reply_document(
                                document=doc,
                                filename=file_info['filename'],
                                caption=file_info['caption'],
                                parse_mode=file_info['parse_mode'],
                                read_timeout=300, write_timeout=300, connect_timeout=300, pool_timeout=300
                            )
                            
            elif file_info['type'] == 'activity_interpretation':
                # Send activity interpretation
                if 'activity_result' in analysis_intermediates:
                    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=True) as tmp:
                        tmp.write(analysis_intermediates['activity_result'])
                        tmp.flush()
                        
                        with open(tmp.name, 'rb') as doc:
                            await message.reply_document(
                                document=doc,
                                filename=file_info['filename'],
                                caption=file_info['caption'],
                                parse_mode=file_info['parse_mode'],
                                read_timeout=300, write_timeout=300, connect_timeout=300, pool_timeout=300
                            )
                            
            elif file_info['type'] == 'physiology':
                # Send physiology analysis
                if 'physiology_result' in analysis_intermediates:
                    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=True) as tmp:
                        tmp.write(analysis_intermediates['physiology_result'])
                        tmp.flush()
                        
                        with open(tmp.name, 'rb') as doc:
                            await message.reply_document(
                                document=doc,
                                filename=file_info['filename'],
                                caption=file_info['caption'],
                                parse_mode=file_info['parse_mode'],
                                read_timeout=300, write_timeout=300, connect_timeout=300, pool_timeout=300
                            )
                            
            elif file_info['type'] == 'season_plan':
                # Send season plan
                planning_intermediates = result['planning_intermediates']
                if planning_intermediates and 'season_plan' in planning_intermediates:
                    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=True) as tmp:
                        tmp.write(planning_intermediates['season_plan'])
                        tmp.flush()
                        
                        with open(tmp.name, 'rb') as doc:
                            await message.reply_document(
                                document=doc,
                                filename=file_info['filename'],
                                caption=file_info['caption'],
                                parse_mode=file_info['parse_mode'],
                                read_timeout=300, write_timeout=300, connect_timeout=300, pool_timeout=300
                            )
                            
            elif file_info['type'] == 'completion':
                # Send final completion message
                await message.reply_text(
                    file_info['content'],
                    parse_mode=file_info['parse_mode']
                )
        
    except Exception as e:
        logger.error(f"Error processing full analysis: {str(e)}", exc_info=True)
        
        # Update progress to show error
        try:
            await progress_manager.finish("❌ Analysis failed\\. Please try again\\.")
        except:
            # Fallback if progress manager fails
            error_msg = escape_markdown(f"❌ Analysis failed: {str(e)}\n\nPlease try again\\.")
            await message.reply_text(
                error_msg,
                parse_mode=ParseMode.MARKDOWN_V2
            )
    
    # Clean up user data
    if user_id in user_data:
        del user_data[user_id]
    
    return ConversationHandler.END

async def cancel_coach(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel the AI coach conversation."""
    message = update.message or update.callback_query.message
    user_id = update.effective_user.id
    
    # Clean up user data
    if user_id in user_data:
        del user_data[user_id]
    
    await message.reply_text(
        "🚫 AI coach cancelled\\.",
        parse_mode=ParseMode.MARKDOWN_V2
    )
    return ConversationHandler.END

# Create conversation handler
coach_handler = ConversationHandler(
    entry_points=[
        CommandHandler("coach", start_coach),
        MessageHandler(filters.Regex("^🏃‍♂️ AI Coach$"), start_coach),
        CallbackQueryHandler(start_coach, pattern="^coach$")
    ],
    states={
        EXPECTING_ANALYSIS_CONTEXT: [
            MessageHandler(
                (filters.TEXT & ~filters.COMMAND) | filters.Regex("^/skip$"),
                process_analysis_context
            )
        ],
        EXPECTING_PLANNING_CONTEXT: [
            MessageHandler(
                (filters.TEXT & ~filters.COMMAND) | filters.Regex("^/skip$"),
                process_planning_context
            )
        ]
    },
    fallbacks=[CommandHandler("cancel", cancel_coach)]
)
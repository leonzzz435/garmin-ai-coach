import logging
import datetime
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
    ConversationHandler
)
from utils.data_extractor import TriathlonCoachDataExtractor, ExtractionConfig, ReportGenerator
from utils.prompts import (
    data_extraction_prompt_01, 
    data_extraction_prompt_02, 
    system,
    workout_system,
    workout_generation_prompt
)
from utils.auth import SecureCredentialManager, SecureReportManager
from config import ANTHROPIC_API_KEY, TELE_BOT_KEY
import anthropic

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Initialize the Anthropic Client
client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# Configuration for the bot
BOT_TOKEN = TELE_BOT_KEY

# Initialize global variables
user_data = {}  # Structure: {user_id: {'save_credentials': bool}}

# Define conversation states
EXPECTING_EMAIL = 1
EXPECTING_PASSWORD = 2

# Helper function to escape special characters

def escape_markdown(text: str) -> str:
    """
    Escapes special characters for Telegram MarkdownV2.
    """
    # First escape the backslash itself
    text = text.replace('\\', '\\\\')
    # Then escape all other special characters except asterisks (used for bold)
    special_chars = ['_', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    return text

# Function to format and split long reports
def format_and_send_report(report_text: str) -> list:
    """
    Format and split report into chunks while escaping special characters.
    """
    max_length = 4000  # Telegram character limit
    escaped_text = escape_markdown(report_text)  # Escape MarkdownV2 characters
    return [escaped_text[i:i + max_length] for i in range(0, len(escaped_text), max_length)]

# Command handlers

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.effective_user.first_name
    await update.message.reply_text(
        f"Hey {user_name}\! 🏃‍♂️ Welcome to your AI Training Assistant\!\n\n" +
        "*Available Commands:*\n\n" +
        "🔐 *Getting Started:*\n" +
        "• `/login` \\- Connect your Garmin account \\(credentials stored securely\\)\n\n" +
        "📊 *Main Features:*\n" +
        "• `/generate` \\- Get AI\\-powered training insights\n" +
        "• `/workout` \\- Get discipline\\-specific workout suggestions\n" +
        "• `/roadmap` \\- View upcoming features\n" +
        "• `/help` \\- Show detailed command overview\n\n" +
        "🔒 *Security Note:*\n" +
        "• Your credentials are only used to fetch data from Garmin\n" +
        "• All credentials are stored securely with encryption\n" +
        "• All communication is encrypted\n" +
        "• Created by Zett with privacy in mind 🛡️\n\n" +
        "Ready to start\\? Use `/help` to see all commands or `/login` to connect your Garmin account\\! 🚀",
        parse_mode=ParseMode.MARKDOWN_V2
    )

async def generate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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
        
        if stored_report:
            # Use existing report
            athlete_data, timestamp = stored_report
            # Calculate how old the report is
            age_minutes = int((datetime.datetime.now() - timestamp).total_seconds() / 60)
            await update.message.reply_text(
                "📋 Using your existing training report from " +
                f"{age_minutes} minutes ago\\.\n" +
                "This helps reduce API calls and processing time\\! 🚀",
                parse_mode=ParseMode.MARKDOWN_V2
            )
            activities_report = athlete_data
        else:
            # Generate new report
            extractor = TriathlonCoachDataExtractor(email, password)
            config = ExtractionConfig(activities_range=21, metrics_range=56, include_detailed_activities=True, include_metrics=True)
            data = extractor.extract_data(config)
            report = ReportGenerator(data)
            activities_report = report.generate_activities_report()
            
            # Store report securely for future use
            report_manager.store_report(activities_report)
            
            await update.message.reply_text(
                "✅ Data retrieved successfully\\!\n" +
                "🔄 Processing your training data\\.\\.\\.\n" +
                "🧠 Generating personalized insights\\.\\.\\.\n" +
                "💾 Saving report for quick access to workouts\\!",
                parse_mode=ParseMode.MARKDOWN_V2
            )

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
        activity_report = message_pre.content[0].text  # Don't escape since this is used in Claude conversation

        # Generate comprehensive analysis with metrics
        metrics_report = report.generate_metrics_report()
        prompt_2 = data_extraction_prompt_02 % metrics_report

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

        # Send final comprehensive report
        final_messages = format_and_send_report(final_report)  # This will handle the escaping
        for msg in final_messages:
            await update.message.reply_text(
                msg,
                parse_mode=ParseMode.MARKDOWN_V2
            )
    except Exception as e:
        logger.error(f"Error in generate command: {str(e)}", exc_info=True)
        error_msg = escape_markdown(f"🔄 Connection issue: {str(e)}\n\nPlease try again.")
        await update.message.reply_text(
            error_msg,
            parse_mode=ParseMode.MARKDOWN_V2
        )

# Error handler
async def clear_credentials(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Clear stored credentials for the user."""
    user_id = update.effective_user.id
    cred_manager = SecureCredentialManager(user_id)
    
    if cred_manager.clear_credentials():
        if user_id in user_data:
            user_data[user_id].clear()
        await update.message.reply_text(
            "✅ Your stored credentials have been cleared\\.\n" +
            "Use `/login` to set up new credentials\\.",
            parse_mode=ParseMode.MARKDOWN_V2
        )
    else:
        await update.message.reply_text(
            "❌ Failed to clear credentials\\. Please try again or contact support\\.",
            parse_mode=ParseMode.MARKDOWN_V2
        )

async def help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 *Available Commands*\n\n" +
        "🔐 *Authentication*\n" +
        "• `/login` \\- Connect your Garmin account \\(credentials stored securely\\)\n" +
        "• `/clear_credentials` \\- Remove stored credentials\n\n" +
        "📊 *Features*\n" +
        "• `/generate` \\- Get personalized training insights\n" +
        "• `/workout` \\- Get discipline\\-specific workout suggestions\n" +
        "• `/roadmap` \\- View upcoming features\n" +
        "• `/help` \\- Show this command overview\n\n" +
        "🔒 *Security Note*\n" +
        "Your credentials are stored securely with encryption\\.",
        parse_mode=ParseMode.MARKDOWN_V2
    )

async def roadmap(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🗺️ *Development Roadmap*\n\n" +
        "*Coming Soon\\:*\n\n" +
        "1️⃣ *General Training Q&A*\n" +
        "• Ask training\\-related questions without Garmin data\n" +
        "• Get expert advice on training principles\n" +
        "• Discuss injury prevention and recovery\n\n" +
        "2️⃣ *Smart Workout Suggestions*\n" +
        "• Daily workout recommendations based on your data\n" +
        "• Adaptive training plans\n" +
        "• Recovery\\-based intensity adjustments\n\n" +
        "Stay tuned for these exciting updates\\! 🚀",
        parse_mode=ParseMode.MARKDOWN_V2
    )

async def workout(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    
    # Check if we have a recent report
    report_manager = SecureReportManager(user_id)
    stored_report = report_manager.get_report()
    
    if stored_report:
        # Use existing report
        athlete_data, timestamp = stored_report
        # Calculate how old the report is
        age_minutes = int((datetime.datetime.now() - timestamp).total_seconds() / 60)
        await update.message.reply_text(
            "📋 Using your existing training report from " +
            f"{age_minutes} minutes ago\\.\n" +
            "To get fresh insights, use /generate first, then /workout\\! 🔄",
            parse_mode=ParseMode.MARKDOWN_V2
        )
    else:
        # Get new data like in generate command
        cred_manager = SecureCredentialManager(user_id)
        stored_credentials = cred_manager.get_credentials()
        
        if not stored_credentials:
            await update.message.reply_text(
                "🔒 No stored credentials found\\. Use `/login` to connect your account\\!",
                parse_mode=ParseMode.MARKDOWN_V2
            )
            return
        
        email, password = stored_credentials
        
        await update.message.reply_text(
            "🔍 Fetching your latest training data\\.\\.\\.\n" +
            "⏳ This might take a minute to ensure accurate suggestions\\!",
            parse_mode=ParseMode.MARKDOWN_V2
        )

        try:
            extractor = TriathlonCoachDataExtractor(email, password)
            config = ExtractionConfig(activities_range=21, metrics_range=56, include_detailed_activities=True, include_metrics=True)
            data = extractor.extract_data(config)
            
            report = ReportGenerator(data)
            athlete_data = report.generate_activities_report()
            
            # Store report securely for future use
            report_manager = SecureReportManager(user_id)
            report_manager.store_report(athlete_data)

        except Exception as e:
            logger.error(f"Error in workout command: {str(e)}", exc_info=True)
            error_msg = escape_markdown(f"🔄 Connection issue: {str(e)}\n\nPlease try again.")
            await update.message.reply_text(
                error_msg,
                parse_mode=ParseMode.MARKDOWN_V2
            )
            return

    await update.message.reply_text(
        "🧠 Analyzing your training patterns and generating discipline\\-specific workouts\\.\\.\\.",
        parse_mode=ParseMode.MARKDOWN_V2
    )
    
    # Generate workouts using the athlete data
    prompt = workout_generation_prompt % athlete_data
    
    message = client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=4096,
        temperature=0,
        system=workout_system,
        messages=[
            {"role": "user", "content": prompt}
        ]
    )
    
    workout_suggestions = message.content[0].text
    
    # Send workout suggestions
    messages = format_and_send_report(workout_suggestions)
    for msg in messages:
        await update.message.reply_text(
            msg,
            parse_mode=ParseMode.MARKDOWN_V2
        )

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error(f"Update {update} caused error {context.error}")
    if update:
        error_message = escape_markdown(f"⚠️ Something unexpected happened: {context.error}\nNo worries - Zett is working on that already (maybe 😁)")
        await update.message.reply_text(
            error_message,
            parse_mode=ParseMode.MARKDOWN_V2
        )

async def start_login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start the login process."""
    user_id = update.effective_user.id
    # Check if user already has stored credentials
    cred_manager = SecureCredentialManager(user_id)
    if cred_manager.has_stored_credentials():
        await update.message.reply_text(
            "⚠️ You already have stored credentials\\. Options:\n\n" +
            "1\\. Continue with stored credentials: Use `/generate` or `/workout`\n" +
            "2\\. Clear stored credentials: `/clear_credentials`\n" +
            "3\\. Start fresh: Clear credentials first, then use `/login`",
            parse_mode=ParseMode.MARKDOWN_V2
        )
        return ConversationHandler.END

    # Initialize user data
    user_data[user_id] = {}

    # Ask for email first
    await update.message.reply_text(
        "Please enter your Garmin email address:",
        parse_mode=ParseMode.MARKDOWN_V2
    )
    return EXPECTING_EMAIL

async def process_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process the email input and ask for password."""
    user_id = update.effective_user.id
    email = update.message.text.strip()
    
    # Store email temporarily for the login process
    user_data[user_id]["temp_email"] = email
    
    # Ask for password
    await update.message.reply_text(
        "Great\\! Now please enter your password:",
        parse_mode=ParseMode.MARKDOWN_V2
    )
    return EXPECTING_PASSWORD

async def process_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process the password and complete login."""
    user_id = update.effective_user.id
    password = update.message.text.strip()
    email = user_data[user_id].get("temp_email")
    # Delete the message containing the password immediately
    await update.message.delete()
    
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="🔐 Testing connection to Garmin\\.\\.\\.",
        parse_mode=ParseMode.MARKDOWN_V2
    )
    
    try:
        # Test connection with Garmin
        extractor = TriathlonCoachDataExtractor(email, password)
        
        # Store credentials securely
        cred_manager = SecureCredentialManager(user_id)
        if cred_manager.store_credentials(email, password):
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="✅ Connection successful\\!\n" +
                    "🔒 Credentials securely stored\\.\n" +
                    "Use /generate for insights or /workout for training suggestions\\! 🚀",
                parse_mode=ParseMode.MARKDOWN_V2
            )
        else:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="❌ Connection successful but failed to store credentials\\.\n" +
                    "Please try again or contact support\\.",
                parse_mode=ParseMode.MARKDOWN_V2
            )
    except Exception as e:
        logger.error(f"Connection test error: {str(e)}")
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="❌ Connection failed\\. Please check your credentials and try again\\.\n" +
                "Your password was not stored\\.",
            parse_mode=ParseMode.MARKDOWN_V2
        )
    
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel the conversation."""
    await update.message.reply_text(
        "Login cancelled\\. Use /login to try again\\.",
        parse_mode=ParseMode.MARKDOWN_V2
    )
    return ConversationHandler.END

# Main function
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Create conversation handler for login process
    login_handler = ConversationHandler(
        entry_points=[CommandHandler("login", start_login)],
        states={
            EXPECTING_EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_email)],
            EXPECTING_PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_password)]
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    # Add handlers
    app.add_handler(login_handler)  # Must be added first to handle the conversation flow
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("generate", generate))
    app.add_handler(CommandHandler("roadmap", roadmap))
    app.add_handler(CommandHandler("help", help))
    app.add_handler(CommandHandler("clear_credentials", clear_credentials))
    app.add_handler(CommandHandler("workout", workout))

    # Error handler
    app.add_error_handler(error_handler)

    # Run the bot
    logger.info("Starting bot...")
    app.run_polling()

if __name__ == "__main__":
    main()

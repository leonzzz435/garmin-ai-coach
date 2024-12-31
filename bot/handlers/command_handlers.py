"""Basic command handlers for the Telegram bot."""

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from bot.formatters import escape_markdown

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the /start command."""
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

async def help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the /help command."""
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
    """Handle the /roadmap command."""
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

async def clear_credentials(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the /clear_credentials command."""
    from core.security import SecureCredentialManager
    
    user_id = update.effective_user.id
    cred_manager = SecureCredentialManager(user_id)
    
    if cred_manager.clear():
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

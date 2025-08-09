
import asyncio
import logging
from typing import Optional
from telegram import Message
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


class ProgressManager:
    
    def __init__(self, context: ContextTypes.DEFAULT_TYPE, chat_id: int):
        self.context = context
        self.chat_id = chat_id
        self.progress_message: Optional[Message] = None
        
    async def start(self, initial_text: str) -> None:
        try:
            self.progress_message = await self.context.bot.send_message(
                chat_id=self.chat_id,
                text=initial_text,
                parse_mode=ParseMode.MARKDOWN_V2
            )
        except Exception as e:
            logger.error(f"Failed to send initial progress message: {e}")
            
    async def update(self, new_text: str, delay: float = 0.5) -> None:
        if not self.progress_message:
            logger.warning("Progress message not initialized")
            return
            
        try:
            # Small delay to make updates visible
            if delay > 0:
                await asyncio.sleep(delay)
                
            await self.context.bot.edit_message_text(
                text=new_text,
                chat_id=self.chat_id,
                message_id=self.progress_message.message_id,
                parse_mode=ParseMode.MARKDOWN_V2
            )
        except Exception as e:
            logger.error(f"Failed to update progress message: {e}")
            
    async def finish(self, final_text: str) -> None:
        if not self.progress_message:
            logger.warning("Progress message not initialized")
            return
            
        try:
            await self.context.bot.edit_message_text(
                text=final_text,
                chat_id=self.chat_id,
                message_id=self.progress_message.message_id,
                parse_mode=ParseMode.MARKDOWN_V2
            )
        except Exception as e:
            logger.error(f"Failed to send final progress message: {e}")


class AICoachProgressManager(ProgressManager):
    
    async def start_analysis(self) -> None:
        await self.start("🚀 Starting AI coach analysis\\.\\.\\.")
        
    async def extracting_data(self) -> None:
        await self.update("📥 Extracting Garmin data\\.\\.\\.")
        
    async def running_analysis(self) -> None:
        await self.update("⚙️ Running training analysis\\.\\.\\.")
        
    async def generating_plan(self) -> None:
        await self.update("📋 Generating weekly training plan\\.\\.\\.")
        
    async def preparing_reports(self) -> None:
        await self.update("📊 Preparing reports and files\\.\\.\\.")
        
    async def analysis_complete(self) -> None:
        await self.finish("✅ Analysis complete\\! Sending reports\\.\\.\\.")
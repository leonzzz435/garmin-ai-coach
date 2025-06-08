"""Message formatter for enhanced Telegram bot UX."""

import datetime
from typing import Dict, List, Optional
from telegram.constants import ParseMode


def escape_markdownv2(text: str) -> str:
    """Escape special characters for Telegram MarkdownV2."""
    # Characters that need escaping in MarkdownV2
    escape_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    
    for char in escape_chars:
        text = text.replace(char, f'\\{char}')
    
    return text


class MessageFormatter:
    """Formats messages with emojis and better structure."""
    
    @staticmethod
    def create_analysis_summary(date_str: str) -> str:
        """Create a grouped summary message for AI Coach analysis results."""
        summary = f"""📦 *AI Coach Analysis Report* — `{date_str}`

🔍 *Comprehensive Analysis Complete:*
📄 Training Report: analysis\\_{date_str}\\.html
📅 Weekly Plan: weekplan\\_{date_str}\\.html

📂 *Specialist Analysis \\(MD files\\)*:
🧪 Dr\\. Nakamura — Predictive performance modeling
🏃 Coach Petrova — Technical execution assessment
🧬 Dr\\. Osei — Recovery optimization analysis
📆 Coach Magnus — Long\\-term periodization strategy

🟢 _Analysis complete\\. Performance optimization ready\\._"""
        
        return summary
    
    @staticmethod
    def create_file_caption(file_type: str, description: str) -> str:
        """Create enhanced captions for different file types."""
        # Escape the description
        escaped_desc = escape_markdownv2(description)
        
        captions = {
            'analysis_html': f"""📊 *Training Analysis Report*
Complete synthesis of all performance factors
• Integrated performance modeling
• Multi\\-factor analysis and insights
• Actionable recommendations
• Comprehensive training assessment

{escaped_desc}""",
            
            'weekplan_html': f"""📅 *Weekly Training Plan*
Detailed workout prescriptions by Coach Magnus
• Systematic training progression
• Balanced intensity distribution
• Recovery integration
• Competition preparation protocols

{escaped_desc}""",
            
            'metrics': f"""🧪 *Metrics Analysis by Dr\\. Nakamura*
Predictive performance modeling and training optimization
• Adaptive performance modeling algorithms
• Training load optimization analysis
• Performance plateau and breakthrough detection
• Risk quantification for overtraining prevention

{escaped_desc}""",
            
            'activity_interpretation': f"""🏃 *Activity Analysis by Coach Petrova*
Technical execution assessment and progression mapping
• Workout execution quality evaluation
• Pacing strategy optimization
• Session progression patterns
• Training effectiveness scoring

{escaped_desc}""",
            
            'physiology': f"""🧬 *Physiology Analysis by Dr\\. Osei*
Recovery optimization and adaptation monitoring
• Heart rate variability pattern analysis
• Sleep architecture and recovery assessment
• Hormonal response to training stimuli
• Overtraining and maladaptation early warning

{escaped_desc}""",
            
            'season_plan': f"""📆 *Season Planning by Coach Magnus*
Long\\-term periodization and systematic development
• Competition timeline and peak timing
• Training stress periodization
• Environmental and seasonal adaptations
• Systematic progression methodology

{escaped_desc}"""
        }
        
        return captions.get(file_type, f"📋 *{escape_markdownv2(file_type.replace('_', ' ').title())}*\n\n{escaped_desc}")
    
    @staticmethod
    def create_completion_message() -> str:
        """Create final completion message."""
        return """✅ *Comprehensive analysis completed\\!*

📥 *You received:*
• 📊 Training analysis report \\(HTML\\)
• 📅 Weekly training plan \\(HTML\\)
• 🧪 Metrics analysis \\(MD\\)
• 🏃 Activity interpretation \\(MD\\)
• 🧬 Physiology analysis \\(MD\\)
• 📆 Season plan \\(MD\\)

🎯 *Next steps:*
• Review your training analysis
• Follow your weekly plan
• Track progress with new data

Need adjustments\\? I DONT CARE BICH\\! 💪"""


class FileDeliveryManager:
    """Manages organized file delivery with better UX."""
    
    def __init__(self, date_str: Optional[str] = None):
        self.date_str = date_str or datetime.datetime.now().strftime('%Y%m%d')
        
    def get_file_sequence(self) -> List[Dict[str, str]]:
        """Get the recommended file delivery sequence."""
        return [
            {
                'type': 'summary',
                'content': MessageFormatter.create_analysis_summary(self.date_str),
                'parse_mode': ParseMode.MARKDOWN_V2
            },
            {
                'type': 'analysis_html',
                'filename': f'analysis_{self.date_str}.html',
                'caption': MessageFormatter.create_file_caption(
                    'analysis_html', 
                    'Complete training insights and recommendations'
                ),
                'parse_mode': ParseMode.MARKDOWN_V2
            },
            {
                'type': 'weekplan_html',
                'filename': f'weekplan_{self.date_str}.html',
                'caption': MessageFormatter.create_file_caption(
                    'weekplan_html',
                    'Your personalized training schedule'
                ),
                'parse_mode': ParseMode.MARKDOWN_V2
            },
            {
                'type': 'metrics',
                'filename': f'metrics_{self.date_str}.md',
                'caption': MessageFormatter.create_file_caption(
                    'metrics',
                    'Detailed metrics breakdown'
                ),
                'parse_mode': ParseMode.MARKDOWN_V2
            },
            {
                'type': 'activity_interpretation',
                'filename': f'activity_interpretation_{self.date_str}.md',
                'caption': MessageFormatter.create_file_caption(
                    'activity_interpretation',
                    'Workout pattern analysis'
                ),
                'parse_mode': ParseMode.MARKDOWN_V2
            },
            {
                'type': 'physiology',
                'filename': f'physiology_{self.date_str}.md',
                'caption': MessageFormatter.create_file_caption(
                    'physiology',
                    'Recovery and adaptation insights'
                ),
                'parse_mode': ParseMode.MARKDOWN_V2
            },
            {
                'type': 'season_plan',
                'filename': f'season_plan_{self.date_str}.md',
                'caption': MessageFormatter.create_file_caption(
                    'season_plan',
                    'Long-term training strategy'
                ),
                'parse_mode': ParseMode.MARKDOWN_V2
            },
            {
                'type': 'completion',
                'content': MessageFormatter.create_completion_message(),
                'parse_mode': ParseMode.MARKDOWN_V2
            }
        ]
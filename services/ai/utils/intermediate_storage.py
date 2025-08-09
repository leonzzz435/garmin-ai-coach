
import os
import logging
import re
from pathlib import Path
from typing import Dict, Any

logger = logging.getLogger(__name__)

class IntermediateResultStorage:
    
    def __init__(self, user_name: str, base_path: str = "stuff"):
        # Sanitize user_name for filesystem safety
        self.user_name = self._sanitize_username(user_name)
        self.base_path = Path(base_path)
        
    def _sanitize_username(self, user_name: str) -> str:
        # Remove or replace problematic characters
        sanitized = re.sub(r'[<>:"/\\|?*]', '_', user_name)
        # Limit length and strip whitespace
        sanitized = sanitized.strip()[:50]
        # Ensure it's not empty
        return sanitized if sanitized else "unknown_user"
        
    def store_analysis_results(self, intermediate_results: Dict[str, str], overwrite: bool = True):
        analysis_dir = self.base_path / "analysis"
        
        # Create user-specific subdirectory for privacy
        if not overwrite:
            user_analysis_dir = analysis_dir / self.user_name
            user_analysis_dir.mkdir(parents=True, exist_ok=True)
            analysis_dir = user_analysis_dir
        else:
            analysis_dir.mkdir(parents=True, exist_ok=True)
        
        # File mapping for analysis results
        file_mapping = {
            'metrics_result': 'metrics.md',
            'activity_result': 'activity_interpretation.md', 
            'physiology_result': 'physiology.md',
            'synthesis_result': 'synthesis.md'
        }
        
        stored_files = []
        
        for result_key, filename in file_mapping.items():
            if result_key in intermediate_results:
                file_path = analysis_dir / filename
                try:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(intermediate_results[result_key])
                    stored_files.append(str(file_path))
                    logger.info(f"Stored {result_key} to {file_path}")
                except Exception as e:
                    logger.error(f"Failed to store {result_key}: {e}")
        
        return stored_files
    
    def store_weekly_plan_results(self, season_plan: str, weekly_plan: str, overwrite: bool = True):
        plans_dir = self.base_path / "weekly_plans"
        
        # Create user-specific subdirectory for privacy
        if not overwrite:
            user_plans_dir = plans_dir / self.user_name
            user_plans_dir.mkdir(parents=True, exist_ok=True)
            plans_dir = user_plans_dir
        else:
            plans_dir.mkdir(parents=True, exist_ok=True)
        
        stored_files = []
        
        try:
            # Store season plan
            season_file = plans_dir / "season_plan.md"
            with open(season_file, 'w', encoding='utf-8') as f:
                f.write(season_plan)
            stored_files.append(str(season_file))
            
            # Store weekly plan
            weekly_file = plans_dir / "two_week_plan.md"
            with open(weekly_file, 'w', encoding='utf-8') as f:
                f.write(weekly_plan)
            stored_files.append(str(weekly_file))
            
            logger.info(f"Stored weekly planning results to {plans_dir}")
            
        except Exception as e:
            logger.error(f"Failed to store weekly planning results: {e}")
        
        return stored_files
    
    def get_stored_analysis_summary(self) -> str:
        analysis_dir = self.base_path / "analysis"
        files = list(analysis_dir.glob("*.md")) if analysis_dir.exists() else []
        
        if not files:
            return "No intermediate analysis results stored."
        
        summary = f"📁 Stored intermediate analysis results for {self.user_name}:\n"
        for file_path in sorted(files):
            summary += f"• {file_path.name}\n"
        
        return summary
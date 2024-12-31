"""Report generation service for athlete data analysis."""

import logging
from typing import Dict, Any, List, Union
from dataclasses import asdict

from services.garmin import GarminData
from .utils import (
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

logger = logging.getLogger(__name__)

class ReportGenerator:
    """Handles the generation of reports from extracted data."""
    
    def __init__(self, data: Union[GarminData, Dict[str, Any]]):
        """Initialize the report generator with athlete data.
        
        Args:
            data: Either a GarminData object or dictionary containing athlete data
        """
        # Convert GarminData to dict if needed
        self.data = asdict(data) if isinstance(data, GarminData) else data
        logger.info(f"Initializing ReportGenerator with data keys: {list(self.data.keys())}")

    def generate_activities_report(self) -> str:
        """Generate activities-focused report."""
        logger.info("Starting activities report generation")
        
        try:
            sections = [
                self._generate_user_profile_section(),
                self._generate_recent_activities_section(),
            ]
            logger.info("Successfully generated all report sections")
        except Exception as e:
            logger.error(f"Error generating report sections: {str(e)}", exc_info=True)
            raise
        
        return "\n\n".join(sections)

    def generate_metrics_report(self) -> str:
        """Generate metrics and analysis report."""
        sections = [
            self._generate_metrics_section(),
            self._generate_training_status_section(),
            self._generate_predictions_section()
        ]
        
        return "\n\n".join(sections)

    def generate_full_report(self) -> str:
        """Generate a complete markdown report."""
        sections = [
            self._generate_user_profile_section(),
            self._generate_recent_activities_section(),
            self._generate_metrics_section(),
            self._generate_training_status_section(),
            self._generate_predictions_section()
        ]
        
        return "\n\n".join(sections)

    def _generate_user_profile_section(self) -> str:
        """Generate the user profile section of the report."""
        profile = self.data['user_profile']
        
        # Handle weight conversion from mm to kg if needed
        weight = profile['weight']
        weight_kg = f"{weight / 1000:.2f} kg" if weight is not None else "N/A"
        
        return f"""# Athlete Profile
- **Gender**: {profile['gender']}
- **Weight**: {weight_kg}
- **Height**: {profile['height']} cm
- **Birth Date**: {profile['birth_date']}
- **Activity Level**: {profile['activity_level']}
- **VO2Max (Running)**: {profile['vo2max_running']} ml/kg/min
- **VO2Max (Cycling)**: {profile['vo2max_cycling']} ml/kg/min
"""

    def _generate_recent_activities_section(self) -> str:
        """Generate the recent activities section of the report."""
        logger.info("Starting recent activities section generation")
        try:
            if 'recent_activities' not in self.data:
                logger.error("No recent_activities found in data")
                return "No recent activities data available."
            
            activities = self.data['recent_activities']
            if not activities:
                logger.info("Empty recent_activities list")
                return "No activities found for the specified period."
            
            logger.info(f"Processing {len(activities)} activities")
            return summarize_activities(activities)
        except Exception as e:
            logger.error(f"Error in _generate_recent_activities_section: {str(e)}", exc_info=True)
            raise

    def _generate_metrics_section(self) -> str:
        """Generate the metrics section of the report."""
        return f"""# Performance Metrics

{summarize_training_volume(self.data['recent_activities'])}

## Training Intensity
{summarize_training_intensity(self.data['recent_activities'])}

## Recovery Metrics
{summarize_recovery(self.data['recovery_indicators'])}
"""

    def _generate_training_status_section(self) -> str:
        """Generate the training status section of the report."""
        return f"""# Training Status

## Load Evolution
{summarize_training_load(self.data['training_load_history'])}

## VO2Max Evolution
{summarize_vo2max_evolution(self.data['vo2_max_history'])}

{summarize_readiness_evolution(self.data['training_readiness'])}
"""

    def _generate_predictions_section(self) -> str:
        """Generate the predictions and scores section of the report."""
        return f"""# Performance Predictions and Scores

## Race Predictions Evolution
{summarize_race_predictions_weekly(self.data['race_predictions'])}

## Hill Score Evolution
{summarize_hill_score_weekly(self.data['hill_score'])}

## Endurance Score Evolution
{summarize_endurance_score_weekly(self.data['endurance_score_history'])}
"""

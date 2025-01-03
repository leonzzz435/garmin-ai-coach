"""
Flow module for AI analysis and workout generation.

This module contains the Flow classes that orchestrate the AI agents and tasks
for analyzing fitness data and generating workouts using CrewAI.

The module provides two main flows:
1. AnalysisFlow - For analyzing athlete data and generating insights
2. WorkoutFlow - For generating personalized workout plans
"""

from .analysis_flow import AnalysisFlow
from .workout_flow import WorkoutFlow

__all__ = ['AnalysisFlow', 'WorkoutFlow']

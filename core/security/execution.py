"""Secure execution tracking implementation."""

import logging
import json
from datetime import datetime, date
from typing import Optional
from .base import SecureStorageBase, StorageError

# Configure logging
logger = logging.getLogger(__name__)

class ExecutionError(StorageError):
    """Exception for execution tracking errors."""

class DailyCounter(SecureStorageBase):
    """Tracks daily execution limits for specific operations."""
    
    def __init__(self, user_id: str, counter_type: str):
        """
        Initialize counter for a specific user and operation type.
        
        Args:
            user_id: Unique identifier for the user
            counter_type: Type of operation to track (e.g., 'insights', 'workouts')
        """
        super().__init__(user_id, f'counter_{counter_type}')
        self.counter_type = counter_type
        self._ensure_counter()
    
    def _ensure_counter(self) -> None:
        """Ensure counter exists and reset if needed."""
        try:
            data = self._read()
            if not data:
                self._reset_counter()
            else:
                # Reset if date has changed
                counter_date = datetime.fromisoformat(data['date']).date()
                if counter_date != date.today():
                    self._reset_counter()
        except Exception as e:
            logger.error(f"Failed to ensure counter: {str(e)}")
            self._reset_counter()
    
    def _reset_counter(self) -> None:
        """Reset counter for new day."""
        try:
            data = {
                'user_id': self.user_id,
                'date': datetime.now().isoformat(),
                'count': 0
            }
            self._write(data)
            logger.info(f"Reset {self.counter_type} counter for user {self.user_id}")
        except Exception as e:
            raise ExecutionError(f"Failed to reset counter: {str(e)}") from e
    
    def increment(self) -> bool:
        """
        Increment counter if limit not exceeded.
        
        Returns:
            bool: True if increment successful, False if limit exceeded
            
        Raises:
            ExecutionError: If counter operation fails
        """
        try:
            self._ensure_counter()
            data = self._read()
            
            # No limits for developer
            if self.user_id == "35795645":
                return True
                
            # Standard limit of 1 for other users
            limit = 1
            
            if data['count'] >= limit:
                logger.warning(f"{self.counter_type} limit exceeded for user {self.user_id}")
                return False
            
            data['count'] += 1
            self._write(data)
            logger.info(f"Incremented {self.counter_type} counter for user {self.user_id}")
            return True
            
        except Exception as e:
            raise ExecutionError(f"Failed to increment counter: {str(e)}") from e
    
    def get_remaining(self) -> int:
        """
        Get remaining executions for today.
        
        Returns:
            int: Number of remaining executions
            
        Raises:
            ExecutionError: If counter operation fails
        """
        try:
            self._ensure_counter()
            data = self._read()
            # No limits for developer
            if self.user_id == "35795645":
                return float('inf')
                
            # Standard limit of 1 for other users
            limit = 1
            return max(0, limit - data['count'])
        except Exception as e:
            raise ExecutionError(f"Failed to get remaining count: {str(e)}") from e
    
    def reset(self) -> None:
        """
        Force reset counter.
        
        Raises:
            ExecutionError: If reset fails
        """
        try:
            self._reset_counter()
        except Exception as e:
            raise ExecutionError(f"Failed to force reset counter: {str(e)}") from e

class ExecutionTracker:
    """Manages execution tracking for insights and workouts."""
    
    def __init__(self, user_id: str):
        """Initialize execution tracker for a user."""
        self.insights_counter = DailyCounter(user_id, 'insights')
        self.workout_counter = DailyCounter(user_id, 'workouts')
    
    def check_insights_limit(self) -> bool:
        """Check if insights can be generated."""
        return self.insights_counter.increment()
    
    def check_workout_limit(self) -> bool:
        """Check if workout can be generated."""
        return self.workout_counter.increment()
    
    def reset_all_counters(self) -> None:
        """Reset both insights and workout counters."""
        self.insights_counter.reset()
        self.workout_counter.reset()
        logger.info(f"Reset all counters for user {self.insights_counter.user_id}")
    
    def reset_workout_counter(self) -> None:
        """Reset workout counter."""
        self.workout_counter.reset()
    
    def reset_insights_counter(self) -> None:
        """Reset insights counter."""
        self.insights_counter.reset()
    
    def get_remaining_insights(self) -> int:
        """Get remaining insight generations for today."""
        return self.insights_counter.get_remaining()
    
    def get_remaining_workouts(self) -> int:
        """Get remaining workout generations for today."""
        return self.workout_counter.get_remaining()

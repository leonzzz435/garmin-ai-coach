from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import Optional, Dict

class RacePriority(Enum):
    """Priority levels for races"""
    A = "A"  # Main season goal
    B = "B"  # Important but not primary
    C = "C"  # Training race or minor event

@dataclass
class Competition:
    """Competition/Race event data with flexible input handling"""
    name: str
    date: date
    race_type: str  # Free text input (e.g., "Half Marathon", "Sprint Tri", "5k")
    priority: RacePriority
    target_time: Optional[str] = None  # Free text input (e.g., "sub 3", "2:30 hrs")
    location: Optional[str] = None
    notes: Optional[str] = None
    completed: bool = False

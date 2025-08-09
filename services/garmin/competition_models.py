from dataclasses import dataclass
from datetime import date
from enum import Enum


class RacePriority(Enum):
    A = "A"  # Main season goal
    B = "B"  # Important but not primary
    C = "C"  # Training race or minor event


@dataclass
class Competition:
    name: str
    date: date
    race_type: str  # Free text input (e.g., "Half Marathon", "Sprint Tri", "5k")
    priority: RacePriority
    target_time: str | None = None  # Free text input (e.g., "sub 3", "2:30 hrs")
    location: str | None = None
    notes: str | None = None
    completed: bool = False

"""
Core package for centralized configuration, security, and storage functionality.
"""

from .config import get_config
from .security import SecureStorageBase

__all__ = ['get_config', 'SecureStorageBase']

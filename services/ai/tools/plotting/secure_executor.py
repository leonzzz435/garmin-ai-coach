"""Secure Python executor for AI-generated plotting code with maximum agent freedom."""

import logging
import sys
import threading
import time
from io import StringIO
from typing import Dict, Any, Optional
import traceback
import re

logger = logging.getLogger(__name__)

class SecurePythonExecutor:
    """Secure execution environment for Python plotting code with agent freedom."""
    
    # Core plotting libraries - agents can import others if needed
    CORE_IMPORTS = {
        'plotly.graph_objects': 'go',
        'plotly.express': 'px',
        'plotly.subplots': 'make_subplots',
        'plotly.figure_factory': 'ff',
        'pandas': 'pd',
        'numpy': 'np',
        'datetime': 'datetime',
        'json': 'json',
        'math': 'math',
        'statistics': 'statistics',
        'collections': 'collections',
        're': 're'
    }
    
    # Only block truly dangerous operations
    BLOCKED_PATTERNS = [
        r'open\s*\(',  # File operations
        r'\.system\s*\(',  # System calls
        r'\.popen\s*\(',  # Process operations
        r'subprocess\.call',  # Subprocess calls
        r'subprocess\.run',  # Subprocess calls
        r'__import__\s*\(',  # Dynamic imports
        r'exec\s*\(',  # Code execution
        r'eval\s*\(',  # Code evaluation
    ]
    
    def __init__(self, max_execution_time: int = 30, max_memory_mb: int = 200):
        """Initialize secure executor with generous resource limits.
        
        Args:
            max_execution_time: Maximum execution time in seconds
            max_memory_mb: Maximum memory usage in MB
        """
        self.max_execution_time = max_execution_time
        self.max_memory_mb = max_memory_mb
        
    def validate_code(self, code: str) -> tuple[bool, str]:
        """Light validation - only block truly dangerous operations.
        
        Args:
            code: Python code to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Only check for truly dangerous patterns
        for pattern in self.BLOCKED_PATTERNS:
            if re.search(pattern, code, re.IGNORECASE):
                return False, f"Blocked dangerous operation: {pattern}"
        
        return True, ""
    
    def create_safe_globals(self) -> Dict[str, Any]:
        """Create globals with common libraries pre-imported.
        
        Returns:
            Globals dictionary with common libraries
        """
        # Start with standard builtins (much more permissive)
        safe_globals = {
            '__builtins__': __builtins__,
        }
        
        # Pre-import common libraries for convenience
        try:
            import plotly.graph_objects as go
            import plotly.express as px
            from plotly.subplots import make_subplots
            import plotly.figure_factory as ff
            import pandas as pd
            import numpy as np
            import datetime
            import json
            import math
            import statistics
            import collections
            import re
            
            safe_globals.update({
                'go': go,
                'px': px,
                'make_subplots': make_subplots,
                'ff': ff,
                'pd': pd,
                'np': np,
                'datetime': datetime,
                'json': json,
                'math': math,
                'statistics': statistics,
                'collections': collections,
                're': re
            })
        except ImportError as e:
            logger.warning(f"Could not import some libraries: {e}")
        
        return safe_globals
    
    def execute_with_timeout(self, code: str, safe_globals: Dict[str, Any], safe_locals: Dict[str, Any]) -> tuple[bool, Any, str]:
        """Execute code with timeout protection.
        
        Args:
            code: Python code to execute
            safe_globals: Globals dictionary
            safe_locals: Locals dictionary
            
        Returns:
            Tuple of (success, result, error_message)
        """
        result = {'success': False, 'output': None, 'error': ''}
        
        def target():
            try:
                # Capture stdout for any print statements
                old_stdout = sys.stdout
                sys.stdout = StringIO()
                
                # Execute the code with full freedom
                exec(code, safe_globals, safe_locals)
                
                # Get any output
                output = sys.stdout.getvalue()
                sys.stdout = old_stdout
                
                # Look for standard plotting results
                if 'fig' in safe_locals:
                    result['success'] = True
                    result['output'] = safe_locals['fig']
                elif 'figure' in safe_locals:
                    result['success'] = True
                    result['output'] = safe_locals['figure']
                elif 'plot' in safe_locals:
                    result['success'] = True
                    result['output'] = safe_locals['plot']
                elif output.strip():
                    result['success'] = True
                    result['output'] = output
                else:
                    # Agent might have created something else - be flexible
                    possible_figures = [v for k, v in safe_locals.items() 
                                      if hasattr(v, 'to_html') or hasattr(v, 'show')]
                    if possible_figures:
                        result['success'] = True
                        result['output'] = possible_figures[0]
                    else:
                        result['error'] = "No plottable output found. Expected 'fig', 'figure', 'plot' variable or object with plotting methods."
                        
            except Exception as e:
                sys.stdout = old_stdout
                result['error'] = f"Execution error: {str(e)}"
                # Include traceback for agent learning
                if logger.isEnabledFor(logging.DEBUG):
                    result['error'] += f"\n{traceback.format_exc()}"
        
        # Run with generous timeout
        thread = threading.Thread(target=target)
        thread.daemon = True
        thread.start()
        thread.join(self.max_execution_time)
        
        if thread.is_alive():
            result['error'] = f"Code execution timed out after {self.max_execution_time} seconds. Consider optimizing your code."
            return False, None, result['error']
        
        return result['success'], result['output'], result['error']
    
    def execute_plotting_code(self, code: str) -> tuple[bool, Any, str]:
        """Execute plotting code with maximum agent freedom.
        
        Args:
            code: Complete Python plotting code to execute
            
        Returns:
            Tuple of (success, plotly_figure_or_output, error_message)
        """
        logger.info("Starting code execution with agent freedom")
        
        # Light validation - only block truly dangerous operations
        is_valid, validation_error = self.validate_code(code)
        if not is_valid:
            logger.warning(f"Code blocked for safety: {validation_error}")
            return False, None, f"Security check failed: {validation_error}"
        
        # Create permissive execution environment
        safe_globals = self.create_safe_globals()
        safe_locals = {}
        
        # Execute with generous timeout
        success, result, error = self.execute_with_timeout(code, safe_globals, safe_locals)
        
        if success:
            logger.info("Code execution successful")
        else:
            logger.info(f"Code execution failed: {error}")
        
        return success, result, error
    
    def plot_to_html(self, fig) -> Optional[str]:
        """Convert various plot objects to HTML string.
        
        Args:
            fig: Plot object (Plotly figure, matplotlib, etc.)
            
        Returns:
            HTML string or None if conversion fails
        """
        try:
            # Plotly figures
            if hasattr(fig, 'to_html'):
                return fig.to_html(include_plotlyjs='inline', div_id=None)
            
            # Matplotlib figures (if agent imported matplotlib)
            elif hasattr(fig, 'savefig'):
                logger.warning("Matplotlib figures not directly supported. Use Plotly for interactive plots.")
                return None
            
            # String output (agent might return HTML directly)
            elif isinstance(fig, str) and '<' in fig:
                return fig
            
            else:
                logger.warning(f"Unknown plot type: {type(fig)}")
                return str(fig)  # Fallback to string representation
                
        except Exception as e:
            logger.error(f"Failed to convert plot to HTML: {e}")
            return None
# Current Task

## Objective
Fix the root cause of GitHub CI test failure: `ModuleNotFoundError: No module named 'core.config'`

## Context
The CI is failing because tests are trying to import `core.config` module which doesn't exist. The error occurs in this import chain:
- Tests import from services/ai/langgraph/
- Those modules import from services/ai/ai_settings.py  
- ai_settings.py tries to import from core.config
- But core.config module is missing

## Next Steps
1. Investigate what's supposed to be in core.config by examining the import statements
2. Check if core.config exists or if there's a missing file
3. Either create the missing core/config.py file or fix the import paths
4. Ensure all imports are properly resolved for the test environment
5. Run tests locally to verify the fix before CI

## Related Files
- `services/ai/ai_settings.py` - Contains the failing import
- `core/__init__.py` - Core module initialization 
- `tests/test_langgraph_planning_workflow.py` - Failing test
- `tests/test_langgraph_poc.py` - Failing test
# Current Task: iPhone App Development Planning

## Current Objectives

### Primary Objective
Transform the existing AI triathlon coaching system (currently Telegram-based) into a native iPhone application while maintaining all existing AI analysis capabilities.

### Specific Goals for This Phase
1. **Architecture Design** ✅ - Design hybrid approach with iOS frontend + Python backend API
2. **Technical Specification** ✅ - Define MVP features and implementation approach  
3. **Documentation Creation** ✅ - Create comprehensive development plan and roadmap
4. **Next Phase Preparation** 🔄 - Prepare for backend API development

## Context

### Current System Overview
- **Existing Platform**: Telegram bot with sophisticated AI analysis
- **Core Technology**: Python with LangChain orchestrators
- **AI Capabilities**: Multi-agent system analyzing Garmin training data
- **Data Processing**: Comprehensive extraction from Garmin Connect
- **Analysis Output**: HTML reports with embedded charts/visualizations

### Constraints & Considerations
- **No Garmin OAuth**: Cannot use official Garmin developer APIs
- **Hybrid Approach**: Keep Python backend, build iOS frontend
- **MVP Focus**: Minimal viable product for first version
- **Security**: Maintain existing credential encryption and security measures

### User Requirements
- **Platform**: Native iPhone app
- **Authentication**: Seamless Garmin login experience
- **Core Feature**: Trigger analysis and view formatted reports
- **User Experience**: Simple, clean, focused interface

## Next Steps

### Immediate Next Actions
1. **Setup Backend API Structure**
   - Create FastAPI project structure
   - Design API endpoints for authentication and analysis
   - Integrate with existing services (SecureCredentialManager, LangChainFullAnalysisFlow)

2. **Define API Contracts**
   - Authentication flow (login, token management)
   - Analysis orchestration (trigger, status, results)
   - Data models for request/response structures

3. **iOS Project Planning**
   - Choose development approach (SwiftUI vs UIKit)
   - Define app navigation structure
   - Plan data flow between views

### Dependencies
- **Backend API**: Must be completed before iOS development can begin
- **Existing Services**: All current AI analysis capabilities must remain functional
- **Security Layer**: Credential management and encryption must be preserved

### Success Criteria for Next Phase
- Backend API successfully wraps existing Python services
- Authentication flow works end-to-end
- Analysis can be triggered and monitored via API
- API is deployed and accessible for iOS development

## Related Tasks from Project Roadmap
- Aligns with "Phase 1: Backend API Development" from projectRoadmap.md
- Supports MVP features defined in roadmap
- Maintains compatibility with existing techStack.md decisions

## Maintenance Update (2025-08)

- Repo cleanup completed (Option A)
  - Removed internal docstrings across codebase; minimal one‑liners kept only for key entry points and orchestrator facades: [`main.py`](main.py), [`services/ai/langchain/master_orchestrator.py`](services/ai/langchain/master_orchestrator.py), [`services/ai/langchain/analysis_orchestrator.py`](services/ai/langchain/analysis_orchestrator.py), [`services/ai/langchain/weekly_plan_orchestrator.py`](services/ai/langchain/weekly_plan_orchestrator.py)
  - Replaced print calls with structured logging via [`utils/logging.py`](utils/logging.py)
  - Deleted commented‑out code and tightened ignore rules in [`.gitignore`](.gitignore)
  - Standardized tooling in [`pyproject.toml`](pyproject.toml) (Ruff/Black) and tasks in [`pixi.toml`](pixi.toml)
  - Added maintenance utility: [`scripts/cleanup_repo.py`](scripts/cleanup_repo.py) (dry‑run/apply)
- Smoke test: bot boots via dev task (`pixi run start-dev`) from [`main.py`](main.py)
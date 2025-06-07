# Current Task: CrewAI to LangChain Migration

## Objective
Migrate the Tele Garmin bot from CrewAI to LangChain to resolve critical privacy vulnerabilities that allow cross-user data contamination.

## Context & Urgency
**CRITICAL PRIVACY ISSUE**: CrewAI's built-in task output storage creates shared databases that leak user data between different users. This is an unfixable architectural flaw that violates basic multi-user application security principles.

**Evidence of Data Leakage**:
- User's friend used the bot days ago
- Today, user's analysis contained information only known from previous days
- Investigation revealed shared storage: `~/.local/share/tele_garmin/CrewAI/latest_kickoff_task_outputs.db`

## Current Technical Analysis

### CrewAI Issues Identified
1. **Mandatory Task Storage**: `TaskOutputStorageHandler` automatically created for every Crew
2. **Shared Storage Path**: All users write to same database file
3. **No Disable Option**: Hardcoded behavior with no configuration to turn off
4. **Cross-User Access**: Previous task outputs accessible to subsequent users

### Current AI Flow Architecture (CrewAI-based)

#### 1. Analysis Flow (`services/ai/flows/analysis/analysis_flow.py`)
**Primary Purpose**: Comprehensive training data analysis and report generation

**Agents**:
- `metrics_agent`: Training load, VO2 max, recovery analysis
- `activity_data_agent`: Structured data extraction from activity files
- `activity_interpreter_agent`: Workout progression pattern analysis
- `physiology_agent`: Physiological response and adaptation analysis
- `synthesis_agent`: Comprehensive report synthesis
- `formatter_agent`: HTML report formatting

**Output**: Detailed HTML analysis report

#### 2. Weekly Plan Flow (`services/ai/flows/weekly_plan/weekly_plan_flow.py`)
**Primary Purpose**: Generate personalized weekly training plans

**Agents**:
- `season_planner_agent`: High-level periodization and season planning
- `weekly_planner_agent`: Detailed two-week training plan creation
- `formatter_agent`: HTML formatting for training plans

**Features**:
- Season-level planning integration
- Competition schedule consideration
- User context integration (injuries, preferences, etc.)
- Two-week detailed workout prescriptions

**Output**: HTML weekly training plan

#### 3. Bot Integration
**Commands**:
- `/generate`: Triggers AnalysisFlow
- `/weekplan`: Triggers WeeklyPlanFlow
- `/workout`: Referenced in UI but no separate flow (merged into weekly planning)

**Note**: There is no separate "WorkoutFlow" - workout functionality is integrated into the WeeklyPlanFlow.

### Code Locations Requiring Changes
- `services/ai/flows/analysis/analysis_flow.py` - Main analysis orchestration
- `services/ai/flows/weekly_plan/weekly_plan_flow.py` - Weekly planning logic
- `services/ai/model_config.py` - LLM configuration
- `services/ai/ai_settings.py` - Agent role definitions
- `bot/handlers/command_handlers.py` - Command routing
- `bot/handlers/conversation_handlers.py` - Flow triggering

## Migration Plan: CrewAI → LangChain

### Phase 1: Architecture Design (Days 1-2)

#### 1.1 LangChain Agent Architecture
**Design Goal**: Create isolated, user-specific agent execution environment

```python
# Target architecture concept
class UserIsolatedAgentSystem:
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.memory = UserSpecificMemory(user_id)  # Isolated memory
        self.tools = create_user_tools(user_id)    # User-scoped tools
        
    def create_analysis_chain(self):
        # LangChain LCEL chains with user isolation
        pass
```

#### 1.2 Flow Mapping Strategy
**Analysis Flow Conversion**:
| CrewAI Agent | LangChain Implementation |
|--------------|-------------------------|
| `metrics_agent` | `create_runnable_sequence()` with metrics analysis prompts |
| `activity_data_agent` | Custom tool + chain for activity processing |
| `activity_interpreter_agent` | Multi-step chain with activity interpretation |
| `physiology_agent` | Specialized chain for physiological analysis |
| `synthesis_agent` | Final synthesis chain combining all results |
| `formatter_agent` | Output formatting chain (HTML generation) |

**Weekly Plan Flow Conversion**:
| CrewAI Agent | LangChain Implementation |
|--------------|-------------------------|
| `season_planner_agent` | High-level planning chain with periodization logic |
| `weekly_planner_agent` | Detailed workout prescription chain |
| `formatter_agent` | HTML formatting chain for training plans |

#### 1.3 State Management Design
Replace CrewAI's shared state with user-isolated state management:

```python
class UserAnalysisState:
    """User-specific analysis state - NO shared storage"""
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.state_file = f"user_states/{user_id}/analysis_state.json"
        # Ensure complete user isolation
```

### Phase 2: Implementation (Days 3-7)

#### 2.1 Core Agent System
**Priority**: Replace analysis flow first (most critical)

**New Structure**:
```
services/ai/langchain/
├── agents/
│   ├── metrics_agent.py
│   ├── activity_agent.py
│   ├── physiology_agent.py
│   ├── synthesis_agent.py
│   └── planning_agent.py       # For weekly planning
├── chains/
│   ├── analysis_chain.py
│   ├── planning_chain.py
│   └── formatting_chain.py
├── memory/
│   ├── user_memory.py          # User-isolated memory
│   └── memory_manager.py
├── tools/
│   ├── garmin_tools.py
│   └── visualization_tools.py
└── orchestrator.py             # Main coordination logic
```

#### 2.2 User Isolation Implementation
**Critical Requirements**:
- Each user gets completely separate execution environment
- No shared files, databases, or memory between users
- Clear data boundaries and access controls

```python
class LangChainAnalysisOrchestrator:
    def __init__(self, user_id: str, garmin_data: GarminData):
        # Enforce user isolation from the start
        self.user_workspace = Path(f"user_workspaces/{user_id}")
        self.user_workspace.mkdir(parents=True, exist_ok=True)
        
        # All operations scoped to this user
        self.memory = UserIsolatedMemory(user_id)
        self.chains = self._create_user_chains(user_id)
```

#### 2.3 Chain Configuration Examples

**Analysis Chain Architecture**:
```python
def create_analysis_chain(user_id: str):
    # Metrics analysis
    metrics_prompt = ChatPromptTemplate.from_template("""
    Analyze training metrics for user {user_id}:
    Data: {metrics_data}
    Competitions: {competitions}
    Focus: training load trends, VO2 max changes, recovery status
    """)
    
    # Activity interpretation
    activity_prompt = ChatPromptTemplate.from_template("""
    Interpret workout patterns for user {user_id}:
    Activities: {activity_data}
    Focus: progression patterns, workout execution quality
    """)
    
    # Synthesis
    synthesis_prompt = ChatPromptTemplate.from_template("""
    Create comprehensive analysis for user {user_id}:
    Metrics Analysis: {metrics_result}
    Activity Analysis: {activity_result}
    Physiology Analysis: {physiology_result}
    """)
    
    # Chain composition with user isolation
    analysis_chain = (
        metrics_prompt | llm | StrOutputParser() |
        RunnableLambda(lambda x: {"metrics_result": x}) |
        (activity_prompt | llm | StrOutputParser()) |
        RunnableLambda(lambda x: {"activity_result": x}) |
        # ... continue chain
    ).with_config({"run_name": f"analysis_{user_id}"})
    
    return analysis_chain
```

**Weekly Planning Chain Architecture**:
```python
def create_weekly_plan_chain(user_id: str):
    season_planning_prompt = ChatPromptTemplate.from_template("""
    Create season plan for user {user_id}:
    Current metrics: {garmin_data}
    Competition schedule: {competitions}
    User context: {athlete_context}
    """)
    
    weekly_planning_prompt = ChatPromptTemplate.from_template("""
    Create detailed weekly plan for user {user_id}:
    Season plan: {season_plan}
    Current training state: {current_state}
    Specific context: {weekly_context}
    """)
    
    planning_chain = (
        season_planning_prompt | llm | StrOutputParser() |
        RunnableLambda(lambda x: {"season_plan": x}) |
        weekly_planning_prompt | llm | StrOutputParser()
    ).with_config({"run_name": f"weekly_plan_{user_id}"})
    
    return planning_chain
```

### Phase 3: Testing & Validation (Days 8-10)

#### 3.1 User Isolation Testing
**Test Cases**:
1. **Multiple User Simulation**: Run analysis for User A, then User B, verify no data leakage
2. **Concurrent User Testing**: Multiple users running analysis simultaneously
3. **State Persistence**: User-specific state survives between sessions
4. **Memory Isolation**: Each user's memory is completely separate

#### 3.2 Functionality Verification
Ensure all current features work with new LangChain implementation:
- ✅ Training metrics analysis (from AnalysisFlow)
- ✅ Activity interpretation (from AnalysisFlow)
- ✅ Physiology analysis (from AnalysisFlow)
- ✅ Synthesis and report generation (from AnalysisFlow)
- ✅ Season planning (from WeeklyPlanFlow)
- ✅ Weekly workout prescriptions (from WeeklyPlanFlow)
- ✅ HTML formatting (both flows)
- ✅ Competition data integration
- ✅ User context integration

### Phase 4: Deployment (Days 11-12)

#### 4.1 Gradual Migration
1. **Feature Flag**: Allow switching between CrewAI and LangChain
2. **A/B Testing**: Compare outputs for quality assurance
3. **User Feedback**: Monitor for any regression in analysis quality

#### 4.2 Cleanup
- Remove CrewAI dependencies
- Clean up old task output databases
- Update documentation

## Implementation Dependencies

### New Dependencies
```python
# Replace in requirements.txt
# crewai==0.105.0  # REMOVE
langchain>=0.1.0
langchain-openai>=0.1.0
langchain-community>=0.0.20
```

### Configuration Changes
- Update `services/ai/model_config.py` for LangChain LLM integration
- Modify environment variable handling
- Restructure agent role definitions

## Success Criteria

### Primary Goals (Must Have)
1. **Zero Cross-User Data Leakage**: Complete user isolation verified through testing
2. **Feature Parity**: All current analysis and planning capabilities maintained
3. **Performance**: Analysis time comparable to current system (30-60 seconds)

### Secondary Goals (Nice to Have)
1. **Improved Error Handling**: Better failure recovery than CrewAI
2. **Enhanced Logging**: User-specific operation logs
3. **Scalability**: Better support for concurrent users

## Risk Mitigation

### High Risk: Analysis Quality Regression
**Mitigation**: 
- Parallel testing with existing system
- User feedback collection
- Gradual rollout with rollback option

### Medium Risk: Implementation Timeline
**Mitigation**:
- Start with minimal viable implementation
- Iterative improvement approach
- Focus on user isolation first, optimization later

### Low Risk: New Dependency Issues
**Mitigation**:
- Use stable LangChain versions
- Comprehensive testing in development environment

## Next Immediate Steps
1. **Day 1**: Design LangChain agent architecture and user isolation strategy
2. **Day 2**: Create proof-of-concept for analysis chain with user isolation
3. **Day 3**: Begin implementing core analysis orchestrator
4. **Day 4**: Implement user-isolated memory and state management
5. **Day 5**: Create weekly planning chains

## Decision Points Needed
1. **Memory Strategy**: File-based vs in-memory user state management?
2. **Chain Complexity**: Single complex chain vs multiple simple chains?
3. **Error Handling**: How aggressive should retry logic be?
4. **Migration Timeline**: Immediate switch or gradual transition?

## References
- **Related Context**: See `codebaseSummary.md` for detailed current architecture analysis
- **Privacy Issue Details**: CrewAI `TaskOutputStorageHandler` sharing data across users
- **User Evidence**: Friend's data appeared in user's analysis, confirming data leakage
- **Current Flows**: Only 2 flows exist (Analysis + WeeklyPlan), no separate WorkoutFlow
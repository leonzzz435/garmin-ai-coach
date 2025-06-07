# Codebase Summary: Tele Garmin Bot

## Overview
A Telegram bot that provides personalized training analysis for runners using Garmin data. The bot uses AI agents to analyze training metrics, activities, and physiology data to generate comprehensive reports and training plans.

## Current Architecture

### Core Components

#### 1. Bot Framework (`bot/`)
- **Telegram Integration**: Python Telegram Bot library
- **Handlers**: Command, conversation, data, and error handlers
- **Security**: User authentication and data encryption

#### 2. AI Analysis System (`services/ai/`)
- **Framework**: CrewAI (❌ **CRITICAL ISSUE IDENTIFIED**)
- **Flows**: Analysis flow and weekly planning flow
- **Agents**: Specialized AI agents for different analysis types
- **Tools**: Custom visualization and data processing tools

#### 3. Data Management (`services/garmin/`)
- **Garmin API Client**: Fetches user data from Garmin Connect
- **Data Models**: Structured data classes for training metrics
- **Data Extractor**: Processes raw Garmin data

#### 4. Security Layer (`core/security/`)
- **Encryption**: User credentials and sensitive data
- **Storage**: Secure file-based storage with user isolation
- **Competition Management**: Race data storage
- **Cache**: User-specific caching for analysis results

## 🚨 CRITICAL PRIVACY ISSUE DISCOVERED

### Problem: CrewAI Context Pollution
**Issue**: CrewAI automatically stores task outputs in shared storage, causing cross-user data contamination.

**Technical Details**:
- CrewAI creates `TaskOutputStorageHandler` for every Crew instance
- Storage path: `~/.local/share/tele_garmin/CrewAI/latest_kickoff_task_outputs.db`
- **NOT user-specific** - all users share the same database
- No option to disable this behavior

**Evidence**:
```python
# From CrewAI source - automatically created
_task_output_handler: TaskOutputStorageHandler = PrivateAttr(
    default_factory=TaskOutputStorageHandler  # Shared across users!
)
```

**Privacy Violation**:
```
User A runs analysis → Task outputs stored in shared DB
User B runs analysis → AI can access User A's previous data
Result: User B might see references to User A's training data
```

### Current Mitigation (Temporary)
- Set `CREWAI_STORAGE_DIR` environment variable per user
- Clear task outputs between users
- **Status**: Band-aid solution, not architecturally sound

## Key Data Flow

### Analysis Flow
1. **Data Extraction**: Garmin API → Structured data models
2. **AI Processing**: CrewAI crews analyze different aspects:
   - Metrics analysis (training load, VO2 max)
   - Activity interpretation (workouts, patterns)
   - Physiology analysis (recovery, stress)
   - Synthesis (comprehensive report)
3. **Report Generation**: HTML formatted analysis
4. **Caching**: Results stored in user-specific cache

### User Data Isolation
- ✅ **Garmin credentials**: Encrypted per user
- ✅ **Competition data**: User-specific files
- ✅ **Cache data**: User-specific cache handlers
- ❌ **AI task outputs**: Shared CrewAI storage (VULNERABILITY)

## External Dependencies

### AI/ML Stack
- **CrewAI**: Multi-agent orchestration (❌ Privacy issues)
- **OpenAI/Deepseek**: LLM providers
- **LiteLLM**: Model abstraction layer

### Data Processing
- **Garmin Connect API**: Training data source
- **Pandas**: Data manipulation
- **Matplotlib**: Visualization generation

### Infrastructure
- **SQLite**: Local data storage
- **Cryptography**: Data encryption
- **Telegram Bot API**: User interface

## Code Organization

### Well-Structured Areas
- **Security modules**: Comprehensive encryption and user isolation
- **Data models**: Clean separation of concerns
- **Bot handlers**: Clear command/conversation flow
- **Error handling**: Robust error management

### Areas Needing Attention
- **AI orchestration**: CrewAI privacy issues require complete replacement
- **Configuration management**: Scattered across multiple files
- **Testing**: Limited test coverage for AI flows

## Recent Changes and Technical Debt

### Implemented Features
- User-specific caching for AI analysis results
- Competition data management
- Secure credential storage
- HTML report formatting

### Technical Debt
1. **CrewAI Dependency**: Fundamental privacy flaw requiring migration
2. **Configuration Complexity**: Multiple config files and settings
3. **Limited Error Recovery**: AI analysis failures not gracefully handled
4. **Scalability Concerns**: File-based storage limits concurrent users

## Performance Characteristics
- **Analysis Time**: 30-60 seconds for complete analysis
- **Memory Usage**: Moderate (CrewAI agents + data processing)
- **Storage**: Encrypted files per user (~1-5MB per user)
- **Concurrency**: Limited by CrewAI's global storage issues

## Migration Requirements

### Immediate Priority: Replace CrewAI
**Reason**: Unfixable privacy vulnerability in multi-user environment

**Target**: LangChain with proper user isolation
- No shared storage between users
- Better agent coordination options
- More granular control over data flow
- Established multi-user patterns

### Secondary Priorities
1. Centralized configuration management
2. Enhanced error handling for AI failures
3. Performance optimization for analysis flows
4. Expanded test coverage

## User Feedback Integration
Current system has shown cross-user data leakage, confirming the need for immediate architectural changes to ensure data privacy and system reliability.
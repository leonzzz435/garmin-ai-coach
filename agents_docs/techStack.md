# Technology Stack

## Backend (Existing)

### Core Python Framework
- **Python 3.10+** - Main programming language
- **Pixi** - Package management and environment handling
- **Anthropic Claude** - AI model for analysis generation

### AI & Data Processing
- **LangGraph** - State-based workflow orchestration framework (migrating from LangChain)
- **LangSmith** - AI observability and cost tracking platform
- **LangChain** - Legacy multi-agent orchestration (being phased out)
- **Anthropic Web Search** - Built-in web search tool for Claude models (max 3 uses per analysis)
- **Garmin Connect Client** - Custom data extraction from Garmin
- **Matplotlib/Plotly** - Chart and visualization generation
- **Pandas/NumPy** - Data processing and analysis

### Security & Storage
- **Custom Security Managers** - Credential encryption and user management
- **Local File Storage** - Report caching and intermediate results
- **Encrypted Credential Storage** - Secure Garmin login handling

### Telegram Integration (Current)
- **python-telegram-bot** - Bot framework and handlers
- **HTML Report Generation** - Rich formatted output

## Backend API (New - Phase 1)

### API Framework
- **FastAPI** - Modern Python web framework
  - Chosen for: Auto-generated OpenAPI docs, type hints, async support
  - Integrates well with existing Python codebase
  - Built-in request validation and serialization

### Authentication & Security
- **JWT (JSON Web Tokens)** - Stateless authentication
- **bcrypt** - Password hashing (if needed for user accounts)
- **HTTPS/TLS** - Encrypted communication
- **CORS middleware** - Cross-origin request handling

### API Documentation
- **OpenAPI/Swagger** - Auto-generated API documentation
- **Pydantic** - Request/response model validation

### Deployment
- **Docker** - Containerization for consistent deployment
- **Railway/Render/DigitalOcean** - Cloud hosting platforms
- **Gunicorn/Uvicorn** - ASGI server for production

## iOS App (New - Phase 2)

### Development Framework
- **SwiftUI** - Modern declarative UI framework
  - Chosen for: Native performance, modern syntax, Apple ecosystem integration
  - Better than UIKit for rapid development
  - Excellent for data-driven interfaces

### Architecture Pattern
- **MVVM (Model-View-ViewModel)** - Clean separation of concerns
- **Combine** - Reactive programming for API communication
- **SwiftUI Navigation** - Modern navigation paradigm

### Core iOS Technologies
- **URLSession** - HTTP networking with async/await
- **WebKit (WKWebView)** - HTML report rendering
- **Keychain Services** - Secure credential storage
- **Charts Framework** - Native chart rendering (iOS 16+)
- **Foundation** - Core iOS data types and utilities

### Networking & Data
- **Codable** - JSON serialization/deserialization
- **Async/Await** - Modern concurrency
- **Combine Publishers** - Reactive data flow

### UI/UX
- **SF Symbols** - Apple's icon system
- **SwiftUI Animations** - Smooth transitions and feedback
- **Adaptive Layout** - Support for different screen sizes

## Data Flow Architecture

### Current LangChain Architecture (Legacy)
```
Telegram Bot -> Sequential Orchestrators -> Garmin Connect -> AI Agents -> HTML Reports
                (800+ lines of coordination code)
```

### New LangGraph Architecture (Target)
```
Telegram Bot -> StateGraph Workflow -> Garmin Connect -> AI Nodes -> HTML Reports
                (300 lines, parallel execution, built-in observability)
```

### Future Hybrid Architecture (Post-Migration)
```
iOS App -> FastAPI -> LangGraph StateGraph -> Garmin Connect -> AI Nodes -> JSON/HTML -> iOS App
```

## Development Tools

### Backend Development
- **VS Code** - Primary IDE
- **Postman/Insomnia** - API testing
- **Docker Desktop** - Local containerization
- **Git** - Version control

### iOS Development
- **Xcode** - Apple's IDE (required for iOS development)
- **iOS Simulator** - Testing on virtual devices
- **TestFlight** - Beta testing platform
- **Instruments** - Performance profiling

### Code Quality & Tooling
- **Ruff** — linting and import sorting
  - Lint: `pixi run lint-ruff`
  - Auto-fix: `pixi run ruff-fix`
- **Black + isort** — code formatting
  - Format: `pixi run format`
- **Maintenance Utility** — repo housekeeping script
  - [`scripts/cleanup_repo.py`](scripts/cleanup_repo.py)
  - Dry-run: `python scripts/cleanup_repo.py --dry-run`
  - Apply: `python scripts/cleanup_repo.py --apply`

## Key Architectural Decisions

### 1. Hybrid Approach
- **Decision**: Keep Python backend, add FastAPI layer
- **Rationale**: Preserve existing AI capabilities, avoid rewriting complex logic
- **Alternative Considered**: Full iOS rewrite (rejected due to complexity)

### 2. FastAPI for Backend API
- **Decision**: Use FastAPI over Flask/Django
- **Rationale**: Better async support, auto-documentation, type safety
- **Integration**: Minimal changes to existing codebase

### 3. SwiftUI for iOS
- **Decision**: SwiftUI over UIKit
- **Rationale**: Modern approach, faster development, better data binding
- **Consideration**: Requires iOS 14+ (acceptable for 2025 app)

### 4. JWT Authentication
- **Decision**: Stateless JWT tokens
- **Rationale**: Scalable, works well with mobile apps, no server session storage
- **Security**: Short expiration, secure storage in iOS Keychain

### 5. WebKit for Reports
- **Decision**: Render HTML reports in WKWebView
- **Rationale**: Preserve existing rich formatting, faster than native reimplementation
- **Enhancement**: Could add native charts later for better performance

## Dependencies & Versions

### Backend API Dependencies (New)
```toml
# pyproject.toml additions
fastapi = "^0.104.0"
uvicorn = "^0.24.0"
python-jose = "^3.3.0"
python-multipart = "^0.0.6"
```

### iOS Dependencies (New)
- **Minimum iOS Version**: iOS 15.0
- **Target iOS Version**: iOS 17.0
- **Xcode Version**: 15.0+
- **Swift Version**: 5.9+

## Future Technology Considerations

### Web Search Integration (New)
- **Supported Models**: Claude Opus 4.1, Claude Sonnet 4, Claude 3.7 Sonnet, Claude 3.5 Sonnet/Haiku
- **Implementation**: LangChain built-in web search tool via `bind_tools()`
- **Cost Tracking**: Web search requests tracked at $10 per 1,000 searches
- **Usage Limits**: Maximum 3 web searches per analysis for cost control

## LangGraph Migration (Current Focus)

### Migration Strategy
- **From**: LangChain sequential orchestrators (800+ lines)
- **To**: LangGraph StateGraph workflows (300 lines, 67% reduction)
- **Timeline**: 5-week phased migration approach
- **Benefits**: Built-in observability, parallel execution, simplified code

### New LangGraph Stack
- **LangGraph ^0.2.0** - State-based workflow orchestration
- **LangSmith** - Professional AI observability and cost tracking
- **StateGraph API** - Explicit state management with typed schemas
- **Checkpointers** - Built-in persistence replacing custom storage
- **Streaming API** - Real-time progress updates

### Architecture Changes

#### State Management
```python
# Typed state schema replacing implicit context
class TrainingAnalysisState(TypedDict):
    user_id: str
    athlete_name: str
    garmin_data: Dict[str, Any]
    
    # Agent results with reducers for parallel execution
    metrics_result: Optional[str]
    physiology_result: Optional[str]
    plots: Annotated[List[Dict], lambda x, y: x + y]
```

#### Workflow Definition
```python
# Explicit graph replacing sequential orchestration
workflow = StateGraph(TrainingAnalysisState)
workflow.add_node("metrics", metrics_node)
workflow.add_node("physiology", physiology_node)
workflow.add_edge("metrics", "synthesis")
workflow.add_edge("physiology", "synthesis")
```

#### Parallel Execution
- **Metrics + Physiology**: Independent analysis in parallel
- **Activity Data → Interpreter**: Sequential dependency maintained
- **State Reducers**: Automatic result aggregation

### Infrastructure Replacement

| Component | Current (LangChain) | New (LangGraph) | Code Reduction |
|-----------|-------------------|----------------|----------------|
| Cost Tracking | Custom CostTracker | LangSmith built-in | 150 lines → 10 lines |
| Progress Updates | Custom callbacks | Streaming API | 100 lines → Built-in |
| Persistence | File-based storage | Checkpointers | 200 lines → Built-in |
| Error Handling | Custom retry logic | Node-level handling | 75 lines → 20 lines |
| State Management | Manual coordination | Typed state + reducers | 275 lines → 50 lines |

### Observability Improvements
- **LangSmith Dashboards**: Professional monitoring replacing custom tracking
- **Graph Visualization**: Workflow debugging in LangGraph Studio
- **Streaming Updates**: Real-time progress without custom implementations
- **Cost Analytics**: Automatic token and request cost tracking per workflow

### Future Enhancements (Post-Migration)
- **WebSocket** - Real-time progress updates
- **Apple Watch SDK** - Watch app extension
- **Core Data** - Local data persistence
- **Push Notifications** - Analysis completion alerts
- **Siri Shortcuts** - Voice integration
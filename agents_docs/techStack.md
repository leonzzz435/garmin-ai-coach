# Technology Stack

## Backend (Existing)

### Core Python Framework
- **Python 3.10+** - Main programming language
- **Pixi** - Package management and environment handling
- **Anthropic Claude** - AI model for analysis generation

### AI & Data Processing
- **LangChain** - Multi-agent orchestration framework
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

### Current Architecture
```
Telegram Bot -> Python Services -> Garmin Connect -> AI Analysis -> HTML Reports
```

### New Hybrid Architecture
```
iOS App -> FastAPI -> Python Services -> Garmin Connect -> AI Analysis -> JSON/HTML -> iOS App
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

### Potential Enhancements
- **WebSocket** - Real-time progress updates
- **Apple Watch SDK** - Watch app extension
- **Core Data** - Local data persistence
- **Push Notifications** - Analysis completion alerts
- **Siri Shortcuts** - Voice integration
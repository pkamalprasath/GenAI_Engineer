# Slack Bot Assistant - Technical Architecture

## System Overview

The Slack Bot Assistant is a production-grade AI-powered bot built with modern Python async architecture. It combines agent-based reasoning, RAG knowledge retrieval, and multi-layered memory to provide intelligent Slack automation.

## Architecture Layers

### 1. Slack Integration Layer
**Location**: `src/slack/`

- **Slack Bolt Framework**: AsyncApp for high-performance event handling
- **Event Listeners**: Messages, commands (@app.command), mentions (@app.event)
- **Middleware Stack**:
  - Authentication (bot loop prevention)
  - Rate Limiting (10 req/min per user, 30 req/min per channel)
  - Error Handling (comprehensive exception management)
- **Services**: Message operations, channel management, scheduling

### 2. Agent System
**Location**: `src/agent/`

- **Orchestrator**: Claude-powered agent with tool calling
- **Tool Registry**: Manages all available tools (Slack, GitHub, Notion)
- **Context Builder**: Assembles memory + RAG + conversation history
- **State Management**: TypedDict schema for agent state

**Agent Flow**:
```
User Message → Context Builder → Claude API (with tools) → Tool Execution → Response
```

### 3. Memory System
**Location**: `src/memory/`

**Multi-Layered Design**:
- **Short-Term**: In-memory conversation context (current session)
- **Long-Term**: File-backed storage
  - `MEMORY.md`: Curated important memories
  - `memory/YYYY-MM-DD.md`: Daily conversation logs
  - `USER.md`, `SOUL.md`, `TOOLS.md`: Profile files

**Memory Manager**: Orchestrates all memory operations with unified API

### 4. RAG Knowledge Base
**Location**: `src/rag/`

- **Vector Store**: ChromaDB with HNSW indexing
- **Indexer**: Indexes 200 messages per channel
- **Retriever**: Semantic search with relevance scoring (threshold: 0.7)
- **Embeddings**: OpenAI text-embedding-3-small

**RAG Pipeline**:
```
User Query → Generate Embedding → Vector Search → Filter by Relevance → Format Context
```

### 5. MCP Servers
**Location**: `src/mcp_servers/`

- **Slack MCP**: Custom FastMCP server
  - Tools: get_channel_messages, post_message, schedule_message, get_channel_info
- **GitHub MCP**: Wrapper for official GitHub MCP
  - Tools: create_issue, list_issues
- **Notion MCP**: Wrapper for official Notion MCP
  - Tools: create_page, search

**MCP Registry**: Central tool discovery and execution

### 6. Business Logic Services
**Location**: `src/services/`

- **Summarization Service**: AI-powered channel summaries
- **Issue Detection**: Pattern-based issue identification
- **Reminder Scheduler**: Cron-based reminder system
- **Notion Integration**: Page creation and search

## Data Flow

### Complete Request Flow

```
1. Slack Event Arrives
   ↓
2. Middleware Layer
   - Auth Middleware: Verify authenticity, prevent bot loops
   - Rate Limit Middleware: Check rate limits
   - Error Handler Middleware: Catch exceptions
   ↓
3. Event Listener (messages.py)
   - Validate and sanitize input
   - Check if bot should respond (DM or mention)
   - Add processing indicator (reaction)
   ↓
4. Agent Orchestrator
   - Build context via Context Builder
     • Short-term memory (conversation history)
     • Long-term memory (MEMORY.md)
     • RAG retrieval (vector search)
   - Call Claude API with:
     • System prompt (with context)
     • User message
     • Tool definitions
   ↓
5. Claude Response Processing
   - Extract text content
   - Execute tool calls if present
   - Format final response
   ↓
6. Memory Update
   - Store interaction in short-term memory
   - Write to daily log (memory/YYYY-MM-DD.md)
   ↓
7. Send Response
   - Remove processing indicator
   - Add completion indicator
   - Post response to Slack
```

## Component Interactions

### Agent → Memory
- **Read**: Get conversation history, recall from MEMORY.md
- **Write**: Store interactions in daily logs

### Agent → RAG
- **Query**: Semantic search for relevant past conversations
- **Context**: Formatted results added to agent prompt

### Agent → MCP Tools
- **Discovery**: Get available tools from registry
- **Execution**: Execute tools with validated parameters
- **Results**: Include in agent response

### Memory → RAG
- **Indexing**: Daily logs can be indexed for RAG
- **Retrieval**: RAG queries can search indexed memories

## Security Architecture

### Authentication & Authorization
- Request signature verification (HMAC-SHA256) via Slack Bolt
- Timestamp validation (5-minute window)
- Bot loop prevention (ignore bot_id messages)

### Rate Limiting
- **User-Level**: 10 requests/minute
- **Channel-Level**: 30 requests/minute
- **Implementation**: In-memory token bucket (development), Redis (production)

### Input Validation
- Channel/User ID format validation
- Text length limits
- Injection attack detection
- HTML sanitization

### Token Management
- Environment variables (development)
- Secrets Manager (production)
- Token masking in logs
- Rotation reminders

## Configuration Management

### Settings System
**File**: `config/settings.py`

- **Pydantic Settings**: Type-safe configuration
- **Environment Variables**: Load from .env file
- **Validation**: Automatic at startup (fail fast)
- **Computed Properties**: `is_production`, `use_socket_mode`

### Logging System
**File**: `config/logging.yaml`

- **Handlers**: Console (dev), File rotation (prod)
- **Formatters**: Simple, detailed, JSON
- **Per-Module Levels**: Granular control
- **Third-Party Filtering**: Reduce noise from libraries

## Deployment Modes

### Development Mode
- **Transport**: Socket Mode (WebSocket, no public URL needed)
- **Database**: SQLite for agent state
- **Rate Limiting**: In-memory
- **Vector Store**: Local ChromaDB
- **Logging**: Verbose console output

### Production Mode
- **Transport**: HTTP + FastAPI
- **Database**: PostgreSQL with pgvector
- **Rate Limiting**: Redis-backed
- **Vector Store**: Managed ChromaDB or Pinecone
- **Logging**: Structured JSON to aggregator (DataDog, CloudWatch)
- **Secrets**: AWS Secrets Manager / HashiCorp Vault
- **Deployment**: Docker containers

## Technology Stack

### Core Dependencies
- **Python**: 3.11+ (async/await, type hints)
- **Slack Bolt**: 1.20+ (async Slack framework)
- **Anthropic SDK**: 0.39+ (Claude API)
- **LangGraph**: 0.2+ (agent orchestration)
- **FastMCP**: 2.0+ (MCP server framework)
- **ChromaDB**: 0.5+ (vector store)
- **OpenAI**: 1.50+ (embeddings)

### Supporting Libraries
- **Pydantic**: Data validation and settings
- **aiohttp**: Async HTTP client
- **APScheduler**: Cron job scheduling
- **Poetry**: Dependency management
- **pytest**: Testing framework

## Scalability Considerations

### Horizontal Scaling
- **Stateless Design**: Agent orchestrator is stateless
- **Shared Services**:
  - Redis for rate limiting
  - PostgreSQL for agent state
  - Managed vector store
- **Load Balancing**: Multiple bot instances behind load balancer

### Performance Optimization
- **Async/Await**: Non-blocking I/O throughout
- **Connection Pooling**: Slack client, database connections
- **Caching**: Memory manager caches recent contexts
- **Batch Operations**: Batch embedding generation

### Monitoring & Observability
- **Structured Logging**: JSON logs for parsing
- **Metrics**: Request rate, response time, error rate
- **Tracing**: Request ID propagation
- **Alerting**: Error thresholds, rate limit violations

## Extension Points

### Adding New Tools
1. Define tool function in `src/agent/tools.py`
2. Add tool definition schema
3. Register in ToolRegistry
4. Tool automatically available to agent

### Adding New MCP Servers
1. Create client wrapper in `src/mcp_servers/`
2. Add to MCPRegistry
3. Expose tools via ToolRegistry

### Adding New Business Logic
1. Create service in `src/services/`
2. Inject dependencies (Slack client, etc.)
3. Call from agent tools or directly

## Testing Strategy

### Unit Tests
- Utilities (validators, security, logger)
- Memory operations
- RAG retrieval logic
- Tool execution

### Integration Tests
- Slack event → Agent → Response flow
- Memory persistence
- RAG indexing and retrieval
- Rate limiting enforcement

### End-to-End Tests
- Real Slack workspace (test channel)
- Complete workflows (summarization, reminders, etc.)
- MCP tool execution

## Future Enhancements

1. **Multi-Workspace Support**: Scale to multiple Slack workspaces
2. **Advanced RAG**: Hybrid search, reranking, query decomposition
3. **User Personalization**: Per-user memory and preferences
4. **Analytics Dashboard**: Usage metrics, popular features
5. **Plugin System**: Community-contributed tools and integrations

---

**Built with educational intent - every component is documented and production-ready.**

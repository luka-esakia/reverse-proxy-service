# Generic Reverse Proxy Service

A schema-driven reverse proxy service for external sports APIs, built with FastAPI. Routes operations to provider adapters with validation, rate limiting, exponential backoff, and comprehensive audit logging.

## Features

- **Single Entry Point**: POST `/proxy/execute` handles all operations
- **Schema-Driven Routing**: Validates payloads and normalizes responses
- **Adapter Pattern**: Easy provider swapping (currently supports OpenLiga)
- **Rate Limiting**: Configurable per-process request limits
- **Exponential Backoff**: Retry logic with jitter for upstream failures
- **Audit Logging**: Structured JSON logs with request correlation
- **Middleware**: Request/response logging with sensitive data protection

## Quick Start

### 1. Install Dependencies

```bash
# Install with uv
uv sync
```

### 2. Run the Service

```bash
uv run uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### 3. Test with a Simple Request

```bash
curl -X POST http://localhost:8000/proxy/execute \
  -H "Content-Type: application/json" \
  -d '{"operationType": "ListLeagues", "payload": {}}'
```

## Supported Operations

### 1. ListLeagues
Get all available leagues.

**Payload Schema:**
```json
{}
```

**Example Request:**
```bash
curl -X POST http://localhost:8000/proxy/execute \
  -H "Content-Type: application/json" \
  -d '{
    "operationType": "ListLeagues",
    "payload": {}
  }'
```

**Response:**
```json
{
  "requestId": "uuid-here",
  "operationType": "ListLeagues",
  "data": {
    "leagues": [
      {
        "id": 1,
        "name": "Bundesliga",
        "shortcut": "bl1",
        "country": "Germany",
        "season": "2023"
      }
    ]
  }
}
```

### 2. GetLeagueMatches
Get matches for a specific league and season.

**Payload Schema:**
```json
{
  "league_shortcut": "string",
  "league_season": "string"
}
```

**Example Request:**
```bash
curl -X POST http://localhost:8000/proxy/execute \
  -H "Content-Type: application/json" \
  -d '{
    "operationType": "GetLeagueMatches",
    "payload": {
      "league_shortcut": "bl1",
      "league_season": "2023"
    }
  }'
```

### 3. GetTeam
Get team details by ID.

**NOTE: OpenLiga does not support a direct team lookup, so this operation may return limited data.**

**Payload Schema:**
```json
{
  "team_id": "integer"
}
```

**Example Request:**
```bash
curl -X POST http://localhost:8000/proxy/execute \
  -H "Content-Type: application/json" \
  -d '{
    "operationType": "GetTeam",
    "payload": {
      "team_id": 40
    }
  }'
```

### 4. GetMatch
Get match details by ID.)

**Payload Schema:**
```json
{
  "match_id": "integer"
}
```

**Example Request:**
```bash
curl -X POST http://localhost:8000/proxy/execute \
  -H "Content-Type: application/json" \
  -d '{
    "operationType": "GetMatch",
    "payload": {
      "match_id": 12345
    }
  }'
```

## Architecture

### Decision Mapper
The `DecisionMapper` class handles:
1. **Operation Validation**: Maps `operationType` to payload validators
2. **Schema Validation**: Uses Pydantic models to validate request payloads
3. **Provider Routing**: Calls the appropriate provider method
4. **Response Normalization**: Converts provider responses to standardized schemas
5. **Error Handling**: Provides consistent error responses

### Adapter Pattern
The system uses a provider-agnostic interface (`SportsProvider`) with concrete implementations:

- **Base Interface**: `providers/base.py` - Defines the contract
- **OpenLiga Adapter**: `providers/openliga.py` - Implements OpenLiga API integration
- **Easy Extension**: Add new providers by implementing the `SportsProvider` interface

### Middleware & Logging
- **Request/Response Middleware**: Logs all HTTP interactions with metadata
- **Audit Logging**: Structured JSON logs with complete request correlation
- **Sensitive Data Protection**: Automatically redacts authorization headers and cookies
- **Context Variables**: Single request ID propagated across all log entries
- **Request ID Support**: Accepts `X-Request-ID` header or generates UUID automatically

## Configuration

All configuration is done via environment variables:

### Provider Selection
```bash
export PROVIDER_NAME="openliga"  # Currently only openliga supported
```

### Rate Limiting
```bash
export RATE_LIMIT_REQUESTS="10"    # Max requests per window
export RATE_LIMIT_WINDOW="60"      # Time window in seconds
```

### Exponential Backoff
```bash
export MAX_RETRIES="3"             # Maximum retry attempts
export BASE_DELAY="1.0"            # Initial delay in seconds
export MAX_DELAY="30.0"            # Maximum delay cap
export BACKOFF_MULTIPLIER="2.0"    # Exponential multiplier
export JITTER_RANGE="0.1"          # Jitter percentage (0.1 = 10%)
```

### Server Settings
```bash
export HOST="0.0.0.0"              # Bind address
export PORT="8000"                 # Port number
export LOG_LEVEL="INFO"            # Logging level
```

## Sample Log Output

All logs use the same request ID for complete correlation across the request lifecycle:

```json
{"requestId": "test-correlation-123", "timestamp": "2024-11-26T12:00:00", "stage": "inbound", "method": "POST", "path": "/proxy/execute"}
{"requestId": "test-correlation-123", "timestamp": "2024-11-26T12:00:00", "stage": "proxy_start", "operation_type": "ListLeagues"}
{"requestId": "test-correlation-123", "timestamp": "2024-11-26T12:00:00", "stage": "validation", "outcome": "pass", "operation_type": "ListLeagues"}
{"requestId": "test-correlation-123", "timestamp": "2024-11-26T12:00:00", "stage": "provider_call", "operation_type": "ListLeagues", "provider": "OpenLigaProvider"}
{"requestId": "test-correlation-123", "timestamp": "2024-11-26T12:00:00", "stage": "upstream_request", "attempt": 1, "method": "GET", "url": "https://api.openligadb.de/getavailableleagues"}
{"requestId": "test-correlation-123", "timestamp": "2024-11-26T12:00:00", "stage": "upstream_response", "status_code": 200, "latency_ms": 245.67, "url": "https://api.openligadb.de/getavailableleagues"}
{"requestId": "test-correlation-123", "timestamp": "2024-11-26T12:00:00", "stage": "provider_response", "outcome": "success", "operation_type": "ListLeagues"}
{"requestId": "test-correlation-123", "timestamp": "2024-11-26T12:00:00", "stage": "response_normalization", "outcome": "success", "operation_type": "ListLeagues"}
{"requestId": "test-correlation-123", "timestamp": "2024-11-26T12:00:00", "stage": "proxy_complete", "outcome": "success", "operation_type": "ListLeagues"}
{"requestId": "test-correlation-123", "timestamp": "2024-11-26T12:00:00", "stage": "outbound", "status_code": 200, "body_size": 1234, "latency_ms": 267.89}
```

## Error Handling

The service provides consistent error responses:

### 400 - Bad Request
```json
{
  "error": "Unknown operationType: InvalidOp",
  "code": "UNKNOWN_OPERATION",
  "details": {"valid_operations": ["ListLeagues", "GetLeagueMatches", "GetTeam", "GetMatch"]}
}
```

### 400 - Validation Error
```json
{
  "error": "Payload validation failed",
  "code": "VALIDATION_ERROR",
  "details": {
    "validation_errors": [
      {"field": "team_id", "message": "field required", "type": "missing"}
    ]
  }
}
```

### 502 - Upstream Error
```json
{
  "error": "Upstream API failed",
  "code": "UPSTREAM_ERROR",
  "details": {"message": "Upstream API failed with status 500"}
}
```

## Development

### Adding a New Provider

1. **Implement the Interface**:
   ```python
   # providers/new_provider.py
   from .base import SportsProvider
   
   class NewProvider(SportsProvider):
       async def list_leagues(self) -> Dict[str, Any]:
           # Implementation here
           pass
   ```

2. **Update the Factory**:
   ```python
   # main.py
   def create_provider():
       if config.provider_name == "new_provider":
           return NewProvider(provider_config)
   ```

3. **Set Environment Variable**:
   ```bash
   export PROVIDER_NAME="new_provider"
   ```

### Testing

```bash
# Health check
curl http://localhost:8000/health

# Get supported operations and schemas
curl http://localhost:8000/operations

# Test with custom request ID for correlation
curl -X POST http://localhost:8000/proxy/execute \
  -H "Content-Type: application/json" \
  -H "X-Request-ID: my-test-123" \
  -d '{"operationType": "ListLeagues", "payload": {}}'

# Test error handling
curl -X POST http://localhost:8000/proxy/execute \
  -H "Content-Type: application/json" \
  -d '{"operationType": "InvalidOp", "payload": {}}'
```

## Project Structure

```
.
├── main.py                 # FastAPI application entry point
├── config.py              # Configuration management
├── providers/
│   ├── base.py            # Provider interface
│   └── openliga.py        # OpenLiga implementation
├── proxy/
│   ├── decision_mapper.py # Operation routing and validation
│   ├── middleware.py      # Request/response logging
│   ├── logging_config.py  # Structured logging utilities
│   └── schemas.py         # Pydantic models
├── pyproject.toml         # Dependencies
└── README.md             # This file
```

## Rate Limiting & Backoff Details

- **Rate Limiting**: In-memory per-process limiting using a sliding window approach
- **Exponential Backoff**: Implements exponential backoff with jitter on 429/5xx errors and timeouts
- **Configurable**: All timing and limits configurable via environment variables
- **Observability**: All rate limiting waits and retry attempts are logged with correlation
- **Graceful Degradation**: Service continues operating even when upstream APIs are slow or failing

## Features Implemented

✅ **Single Entry Point**: POST `/proxy/execute` handles all operations  
✅ **Schema-Driven Decision Mapper**: Validates payloads and routes operations  
✅ **Adapter Pattern**: Provider-agnostic interface with OpenLiga implementation  
✅ **Audit & Logging Layer**: Structured logs with request ID correlation  
✅ **Request/Response Middleware**: Logs metadata safely without exposing secrets  
✅ **Rate Limiting**: Configurable per-process limits with sliding window  
✅ **Exponential Backoff**: Retry logic with jitter for upstream failures  
✅ **Error Handling**: Consistent error responses with proper HTTP status codes  
✅ **Configuration**: Environment variable based configuration  
✅ **Request ID Correlation**: Complete traceability across all log entries

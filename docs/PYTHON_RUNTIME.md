# Python Runtime Guide

Complete guide to using the DebugIn Python agent for dynamic debugging.

## Installation

### From Source
```bash
pip install -e .
```

### Via pip
```bash
pip install tracepointdebug
```

## Quick Start

### 1. Embed the Agent

```python
from tracepointdebug import start_agent

# Start the agent
agent = start_agent(
    control_api_port=5001,
    event_sink_url='http://127.0.0.1:4317'
)
```

### 2. Create a Tracepoint via HTTP

```bash
curl -X POST http://127.0.0.1:5001/tracepoints \
  -H "Content-Type: application/json" \
  -d '{
    "file": "myapp/handlers.py",
    "line": 42,
    "condition": "user_id > 100"
  }'
```

### 3. Application Executes, Breakpoint Fires

When your code hits line 42 with `user_id > 100`, the agent captures:
- Arguments passed to the function
- Local variables
- Return value
- Call stack

### 4. Event Sent to Event Sink

```json
{
  "name": "probe.hit.snapshot",
  "timestamp": "2025-01-01T12:00:00.000Z",
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "client": {
    "hostname": "dev-machine",
    "applicationName": "myapp",
    "applicationInstanceId": "prod-1",
    "agentVersion": "0.3.0",
    "runtime": "python",
    "runtimeVersion": "3.11"
  },
  "payload": {
    "probeId": "tp-uuid-1",
    "probeType": "tracepoint",
    "file": "myapp/handlers.py",
    "line": 42,
    "snapshot": {
      "arguments": { "user_id": 150 },
      "locals": { "session": "abc123" },
      "returnValue": { "status": "ok" }
    }
  }
}
```

## Configuration

### Environment Variables

```bash
# Event sink URL (default: http://127.0.0.1:4317)
export EVENT_SINK_URL=http://event-sink:4317

# Control API port (default: 5001)
export DEBUGIN_CONTROL_API_PORT=5001

# Control API host (default: 127.0.0.1, set to 0.0.0.0 to bind all interfaces)
export DEBUGIN_CONTROL_API_BIND_ALL=1

# Broker configuration
export SIDEKICK_BROKER_HOST=wss://broker.example.com
export SIDEKICK_BROKER_PORT=443
```

### Programmatic Configuration

```python
from tracepointdebug import ControlAPI

# Create with custom settings
api = ControlAPI(port=5001, host='127.0.0.1')
api.start()
```

## Control API Endpoints

### Health Check

```bash
GET /health
```

Response:
```json
{
  "status": "healthy",
  "version": "0.3.0",
  "engine": "pytrace",
  "features": {
    "tracepoints": true,
    "logpoints": true,
    "conditions": true,
    "rateLimit": true,
    "freeThreaded": false
  }
}
```

### Create Tracepoint

```bash
POST /tracepoints
Content-Type: application/json

{
  "file": "app.py",
  "line": 42,
  "condition": "x > 10",
  "tags": ["debug", "production"]
}
```

Response: `201 Created`

### Create Logpoint

```bash
POST /logpoints
Content-Type: application/json

{
  "file": "app.py",
  "line": 50,
  "message": "Processing user {user_id} with balance {balance}",
  "condition": "balance < 0"
}
```

### Enable/Disable Tags

```bash
POST /tags/enable
{ "tags": ["debug"] }

POST /tags/disable
{ "tags": ["production"] }
```

### List Points

```bash
GET /points

Response:
[
  {
    "id": "tp-1",
    "type": "tracepoint",
    "file": "app.py",
    "line": 42,
    "enabled": true
  }
]
```

## Condition Expression Language

Conditions use a safe, restricted expression parser:

```python
# Numeric comparisons
x > 10
count <= 5
value == 100

# Logical operators
x > 10 && y < 20
status == 'active' || role == 'admin'

# String comparisons
name == 'alice'
path.startswith('/api')

# Variable access
user.id > 100
data[0] > 5

# Safe operators (no eval, no function calls)
# Invalid:  exec(), eval(), __import__(), system()
# Valid:    ==, !=, <, >, <=, >=, &&, ||
```

## Event Types

### Tracepoint Hit (snapshot)

Fires when a tracepoint is hit and condition (if any) is true.

```json
{
  "name": "probe.hit.snapshot",
  "payload": {
    "probeId": "tp-1",
    "probeType": "tracepoint",
    "file": "app.py",
    "line": 42,
    "snapshot": {
      "arguments": { "x": 5, "y": 10 },
      "locals": { "result": 15 },
      "returnValue": 15
    },
    "stack": [
      { "file": "app.py", "line": 42, "function": "add" },
      { "file": "main.py", "line": 10, "function": "main" }
    ]
  }
}
```

### Logpoint Hit

Fires when a logpoint is hit with formatted message.

```json
{
  "name": "probe.hit.logpoint",
  "payload": {
    "probeId": "lp-1",
    "probeType": "logpoint",
    "message": "User 123 logged in",
    "messageTemplate": "User {user_id} logged in"
  }
}
```

### Probe Error

Fires when condition evaluation fails.

```json
{
  "name": "probe.error.condition",
  "payload": {
    "probeId": "tp-1",
    "condition": "user.invalid_field > 5",
    "error": "AttributeError: 'User' object has no attribute 'invalid_field'"
  }
}
```

## Rate Limiting

Each probe can have rate limits:

```python
# Default: 10 events per second, burst of 1
limiter = RateLimiter(limit_per_second=10, burst=5)

# Limit to 5 per second, burst of 2
limiter = RateLimiter(limit_per_second=5, burst=2)
```

Events exceeding limits are dropped and reported as `probe.error.rateLimit`.

## Free-Threading Support

Python 3.13+ free-threading mode is detected and supported:

```python
# Agent automatically selects safe engine for FT mode
import sys
if sys.version_info >= (3, 13):
    # May use free-threaded mode
    pass
```

## Framework Integration

### Django

```python
# Add to settings.py
INSTALLED_APPS = [
    # ...
    'tracepointdebug',
]

# Or start manually
from tracepointdebug import start_agent
start_agent()
```

### Flask

```python
from flask import Flask
from tracepointdebug import start_agent

app = Flask(__name__)
agent = start_agent()

@app.route('/')
def index():
    return 'Hello'
```

### FastAPI

```python
from fastapi import FastAPI
from tracepointdebug import start_agent

app = FastAPI()
agent = start_agent()
```

## Troubleshooting

### Agent Won't Start

```bash
# Check event sink is running
curl http://127.0.0.1:4317/health

# Check port is available
lsof -i :5001

# Enable debug logging
DEBUGIN_DEBUG=1 python app.py
```

### Events Not Being Captured

```bash
# Verify tracepoint was created
curl http://127.0.0.1:5001/points

# Check if condition is preventing hits
# Simplify or remove condition temporarily

# Verify event sink is receiving events
curl http://127.0.0.1:4317/api/events
```

### Performance Issues

1. Increase rate limit (more events allowed)
2. Add conditions to limit which code paths are traced
3. Use sampling/burst limiting

## Security Considerations

1. **Default Binding**: Agent binds to `127.0.0.1` by default (localhost only)
2. **Expression Safety**: Conditions are parsed safely without `eval()`
3. **Credential Redaction**: Custom redaction callbacks can mask sensitive data
4. **Event Signing**: Events can be signed for integrity verification

## API Reference

See [docs/PUBLIC_API.md](PUBLIC_API.md) for complete API reference.

## Testing

```bash
# Run all tests
pytest tests/test_python_*.py -v

# Run integration tests
pytest tests/test_python_integration_full.py -v

# Run with coverage
pytest tests/test_python_*.py --cov=tracepointdebug
```

## Examples

See [examples/](../examples/) directory for complete working examples.

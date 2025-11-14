# DebugIn Python Runtime

## Overview

The Python runtime agent (`tracepointdebug`) provides non-breaking tracepoints and dynamic logpoints for Python applications. It supports Python 3.8–3.14 with automatic engine selection and free-threading support for Python 3.13+.

## Installation

```bash
pip install tracepointdebug
```

## Quick Start

```python
import tracepointdebug

# Start the agent with control API enabled
tracepointdebug.start(
    enable_control_api=True,
    control_api_port=5001
)

# Your application code here...
```

## Engine Selection

The agent automatically selects the best trace engine based on your Python version:

| Python Version | Default Engine | Notes |
|---|---|---|
| 3.8–3.10 | Native (C++) | Fast, with pytrace fallback |
| 3.11–3.12 | PyTrace (Pure Python) | Full compatibility |
| 3.13–3.14 (GIL enabled) | PyTrace | Full compatibility |
| 3.13–3.14 (Free-threaded) | PyTrace (forced) | Native not supported in FT mode |

### Override Engine Selection

```bash
# Force native engine
export TRACEPOINTDEBUG_ENGINE=native

# Force pytrace engine
export TRACEPOINTDEBUG_ENGINE=pytrace

# Auto-select (default)
export TRACEPOINTDEBUG_ENGINE=auto
```

## Control API

The Control API runs on `http://127.0.0.1:5001` (configurable).

### Set a Tracepoint

```bash
curl -X POST http://localhost:5001/tracepoints \
  -H "Content-Type: application/json" \
  -d '{
    "file": "app/handlers.py",
    "line": 42,
    "condition": null,
    "tags": ["debug"]
  }'
```

### Set a Logpoint

```bash
curl -X POST http://localhost:5001/logpoints \
  -H "Content-Type: application/json" \
  -d '{
    "file": "app/handlers.py",
    "line": 50,
    "message": "User {user.id} called function with {args[0]}",
    "condition": "args[0] > 100"
  }'
```

### Health Check

```bash
curl http://localhost:5001/health
```

Response:
```json
{
  "status": "healthy",
  "agent": {
    "name": "tracepointdebug",
    "version": "0.3.0",
    "runtime": "python",
    "runtimeVersion": "3.11.0"
  },
  "features": {
    "tracepoints": true,
    "logpoints": true,
    "conditions": true,
    "rateLimit": true,
    "freeThreaded": false
  }
}
```

### List Active Points

```bash
curl http://localhost:5001/points
```

### Enable/Disable Points

```bash
# Enable by ID
curl -X POST http://localhost:5001/points/tp-uuid-1/enable

# Disable by ID
curl -X POST http://localhost:5001/points/tp-uuid-1/disable

# Enable by tag
curl -X POST http://localhost:5001/tags/enable \
  -H "Content-Type: application/json" \
  -d '{"tags": ["debug"]}'

# Disable by tag
curl -X POST http://localhost:5001/tags/disable \
  -H "Content-Type: application/json" \
  -d '{"tags": ["debug"]}'
```

## Configuration

### Environment Variables

```bash
# Control API
export DEBUGIN_CONTROL_API_PORT=5001      # Control API port
export DEBUGIN_CONTROL_API_BIND_ALL=1     # Bind to 0.0.0.0 instead of 127.0.0.1

# Event Sink
export DEBUGIN_EVENT_SINK_URL=http://127.0.0.1:4317

# Broker
export SIDEKICK_BROKER_HOST=broker.example.com
export SIDEKICK_BROKER_PORT=443

# Engine
export TRACEPOINTDEBUG_ENGINE=auto|pytrace|native
```

### Programmatic Configuration

```python
import tracepointdebug

tracepointdebug.start(
    tracepoint_data_redaction_callback=lambda value: "***REDACTED***",
    log_data_redaction_callback=lambda value: "***REDACTED***",
    enable_control_api=True,
    control_api_port=5001
)
```

## Free-Threading Support (Python 3.13+)

The agent automatically detects free-threaded Python and adapts:

```bash
# Build Python 3.13 with free-threading
python3.13 --version --disable-gil

# Agent will auto-select pytrace engine
python3.13 your_app.py
```

The `/health` endpoint reports free-threading status:

```json
{
  "features": {
    "freeThreaded": true
  }
}
```

## Events and Event Sink

All probe events (tracepoint snapshots, logpoint outputs, errors) are sent to the event sink:

```bash
# Start event sink to receive events
python scripts/event_sink.py --port 4317
```

Event types:
- `probe.hit.snapshot` - Tracepoint hit
- `probe.hit.logpoint` - Logpoint hit
- `probe.error.condition` - Condition evaluation failed
- `probe.error.snapshot` - Snapshot capture failed
- `probe.error.rateLimit` - Rate limit exceeded
- `agent.status.started` - Agent started
- `agent.status.stopped` - Agent stopped

## Condition Expressions

Conditions are safe Python expressions evaluated in the local scope:

```
args[0] > 100                    # Check argument
user.status == 'active'          # Check object property
len(items) > 5                   # Check length
message.startswith('ERROR')      # Check string
value is None                    # Check for None
```

### Supported Operators

- **Comparison**: `==`, `!=`, `<`, `<=`, `>`, `>=`
- **Logical**: `and`, `or`, `not`
- **Membership**: `in`, `not in`
- **String methods**: `startswith()`, `endswith()`, `contains()`
- **Type checks**: `isinstance()`

## Rate Limiting

Rate limiting is applied per probe using a token bucket:

```python
{
    "rateLimit": {
        "limitPerSecond": 10,    # Tokens refilled per second
        "burst": 1               # Max tokens that accumulate
    }
}
```

When exceeded, events are dropped and an error event is published.

## Snapshot Configuration

Control snapshot capture depth and size:

```python
{
    "snapshot": {
        "maxDepth": 3,           # Max nesting depth
        "maxProperties": 100,    # Max properties per object
        "maxStringLength": 1024  # Max string length
    }
}
```

## API Reference

See [Control Plane API Specification](control-plane-api.md) for complete endpoint reference.

## Testing

### Unit Tests

```bash
make test-python
# or
pytest tests/
```

### Smoke Tests

```bash
python tests/smoke_test.py
```

### Free-Threading Tests

```bash
python3.13 tests/test_ft_runtime.py
```

## Troubleshooting

### Control API Not Responding

Check if the server started:
```bash
curl http://127.0.0.1:5001/health
```

If not accessible, check:
1. Port is not in use: `lsof -i :5001`
2. Firewall allows local connection
3. DEBUGIN_CONTROL_API_BIND_ALL=1 to bind to 0.0.0.0

### Events Not Arriving at Sink

1. Check event sink is running: `curl http://127.0.0.1:4317/health`
2. Verify DEBUGIN_EVENT_SINK_URL environment variable
3. Check broker connection: `/health` endpoint shows broker status

### Native Engine Crashes

Fallback to pytrace:
```bash
export TRACEPOINTDEBUG_ENGINE=pytrace
```

## Performance

- **Zero overhead** when no probes are active
- **Per-probe overhead** when active: typically <1ms per hit
- **Memory overhead**: ~100KB per active probe

## See Also

- [Control Plane API Specification](control-plane-api.md)
- [Event Schema Specification](event-schema.md)
- [Main README](../README.md)

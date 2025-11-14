# DebugIn Public API Reference

## Overview

This document describes the public API contracts for DebugIn agents across all runtimes. These APIs are stable and should not change without backward compatibility considerations.

---

## Python Public API

### Package: `tracepointdebug`

#### Main Functions

```python
from tracepointdebug import start, stop, __version__
```

##### `start(tracepoint_data_redaction_callback=None, log_data_redaction_callback=None, enable_control_api=True, control_api_port=5001)`

Starts the DebugIn agent.

**Parameters:**
- `tracepoint_data_redaction_callback` (callable, optional): Function to redact sensitive data in snapshots
- `log_data_redaction_callback` (callable, optional): Function to redact sensitive data in logpoints
- `enable_control_api` (bool, default=True): Whether to enable the HTTP control API
- `control_api_port` (int, default=5001): Port for the control API

**Returns:** None

**Raises:** RuntimeError if EVENT_SINK_URL is not configured

**Example:**
```python
import tracepointdebug
tracepointdebug.start(
    enable_control_api=True,
    control_api_port=5001
)
```

##### `stop()`

Stops the DebugIn agent and cleans up resources.

**Parameters:** None

**Returns:** None

**Example:**
```python
import atexit
import tracepointdebug

tracepointdebug.start()
atexit.register(tracepointdebug.stop)
```

##### `__version__`

String constant containing the agent version (e.g., "0.3.0").

**Type:** str

---

### Control API

#### Base URL
```
http://localhost:5001
```

#### Endpoints

All endpoints conform to the [Control Plane API Specification](control-plane-api.md).

**Key Endpoints:**
- `GET /health` - Health check
- `POST /tracepoints` - Create tracepoint
- `POST /logpoints` - Create logpoint
- `GET /points` - List active points
- `POST /points/{id}/enable|disable` - Control point state
- `POST /tags/enable|disable` - Tag-based control

---

## Java Public API

### Agent Attachment

#### Command Line

```bash
java -javaagent:agent-core-0.3.0-all.jar [options] -jar app.jar
```

#### System Properties

Configuration via system properties:

```bash
-Ddebugger.port=5001        # Control API port (default: 5001)
-Ddebugger.host=127.0.0.1   # Control API host (default: 127.0.0.1)
-Ddebugger.enable=true      # Enable/disable agent (default: true)
```

#### Programmatic API

```java
import com.debugin.Agent;
import com.debugin.ControlAPI;

// Check if agent is enabled
boolean enabled = Agent.isEnabled();

// Get control API instance
ControlAPI api = Agent.getControlAPI();
```

---

### Package: `com.debugin`

#### Class: `Agent`

Static utility class for agent lifecycle.

##### `isEnabled()`

Check if the agent is enabled.

**Returns:** boolean

##### `getControlAPI()`

Get the control API instance.

**Returns:** ControlAPI instance, or null if not available

---

### Control API

#### Base URL

```
http://localhost:5001
```

#### Endpoints

Same as Python implementation (see [Control Plane API Specification](control-plane-api.md)).

---

## Node.js Public API

### Package: `tracepointdebug`

#### Main Functions

```javascript
const debugin = require('tracepointdebug');
```

##### `start(options = {})`

Starts the DebugIn agent.

**Parameters:**
- `options` (Object, optional):
  - `controlApiPort` (number, default: 5001): Control API port
  - `controlApiHost` (string, default: 127.0.0.1): Control API host
  - `eventSinkUrl` (string, default: http://127.0.0.1:4317): Event sink URL
  - `brokerUrl` (string, optional): Broker URL
  - `redactTracepoint` (function, optional): Tracepoint redaction callback
  - `redactLogpoint` (function, optional): Logpoint redaction callback

**Returns:** Agent instance (or null if failed)

**Example:**
```javascript
const debugin = require('tracepointdebug');
const agent = debugin.start({
    controlApiPort: 5001,
    controlApiHost: '127.0.0.1'
});
```

##### `stop()`

Stops the DebugIn agent.

**Parameters:** None

**Returns:** None

**Example:**
```javascript
debugin.stop();
```

##### `getInstance()`

Get the current agent instance.

**Returns:** Agent instance, or null if not started

**Example:**
```javascript
const agent = debugin.getInstance();
if (agent && agent.isRunning()) {
    console.log('Agent is running');
}
```

---

### Agent Instance Methods

If `start()` returns an agent instance:

#### `setTracepoint(file, line, condition, config = {})`

Create a tracepoint programmatically.

**Parameters:**
- `file` (string): File path
- `line` (number): Line number
- `condition` (string, optional): Condition expression
- `config` (Object, optional): Additional configuration

**Returns:** string (point ID)

#### `setLogpoint(file, line, message, condition, config = {})`

Create a logpoint programmatically.

**Parameters:**
- `file` (string): File path
- `line` (number): Line number
- `message` (string): Message template
- `condition` (string, optional): Condition expression
- `config` (Object, optional): Additional configuration

**Returns:** string (point ID)

#### `getPoints()`

Get all active points.

**Returns:** Array of point objects

#### `removePoint(pointId)`

Remove a point by ID.

**Parameters:**
- `pointId` (string): Point ID

#### `isRunning()`

Check if agent is running.

**Returns:** boolean

---

### Control API

#### Base URL

```
http://localhost:5001
```

#### Endpoints

Same as Python and Java implementations (see [Control Plane API Specification](control-plane-api.md)).

---

## Configuration via Environment Variables

All runtimes support configuration via environment variables:

```bash
# Control API configuration
export DEBUGIN_CONTROL_API_PORT=5001
export DEBUGIN_CONTROL_API_HOST=127.0.0.1

# Allow binding to 0.0.0.0 instead of 127.0.0.1
export DEBUGIN_CONTROL_API_BIND_ALL=1

# Event sink configuration
export DEBUGIN_EVENT_SINK_URL=http://127.0.0.1:4317

# Broker configuration
export DEBUGIN_BROKER_URL=wss://broker.example.com:443

# Python-specific
export TRACEPOINTDEBUG_ENGINE=auto|pytrace|native
```

---

## Stability Guarantees

### Stable (Will not change without major version)

- Python `start()`, `stop()` functions
- Java `-javaagent` command line
- All Control API endpoints (request/response format)
- Event schema format

### Experimental (May change)

- Internal manager classes (not in public docs)
- Engine selection logic (Python)
- Bytecode instrumentation details (Java)
- Module instrumentation approach (Node.js)

---

## Backward Compatibility

- Control API endpoints will maintain backward compatibility within major versions
- Event schema will not change structure (only additions allowed)
- Configuration keys will not be removed

---

## Migration Guide

### From 0.2.x to 0.3.0

- Python: API unchanged
- Java: System property names may have changed (see docs)
- Node.js: First stable public release

---

## See Also

- [Control Plane API Specification](control-plane-api.md)
- [Event Schema Specification](event-schema.md)
- [Python Runtime Guide](PYTHON.md)
- [Java Agent Guide](JAVA.md)
- [Node.js Agent Guide](NODE.md)

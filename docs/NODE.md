# DebugIn Node.js Agent

## Overview

The Node.js agent provides non-breaking tracepoints and dynamic logpoints for Node.js applications. It supports Node 14, 16, 18, 20, and 22.

**Status**: Implementation in progress. Currently a reference implementation with test plans; full functionality under development.

## Installation

```bash
npm install tracepointdebug
```

Or from git (development):

```bash
npm install github:debugin/debugin#main
```

## Quick Start

```javascript
const debugin = require('tracepointdebug');

// Start the agent with control API enabled
debugin.start({
    controlApiPort: 5001,
    controlApiHost: '127.0.0.1',
    eventSinkUrl: 'http://127.0.0.1:4317'
});

// Your application code here...
```

## Control API

The Control API runs on `http://127.0.0.1:5001` (configurable).

### Set a Tracepoint

```bash
curl -X POST http://localhost:5001/tracepoints \
  -H "Content-Type: application/json" \
  -d '{
    "file": "src/handlers.js",
    "line": 42,
    "condition": null,
    "tags": ["debug"]
  }'
```

Response (201 Created):
```json
{
  "id": "uuid-1",
  "type": "tracepoint",
  "file": "src/handlers.js",
  "line": 42,
  "enabled": true,
  "created": "2025-01-01T12:00:00Z",
  "condition": null
}
```

### Set a Logpoint

```bash
curl -X POST http://localhost:5001/logpoints \
  -H "Content-Type: application/json" \
  -d '{
    "file": "src/handlers.js",
    "line": 50,
    "message": "User {user.id} called with {args[0]}",
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
    "runtime": "node",
    "runtimeVersion": "18.0.0"
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
curl -X POST http://localhost:5001/points/uuid-1/enable

# Disable by ID
curl -X POST http://localhost:5001/points/uuid-1/disable

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

### Programmatic Configuration

```javascript
const debugin = require('tracepointdebug');

debugin.start({
    controlApiPort: 5001,
    controlApiHost: '127.0.0.1',
    eventSinkUrl: 'http://127.0.0.1:4317',
    brokerUrl: 'wss://broker.example.com:443',

    // Data redaction callbacks
    redactTracepoint: (value) => '***REDACTED***',
    redactLogpoint: (value) => '***REDACTED***'
});

// Later: stop the agent
debugin.stop();
```

### Environment Variables

```bash
export DEBUGIN_CONTROL_API_PORT=5001
export DEBUGIN_CONTROL_API_HOST=127.0.0.1
export DEBUGIN_CONTROL_API_BIND_ALL=1        # Bind to 0.0.0.0
export DEBUGIN_EVENT_SINK_URL=http://127.0.0.1:4317
export DEBUGIN_BROKER_URL=wss://broker.example.com:443
```

## Usage with Express

```javascript
const express = require('express');
const debugin = require('tracepointdebug');

// Start agent early
debugin.start();

const app = express();

app.get('/api/users/:id', (req, res) => {
    // Line 15 could have a tracepoint
    const userId = req.params.id;

    // Your handler logic...

    res.json({ id: userId });
});

app.listen(3000);
```

Set a tracepoint:
```bash
curl -X POST http://localhost:5001/tracepoints \
  -H "Content-Type: application/json" \
  -d '{
    "file": "src/server.js",
    "line": 15,
    "condition": "userId > 100"
  }'
```

## Usage with Fastify

```javascript
const fastify = require('fastify')();
const debugin = require('tracepointdebug');

debugin.start();

fastify.get('/api/users/:id', async (request, reply) => {
    const userId = request.params.id;  // Line 11
    // Your handler logic...
    return { id: userId };
});

fastify.listen({ port: 3000 });
```

## Events

All probe events are sent to the event sink at `http://127.0.0.1:4317` (configurable).

Event types:
- `probe.hit.snapshot` - Tracepoint hit with variable snapshot
- `probe.hit.logpoint` - Logpoint message output
- `probe.error.condition` - Condition evaluation error
- `probe.error.snapshot` - Snapshot capture error
- `probe.error.rateLimit` - Rate limit exceeded
- `agent.status.started` - Agent initialized
- `agent.status.stopped` - Agent shutdown

### Event Sink Example

```bash
# Start event sink
python scripts/event_sink.py --port 4317

# Events will be logged as they arrive
```

## Condition Expressions

Conditions are evaluated as safe JavaScript expressions:

```
args[0] > 100                     // Check argument
user.id === "admin"               // Check property
items.length > 5                  // Check array length
message.startsWith('ERROR')       // String method
value !== null                    // Null check
typeof value === 'string'         // Type check
```

### Supported Operations

- **Comparison**: `==`, `!=`, `===`, `!==`, `<`, `<=`, `>`, `>=`
- **Logical**: `&&`, `||`, `!`
- **Arithmetic**: `+`, `-`, `*`, `/`, `%`
- **Member access**: `object.property`, `array[0]`
- **Method calls**: `.length()`, `.startsWith()`, etc.
- **Type checks**: `typeof value`

### Safe Evaluation

Conditions are evaluated with restricted context:
- No access to `eval()`, `Function()`
- No access to global objects (`process`, `require`, etc.)
- Errors are caught and reported

## Rate Limiting

Control event frequency per probe:

```json
{
  "rateLimit": {
    "limitPerSecond": 10,    // Tokens per second
    "burst": 1               // Max burst
  }
}
```

## Snapshot Configuration

Control what variables are captured:

```json
{
  "snapshot": {
    "maxDepth": 3,           // Nesting depth
    "maxProperties": 100,    // Properties per object
    "maxStringLength": 1024  // String truncation
  }
}
```

## Instrumentation

The agent instruments:
- **Function calls**: Entry/exit, arguments, return values
- **Line execution**: Local variables at specified lines
- **Exception handling**: Error objects and stacks
- **Async/await**: Promise resolution tracking

### Limitations

- **Current**: Require-time instrumentation (needs to wrap target modules)
- **Planned**: V8 Inspector Protocol (CDP) for dynamic instrumentation
- **Excluded**: Native modules, built-in Node.js modules

## Testing

### Unit Tests

```bash
npm test
# or
node tests/node_test_plan.js
```

### Test Fixture

```bash
npm install
node tests/fixtures/node_app.js
```

## Troubleshooting

### Agent Not Initialized

Ensure `debugin.start()` is called at application startup:

```javascript
// Good: Call immediately
const debugin = require('tracepointdebug');
debugin.start();

const express = require('express');
// Rest of app...

// Bad: Called too late
const express = require('express');
const app = express();
// ... app setup ...
const debugin = require('tracepointdebug');
debugin.start();  // Too late!
```

### Control API Not Responding

Check if the server started:
```bash
curl http://127.0.0.1:5001/health
```

If not accessible:
1. Check port is free: `lsof -i :5001`
2. Override port: `debugin.start({ controlApiPort: 5002 })`
3. Bind to all interfaces: `export DEBUGIN_CONTROL_API_BIND_ALL=1`

### Events Not Reaching Sink

1. Verify sink is running: `curl http://127.0.0.1:4317/health`
2. Check configuration: `curl http://localhost:5001/health`
3. Check logs: `DEBUG=tracepointdebug:* node app.js`

### Snapshot Errors

Some objects cannot be serialized (e.g., functions, circular references):

- Functions are shown as `[Function: name]`
- Circular references are truncated at max depth
- Large objects are summarized

To avoid serialization issues, use conditions to filter data:

```bash
# Only snapshot when userId is a number
curl -X POST http://localhost:5001/tracepoints \
  -d '{
    "file": "src/handlers.js",
    "line": 42,
    "condition": "typeof userId === \"number\""
  }'
```

## Performance

- **Agent startup overhead**: ~50–100ms
- **Per-probe overhead**: typically <1ms per hit
- **Memory**: ~30MB for agent, ~5KB per active probe

## Framework-Specific Guides

### Express

See [Usage with Express](#usage-with-express) above.

### Fastify

See [Usage with Fastify](#usage-with-fastify) above.

### Hapi

```javascript
const Hapi = require('@hapi/hapi');
const debugin = require('tracepointdebug');

debugin.start();

const server = Hapi.server({
    port: 3000,
    host: 'localhost'
});

server.route({
    method: 'GET',
    path: '/api/users/{id}',
    handler: (request, h) => {
        const userId = request.params.id;  // Line 18
        return { id: userId };
    }
});

server.start();
```

### Next.js

```javascript
// pages/api/users/[id].js

import debugin from 'tracepointdebug';

// Start agent in global scope (once)
if (typeof window === 'undefined') {
    debugin.start();
}

export default function handler(req, res) {
    const { id } = req.query;  // Line 13
    res.status(200).json({ id });
}
```

## Advanced: Custom Instrumentation

For custom probe management (future feature):

```javascript
// Programmatic API (planned)
import { DebugIn } from 'tracepointdebug';

DebugIn.setTracepoint('src/handlers.js', 42);
DebugIn.setLogpoint('src/handlers.js', 50, 'User {userId}');
```

## See Also

- [Control Plane API Specification](control-plane-api.md)
- [Event Schema Specification](event-schema.md)
- [Main README](../README.md)
- [Node.js Agent Source](../lib)

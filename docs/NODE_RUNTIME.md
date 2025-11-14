# Node.js Runtime Guide

Complete guide to using the DebugIn Node.js agent for dynamic debugging.

## Installation

```bash
npm install debugin-agent
```

## Quick Start

### 1. Require Agent

```javascript
// At the top of your app, before other requires
require('debugin-agent').start({
  controlApiPort: 5003,
  eventSinkUrl: 'http://127.0.0.1:4317'
});

// Rest of your app
const express = require('express');
const app = express();
```

### 2. Create Tracepoint via HTTP

```bash
curl -X POST http://127.0.0.1:5003/tracepoints \
  -H "Content-Type: application/json" \
  -d '{
    "file": "handlers/user.js",
    "line": 42,
    "condition": "userId > 100"
  }'
```

### 3. Application Executes, Breakpoint Fires

When your code hits line 42 with matching condition, the agent captures:
- Function arguments
- Local variables
- Return value
- Call stack (V8 stack trace)

### 4. Event Sent to Event Sink

```json
{
  "name": "probe.hit.snapshot",
  "payload": {
    "probeId": "tp-node-1",
    "probeType": "tracepoint",
    "file": "handlers/user.js",
    "line": 42,
    "snapshot": {
      "arguments": { "userId": 150 },
      "locals": { "session": "abc123" },
      "returnValue": { "status": "ok" }
    }
  }
}
```

## Configuration

### Environment Variables

```bash
# Control API port (default: 5003)
export DEBUGIN_CONTROL_API_PORT=5003

# Control API host (default: 127.0.0.1)
export DEBUGIN_CONTROL_API_HOST=127.0.0.1

# Event sink URL (default: http://127.0.0.1:4317)
export DEBUGIN_EVENT_SINK_URL=http://event-sink:4317
```

### Programmatic Configuration

```javascript
const agent = require('debugin-agent').start({
  controlApiPort: 5003,
  controlApiHost: '127.0.0.1',
  eventSinkUrl: 'http://127.0.0.1:4317'
});
```

## Control API Endpoints

### Health Check

```bash
GET http://localhost:5003/health
```

Response:
```json
{
  "status": "healthy",
  "version": "0.3.0",
  "features": {
    "tracepoints": true,
    "logpoints": true,
    "conditions": true,
    "rateLimit": true
  }
}
```

### Create Tracepoint

```bash
POST http://localhost:5003/tracepoints

{
  "file": "app.js",
  "line": 42,
  "condition": "x > 10",
  "tags": ["debug"]
}
```

Response: `201 Created`

### Create Logpoint

```bash
POST http://localhost:5003/logpoints

{
  "file": "app.js",
  "line": 50,
  "message": "Processing user {userId} with balance {balance}"
}
```

### List Points

```bash
GET http://localhost:5003/points
```

### Enable/Disable Points

```bash
POST /points/:id/enable
POST /points/:id/disable

DELETE /points/:id
```

### Tag Management

```bash
POST /tags/enable
{ "tags": ["debug"] }

POST /tags/disable
{ "tags": ["production"] }
```

## Condition Expression Language

Conditions use safe JavaScript-like expressions:

```javascript
// Numeric comparisons
x > 10
count <= 5
value == 100

// String comparisons
name == 'alice'
status != 'inactive'

// Logical operators
x > 10 && y < 20
status == 'active' || role == 'admin'

// Variable access
user.id > 100
data[0] > 5
items.length > 3

// Safe math
count * 2 > 100
price + tax < 1000

// Array/Object methods
names.includes('alice')
Object.keys(data).length > 0

// NOT allowed (blocked for security)
eval(), Function(), require(), process, exec, spawn
```

## Event Types

### Tracepoint Hit (Snapshot)

```json
{
  "name": "probe.hit.snapshot",
  "payload": {
    "probeId": "tp-node-1",
    "probeType": "tracepoint",
    "file": "handler.js",
    "line": 42,
    "snapshot": {
      "arguments": { "userId": 150, "request": {...} },
      "locals": { "result": "computed" },
      "returnValue": { "status": "ok" }
    },
    "stack": [
      { "file": "handler.js", "line": 42, "function": "handleUser" },
      { "file": "server.js", "line": 15, "function": "routeRequest" }
    ]
  }
}
```

### Logpoint Hit

```json
{
  "name": "probe.hit.logpoint",
  "payload": {
    "probeId": "lp-node-1",
    "probeType": "logpoint",
    "file": "handler.js",
    "line": 50,
    "message": "User 123 logged in",
    "messageTemplate": "User {userId} logged in"
  }
}
```

## Rate Limiting

Each probe has rate limiting:

```javascript
const agent = require('debugin-agent');

// Default: 10 events per second, burst of 1
// Can be configured per probe via Control API

// When limit exceeded: events dropped, error event sent
```

## Framework Integration

### Express.js

```javascript
require('debugin-agent').start();

const express = require('express');
const app = express();

app.get('/users/:id', (req, res) => {
  // Agent can trace code in route handlers
  const user = getUser(req.params.id);
  res.json(user);
});

app.listen(3000);
```

### Fastify

```javascript
require('debugin-agent').start();

const fastify = require('fastify')();

fastify.get('/users/:id', async (request, reply) => {
  const user = await getUser(request.params.id);
  return user;
});

fastify.listen({ port: 3000 });
```

### Hapi

```javascript
require('debugin-agent').start();

const Hapi = require('@hapi/hapi');

const server = Hapi.server({
  port: 3000,
  host: 'localhost'
});

server.route({
  method: 'GET',
  path: '/users/{id}',
  handler: (request, h) => {
    return getUser(request.params.id);
  }
});

server.start();
```

### Next.js

```javascript
// pages/api/users/[id].js
require('debugin-agent').start();

export default async (req, res) => {
  const { id } = req.query;
  const user = await getUser(id);
  res.status(200).json(user);
};
```

## Troubleshooting

### Agent Won't Start

```bash
# Check Node version
node --version  # Should be 14+

# Check if port is available
lsof -i :5003

# Enable debug logging
DEBUG=debugin:* node app.js
```

### Events Not Being Captured

```bash
# Verify tracepoint was created
curl http://127.0.0.1:5003/points

# Check condition syntax
# Run: curl -X POST http://localhost:5003/tracepoints -d '{...}'

# Verify event sink is running
curl http://127.0.0.1:4317/health
```

### Performance Issues

1. Increase rate limit (more events allowed)
2. Add conditions to limit traced code paths
3. Use sampling/burst limiting

## Security Considerations

1. **Default Binding**: Agent binds to `127.0.0.1` (localhost only)
2. **Expression Safety**: Conditions evaluated in restricted sandbox
3. **No Code Injection**: Blocked dangerous functions/keywords
4. **Memory Safe**: Snapshots have depth/breadth limits

## Testing

```bash
# Run all Node tests
npm test

# Run with coverage
npm test -- --coverage

# Run specific test file
node tests/test_nodejs_comprehensive.js
```

## Performance Tips

- Conditions reduce overhead by filtering unnecessary events
- Logpoints are lighter than snapshots
- Use tags to control which probes are active
- Rate limiting prevents performance degradation

## Limits

- **Maximum Snapshot Depth**: 10 levels
- **Maximum Collection Size**: 1000 items
- **Maximum Message Length**: 10KB
- **Default Rate Limit**: 10 events/sec, burst 1

## API Reference

See [docs/PUBLIC_API.md](PUBLIC_API.md) for complete API reference.

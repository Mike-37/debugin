# DebugIn Control Plane API Specification

## Overview

The Control Plane API is a **REST/HTTP interface** that allows dynamic configuration of tracepoints, logpoints, and other runtime debugging features. This specification defines the canonical API that all runtime agents (Python, Java, Node.js) must implement.

**Default Configuration:**
- **Port**: 5001 (configurable per runtime)
- **Base URL**: `http://localhost:5001`
- **Content-Type**: `application/json`

---

## Core Concepts

### Probe Types

1. **Tracepoint**: A non-breaking breakpoint that captures a snapshot of local/instance variables when a code location is hit.
2. **Logpoint**: A dynamic logging point that executes a template expression and outputs a message when code is hit.

### Probe Model

All probes share a common data model:

```json
{
  "id": "uuid-string",
  "type": "tracepoint|logpoint",
  "file": "path/to/file.py|file.java|file.js",
  "line": 42,
  "condition": null | "expression",
  "tags": ["tag1", "tag2"],
  "enabled": true,
  "rateLimit": {
    "limitPerSecond": 10,
    "burst": 1
  },
  "snapshot": {
    "maxDepth": 3,
    "maxProperties": 100,
    "maxStringLength": 1024
  }
}
```

### Logpoint-Specific Fields

For logpoints only:

```json
{
  "message": "User {user.name} called function with args {args[0]}",
  "condition": "args[0] > 100"
}
```

---

## Endpoints

### 1. Health Check

**Endpoint:** `GET /health`

**Description:** Returns the health status of the agent and connected services.

**Response (200 OK):**
```json
{
  "status": "healthy",
  "agent": {
    "name": "tracepointdebug",
    "version": "0.3.0",
    "runtime": "python|java|node",
    "runtimeVersion": "3.11|8|18"
  },
  "features": {
    "tracepoints": true,
    "logpoints": true,
    "conditions": true,
    "rateLimit": true,
    "freeThreaded": false
  },
  "broker": {
    "connected": true,
    "url": "wss://broker.example.com:443"
  },
  "eventSink": {
    "connected": true,
    "url": "http://127.0.0.1:4317"
  },
  "uptime": 3600
}
```

---

### 2. List All Points

**Endpoint:** `GET /points`

**Query Parameters:**
- `type`: Filter by type (`tracepoint`, `logpoint`, or omit for all)
- `enabled`: Filter by enabled status (`true`, `false`, or omit for all)
- `tag`: Filter by tag (can be repeated)

**Example:**
```bash
GET /points?type=tracepoint&enabled=true
```

**Response (200 OK):**
```json
{
  "points": [
    {
      "id": "uuid-1",
      "type": "tracepoint",
      "file": "app.py",
      "line": 42,
      "enabled": true,
      "hitCount": 5,
      "tags": ["debug"]
    }
  ],
  "total": 1
}
```

---

### 3. Create Tracepoint

**Endpoint:** `POST /tracepoints`

**Request Body:**
```json
{
  "file": "app.py",
  "line": 42,
  "condition": null,
  "tags": ["feature-x"],
  "snapshot": {
    "maxDepth": 3,
    "maxProperties": 100
  }
}
```

**Response (201 Created):**
```json
{
  "id": "uuid-1",
  "type": "tracepoint",
  "file": "app.py",
  "line": 42,
  "condition": null,
  "enabled": true,
  "tags": ["feature-x"],
  "created": "2025-01-01T12:00:00Z",
  "snapshot": {
    "maxDepth": 3,
    "maxProperties": 100
  }
}
```

**Error Responses:**

- **400 Bad Request**: Invalid file/line, missing required fields
```json
{
  "error": "Invalid line number: line must be >= 1",
  "code": "INVALID_LINE"
}
```

- **404 Not Found**: File not found or not in target application
```json
{
  "error": "File not found: unknown.py",
  "code": "FILE_NOT_FOUND"
}
```

---

### 4. Create Logpoint

**Endpoint:** `POST /logpoints`

**Request Body:**
```json
{
  "file": "app.py",
  "line": 42,
  "message": "User {user.id} hit line 42 with value {value}",
  "condition": "value > 100",
  "tags": ["logging"],
  "rateLimit": {
    "limitPerSecond": 10,
    "burst": 1
  }
}
```

**Response (201 Created):**
```json
{
  "id": "uuid-2",
  "type": "logpoint",
  "file": "app.py",
  "line": 42,
  "message": "User {user.id} hit line 42 with value {value}",
  "condition": "value > 100",
  "enabled": true,
  "tags": ["logging"],
  "created": "2025-01-01T12:00:00Z",
  "rateLimit": {
    "limitPerSecond": 10,
    "burst": 1
  }
}
```

**Error Responses:** Same as tracepoint, plus:

- **422 Unprocessable Entity**: Invalid condition expression or message template
```json
{
  "error": "Invalid condition: unknown variable 'x'",
  "code": "INVALID_CONDITION"
}
```

---

### 5. Update Point

**Endpoint:** `PUT /points/{id}`

**Request Body:** (partial update)
```json
{
  "condition": "new_condition",
  "enabled": false,
  "tags": ["new-tag"]
}
```

**Response (200 OK):** Updated point object

**Error Responses:**
- **404 Not Found**: Point ID does not exist

---

### 6. Enable Point

**Endpoint:** `POST /points/{id}/enable`

**Response (200 OK):**
```json
{
  "id": "uuid-1",
  "enabled": true,
  "message": "Point enabled"
}
```

---

### 7. Disable Point

**Endpoint:** `POST /points/{id}/disable`

**Response (200 OK):**
```json
{
  "id": "uuid-1",
  "enabled": false,
  "message": "Point disabled"
}
```

---

### 8. Delete Point

**Endpoint:** `DELETE /points/{id}`

**Response (204 No Content)**

---

### 9. Tag Management: Enable by Tag

**Endpoint:** `POST /tags/enable`

**Request Body:**
```json
{
  "tags": ["feature-x"]
}
```

**Response (200 OK):**
```json
{
  "enabled": 3,
  "message": "3 points enabled"
}
```

---

### 10. Tag Management: Disable by Tag

**Endpoint:** `POST /tags/disable`

**Request Body:**
```json
{
  "tags": ["feature-x"]
}
```

**Response (200 OK):**
```json
{
  "disabled": 3,
  "message": "3 points disabled"
}
```

---

## Condition Expression Language

Conditions are evaluated as boolean expressions over the local scope. The following operators are supported:

### Operators
- **Comparison**: `==`, `!=`, `<`, `<=`, `>`, `>=`
- **Logical**: `&&` (AND), `||` (OR), `!` (NOT)
- **String operations**: `contains`, `startsWith`, `endsWith`, `matches` (regex)
- **Arithmetic**: `+`, `-`, `*`, `/`, `%`

### Scope Variables
- `args` - Array of function arguments
- `this` / `self` - The instance (if in instance method)
- `locals` - All local variables (access as `locals.var_name`)
- Direct variable access: `user.name`, `list[0]`, etc.

### Examples

```
condition: "args[0] > 100"
condition: "user.status == 'active'"
condition: "message.contains('error')"
condition: "!(enabled && status)"
condition: "response.code >= 400"
```

---

## Event Publishing

When a probe is hit:

1. **Tracepoint**: Snapshot event is published to the event sink
2. **Logpoint**: Message is formatted and published as log event

Events are sent to the configured **Event Sink** (default: `http://127.0.0.1:4317`).

Event schema: See `docs/event-schema.md`

---

## Rate Limiting

Rate limiting is applied **per probe instance** using a **token bucket algorithm**.

```json
"rateLimit": {
  "limitPerSecond": 10,    // Tokens refilled per second
  "burst": 1               // Maximum tokens that can accumulate
}
```

When rate limit is exceeded:
- Event is **dropped**
- A **rate limit error** event is published to the sink
- The dropped event count is incremented

---

## Error Handling

All errors return a standardized error response:

```json
{
  "error": "Human-readable message",
  "code": "MACHINE_READABLE_CODE",
  "details": {
    "key": "value"
  }
}
```

### HTTP Status Codes

| Status | Meaning |
|--------|---------|
| 200 | OK - Request succeeded |
| 201 | Created - Resource created |
| 204 | No Content - Deletion succeeded |
| 400 | Bad Request - Invalid input |
| 404 | Not Found - Resource not found |
| 422 | Unprocessable Entity - Validation failed |
| 500 | Internal Server Error - Server error |

---

## Configuration

### Environment Variables

All runtimes should support configuration via environment variables:

- `DEBUGIN_CONTROL_API_PORT`: Port to bind control API (default: 5001)
- `DEBUGIN_CONTROL_API_HOST`: Host to bind to (default: `127.0.0.1`)
- `DEBUGIN_EVENT_SINK_URL`: Event sink URL (default: `http://127.0.0.1:4317`)
- `DEBUGIN_BROKER_URL`: Broker URL (default: varies per runtime)
- `DEBUGIN_AGENT_TAGS`: Comma-separated tags for this agent instance

---

## Implementation Checklist

For each runtime (Python, Java, Node.js):

- [ ] All endpoints implemented and returning correct status codes
- [ ] Condition expression evaluation with safe execution context
- [ ] Rate limiting per probe instance
- [ ] Event publishing to sink in canonical format
- [ ] Error handling with standardized error responses
- [ ] Integration tests covering all endpoints
- [ ] Thread-safe / async-safe for all operations

---

## See Also

- [Event Schema Specification](event-schema.md)
- [Python Implementation](../tracepointdebug/control_api.py)
- [Test Plans](../tests/python_test_plan.py)

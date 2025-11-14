# DebugIn Event Schema Specification

## Overview

The Event Schema defines the canonical format for all events published by the DebugIn agent to the event sink. All runtime implementations (Python, Java, Node.js) must emit events conforming to this schema.

**Event Sink Endpoint**: `http://127.0.0.1:4317` (configurable via `DEBUGIN_EVENT_SINK_URL`)

---

## Base Event Structure

All events share a common envelope:

```json
{
  "name": "event_type",
  "timestamp": "2025-01-01T12:00:00.000Z",
  "id": "unique-event-id-uuid",
  "client": {
    "hostname": "my-host",
    "applicationName": "my-app",
    "applicationInstanceId": "instance-1",
    "agentVersion": "0.3.0",
    "runtime": "python|java|node",
    "runtimeVersion": "3.11|8|18"
  },
  "payload": {
    // Event-specific payload
  }
}
```

### Base Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Event type identifier |
| `timestamp` | ISO 8601 | Yes | When event occurred |
| `id` | UUID v4 | Yes | Unique event identifier |
| `client` | object | Yes | Client/agent metadata |
| `payload` | object | Yes | Event-specific data |

---

## Event Types

### 1. ProbeHit - Tracepoint Snapshot

**Event Name**: `probe.hit.snapshot`

**Triggered when**: A tracepoint is hit and condition (if any) evaluates to true.

**Full Event Example:**

```json
{
  "name": "probe.hit.snapshot",
  "timestamp": "2025-01-01T12:00:00.123Z",
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "client": {
    "hostname": "dev-machine",
    "applicationName": "my-api",
    "applicationInstanceId": "pod-1",
    "agentVersion": "0.3.0",
    "runtime": "python",
    "runtimeVersion": "3.11"
  },
  "payload": {
    "probeId": "tp-uuid-1",
    "probeType": "tracepoint",
    "file": "app/handlers.py",
    "line": 42,
    "method": "handle_request",
    "className": "RequestHandler",
    "condition": null,
    "conditionEvaluated": true,
    "snapshot": {
      "locals": {
        "user_id": 123,
        "request": {
          "method": "GET",
          "path": "/api/users",
          "__tpd_type__": "Request"
        },
        "items": [1, 2, 3, 4, 5]
      },
      "arguments": {
        "self": {
          "__tpd_type__": "RequestHandler"
        },
        "request": {
          "__tpd_type__": "Request"
        }
      },
      "returnValue": null,
      "exception": null
    },
    "stack": [
      {
        "file": "app/handlers.py",
        "line": 42,
        "method": "handle_request",
        "className": "RequestHandler"
      },
      {
        "file": "app/routes.py",
        "line": 15,
        "method": "route_request"
      }
    ],
    "hitCount": 1,
    "totalHits": 5,
    "rateLimit": {
      "allowedThisSecond": 9,
      "dropped": 0
    }
  }
}
```

**Payload Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `probeId` | UUID | Unique ID of the tracepoint |
| `probeType` | string | "tracepoint" |
| `file` | string | Source file path |
| `line` | integer | Line number |
| `method` | string | Method/function name |
| `className` | string | Class name (if applicable) |
| `condition` | string \| null | The condition expression (if any) |
| `conditionEvaluated` | boolean | Whether condition was evaluated |
| `snapshot` | object | Captured variables (see below) |
| `stack` | array | Call stack frames |
| `hitCount` | integer | Hits in this session |
| `totalHits` | integer | Total hits since agent start |
| `rateLimit` | object | Rate limit statistics |

**Snapshot Object:**

```json
{
  "locals": {
    "variable_name": "value",
    "nested_object": {
      "field": "value"
    }
  },
  "arguments": {
    "arg_name": "value"
  },
  "returnValue": "value_or_null",
  "exception": null | {
    "type": "Exception",
    "message": "error message",
    "stack": "traceback..."
  }
}
```

---

### 2. ProbeHit - Logpoint

**Event Name**: `probe.hit.logpoint`

**Triggered when**: A logpoint is hit and condition (if any) evaluates to true.

**Full Event Example:**

```json
{
  "name": "probe.hit.logpoint",
  "timestamp": "2025-01-01T12:00:00.456Z",
  "id": "550e8400-e29b-41d4-a716-446655440001",
  "client": {
    "hostname": "dev-machine",
    "applicationName": "my-api",
    "agentVersion": "0.3.0",
    "runtime": "python",
    "runtimeVersion": "3.11"
  },
  "payload": {
    "probeId": "lp-uuid-1",
    "probeType": "logpoint",
    "file": "app/handlers.py",
    "line": 50,
    "method": "process_data",
    "className": "DataProcessor",
    "condition": "value > 100",
    "conditionEvaluated": true,
    "conditionResult": true,
    "message": "Processing value 150 for user user-123",
    "messageTemplate": "Processing value {value} for user {user.id}",
    "hitCount": 1,
    "totalHits": 12,
    "rateLimit": {
      "allowedThisSecond": 9,
      "dropped": 0
    }
  }
}
```

**Payload Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `probeId` | UUID | Unique ID of the logpoint |
| `probeType` | string | "logpoint" |
| `file` | string | Source file path |
| `line` | integer | Line number |
| `method` | string | Method/function name |
| `className` | string | Class name (if applicable) |
| `condition` | string \| null | The condition expression |
| `conditionEvaluated` | boolean | Whether condition was evaluated |
| `conditionResult` | boolean | Result of condition evaluation |
| `message` | string | Formatted log message |
| `messageTemplate` | string | Original template with placeholders |
| `hitCount` | integer | Hits in this session |
| `totalHits` | integer | Total hits since agent start |
| `rateLimit` | object | Rate limit statistics |

---

### 3. ProbeError - Condition Evaluation Failure

**Event Name**: `probe.error.condition`

**Triggered when**: A condition expression fails to evaluate.

```json
{
  "name": "probe.error.condition",
  "timestamp": "2025-01-01T12:00:00.789Z",
  "id": "550e8400-e29b-41d4-a716-446655440002",
  "client": { /* ... */ },
  "payload": {
    "probeId": "tp-uuid-1",
    "probeType": "tracepoint",
    "file": "app/handlers.py",
    "line": 42,
    "condition": "user.invalid_field > 5",
    "error": "NameError: name 'user' is not defined",
    "errorType": "NameError",
    "errorStack": "Traceback ..."
  }
}
```

---

### 4. ProbeError - Snapshot Capture Failure

**Event Name**: `probe.error.snapshot`

**Triggered when**: Snapshot capture fails (e.g., non-serializable objects).

```json
{
  "name": "probe.error.snapshot",
  "timestamp": "2025-01-01T12:00:00.890Z",
  "id": "550e8400-e29b-41d4-a716-446655440003",
  "client": { /* ... */ },
  "payload": {
    "probeId": "tp-uuid-1",
    "probeType": "tracepoint",
    "file": "app/handlers.py",
    "line": 42,
    "error": "Failed to serialize variable 'file_handle': cannot serialize file object",
    "errorType": "SerializationError",
    "failedVariable": "file_handle",
    "attemptedValue": "<_io.FileIO name='file.txt' mode='rb'>"
  }
}
```

---

### 5. ProbeError - Rate Limit Exceeded

**Event Name**: `probe.error.rateLimit`

**Triggered when**: A probe hits the rate limit and an event is dropped.

```json
{
  "name": "probe.error.rateLimit",
  "timestamp": "2025-01-01T12:00:01.000Z",
  "id": "550e8400-e29b-41d4-a716-446655440004",
  "client": { /* ... */ },
  "payload": {
    "probeId": "tp-uuid-1",
    "probeType": "tracepoint",
    "file": "app/handlers.py",
    "line": 42,
    "limit": {
      "limitPerSecond": 10,
      "burst": 1
    },
    "droppedCount": 5,
    "message": "Rate limit exceeded: dropped 5 events"
  }
}
```

---

### 6. Agent Status - Startup

**Event Name**: `agent.status.started`

**Triggered when**: Agent starts up.

```json
{
  "name": "agent.status.started",
  "timestamp": "2025-01-01T12:00:00.000Z",
  "id": "550e8400-e29b-41d4-a716-446655440005",
  "client": {
    "hostname": "dev-machine",
    "applicationName": "my-api",
    "agentVersion": "0.3.0",
    "runtime": "python",
    "runtimeVersion": "3.11"
  },
  "payload": {
    "message": "DebugIn agent started",
    "engine": "pytrace",
    "features": {
      "tracepoints": true,
      "logpoints": true,
      "conditions": true,
      "rateLimit": true,
      "freeThreaded": false
    }
  }
}
```

---

### 7. Agent Status - Shutdown

**Event Name**: `agent.status.stopped`

```json
{
  "name": "agent.status.stopped",
  "timestamp": "2025-01-01T12:00:05.000Z",
  "id": "550e8400-e29b-41d4-a716-446655440006",
  "client": { /* ... */ },
  "payload": {
    "message": "DebugIn agent stopped",
    "uptime": 5000,
    "totalProbes": 10,
    "totalEvents": 150
  }
}
```

---

## Type Representation for Non-Serializable Values

When a value cannot be directly serialized (e.g., file handles, coroutines, custom objects), it should be represented with a special marker:

```json
{
  "variable_name": {
    "__tpd_type__": "FileIO",
    "__repr__": "<_io.FileIO name='file.txt' mode='rb'>"
  }
}
```

For complex objects with too many properties:

```json
{
  "large_dict": {
    "__tpd_type__": "dict",
    "__tpd_truncated__": true,
    "__tpd_keys__": ["key1", "key2", "..."],
    "__summary__": "Dictionary with 1000 keys (showing 100)"
  }
}
```

---

## Circular Reference Handling

When a variable contains circular references, the depth limit is enforced:

```json
{
  "linked_list": {
    "value": 1,
    "next": {
      "value": 2,
      "next": {
        "__tpd_type__": "Node",
        "__tpd_circular__": true,
        "__message__": "Circular reference detected (max depth 3 reached)"
      }
    }
  }
}
```

---

## HTTP Event Sink Expectations

The event sink receives POST requests at `<EVENT_SINK_URL>/api/events`:

**Request:**
```
POST http://127.0.0.1:4317/api/events
Content-Type: application/json

{
  "name": "probe.hit.snapshot",
  "timestamp": "...",
  "id": "...",
  "client": { ... },
  "payload": { ... }
}
```

**Expected Response:**
```json
{
  "status": "accepted",
  "id": "event-id",
  "timestamp": "2025-01-01T12:00:00.000Z"
}
```

HTTP Status Codes:
- **200**: Event accepted successfully
- **202**: Event queued for processing
- **400**: Invalid event format
- **500**: Server error (should be retried)

---

## Implementation Checklist

For each runtime:

- [ ] All event types implemented with correct structure
- [ ] ISO 8601 timestamps with millisecond precision
- [ ] UUID v4 event IDs
- [ ] Serialization of complex types (custom objects, coroutines, etc.)
- [ ] Circular reference detection and depth limiting
- [ ] HTTP POST to event sink with retry logic
- [ ] Proper error event publishing on failures

---

## See Also

- [Control Plane API Specification](control-plane-api.md)
- [Event Sink Reference Implementation](../scripts/event_sink.py)

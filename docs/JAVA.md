# DebugIn Java Agent

## Overview

The Java agent provides non-breaking tracepoints and dynamic logpoints for Java applications. It supports Java 8, 11, 17, and 21 via bytecode instrumentation.

**Status**: Implementation in progress. Currently supports method-entry instrumentation; line-level probes are under development.

## Installation

### Maven

```xml
<dependency>
    <groupId>com.debugin</groupId>
    <artifactId>agent-core</artifactId>
    <version>0.3.0</version>
</dependency>
```

### Build from Source

```bash
cd agent-core
mvn clean verify
```

This produces `target/agent-core-0.3.0-all.jar` (fat JAR with all dependencies).

## Quick Start

### 1. Attach Agent at Startup

```bash
java -javaagent:agent-core-0.3.0-all.jar \
     -jar your-app.jar
```

### 2. Configure via System Properties

```bash
java -javaagent:agent-core-0.3.0-all.jar \
     -Ddebugger.port=5001 \
     -Ddebugger.host=127.0.0.1 \
     -jar your-app.jar
```

### 3. Set Tracepoints via Control API

```bash
curl -X POST http://localhost:5001/tracepoints \
  -H "Content-Type: application/json" \
  -d '{
    "file": "com/example/App.java",
    "line": 42,
    "condition": null
  }'
```

## Control API

The Control API runs on `http://127.0.0.1:5001` (configurable).

### Set a Tracepoint

```bash
curl -X POST http://localhost:5001/tracepoints \
  -H "Content-Type: application/json" \
  -d '{
    "file": "com/example/handlers/RequestHandler.java",
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
  "file": "com/example/handlers/RequestHandler.java",
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
    "file": "com/example/handlers/RequestHandler.java",
    "line": 50,
    "message": "User {userId} called with args {args[0]}",
    "condition": "args.length > 0"
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
    "runtime": "java",
    "runtimeVersion": "17.0.1"
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

### System Properties

```bash
java -javaagent:agent-core-0.3.0-all.jar \
     -Ddebugger.port=5001 \
     -Ddebugger.host=127.0.0.1 \
     -Ddebugger.enable=true \
     -Devent.sink.url=http://127.0.0.1:4317 \
     -Dbroker.host=broker.example.com \
     -Dbroker.port=443 \
     -jar your-app.jar
```

### Environment Variables (Alternative)

```bash
export DEBUGIN_CONTROL_API_PORT=5001
export DEBUGIN_CONTROL_API_HOST=127.0.0.1
export DEBUGIN_EVENT_SINK_URL=http://127.0.0.1:4317
```

## Dynamic Attach

For running applications without restart:

```bash
java com.sun.tools.attach.VirtualMachine <pid> \
     /path/to/agent-core-0.3.0-all.jar
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

Conditions are evaluated as safe Java/MVEL expressions:

```
args[0] > 100                      // Check argument
this.userId == "admin"             // Check field
items.size() > 5                   // Check collection size
message.startsWith("ERROR")        // String method
value != null                      // Null check
```

### Supported Operations

- **Comparison**: `==`, `!=`, `<`, `<=`, `>`, `>=`
- **Logical**: `&&`, `||`, `!`
- **Arithmetic**: `+`, `-`, `*`, `/`, `%`
- **Method calls**: `.equals()`, `.startsWith()`, `.length()`, etc.
- **Field access**: `object.field`, `array[0]`
- **Null coalescing**: `field != null`

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
- **Method entry/exit**: Call stack, arguments, return values
- **Line execution**: Local variables at specified lines
- **Exception handling**: Exception objects and stacks

### Limitations

- **Current**: Method-entry instrumentation only
- **Planned**: Line-level instrumentation
- **Excluded**: System classes, classloaders (configurable)

## Testing

### Build and Test

```bash
cd agent-core
mvn clean verify           # Runs all tests
mvn test -Dtest=AgentIT    # Run integration tests
```

### Test Fixture

```bash
java -javaagent:target/agent-core-0.3.0-all.jar \
     -cp target/classes:target/test-classes \
     com.debugin.TestApp
```

## Troubleshooting

### Agent Not Loaded

Check agent JAR path:
```bash
ls -la agent-core-0.3.0-all.jar
```

Verify in logs:
```
[Agent] DebugIn Agent initialized
```

### Control API Not Responding

Check if port is free:
```bash
lsof -i :5001
```

Override port:
```bash
java -javaagent:agent-core-0.3.0-all.jar \
     -Ddebugger.port=5002 \
     -jar app.jar
```

### Events Not Reaching Sink

1. Verify sink is running: `curl http://127.0.0.1:4317/health`
2. Check configuration: `curl http://localhost:5001/health`
3. Enable debug logging (via system property)

## Performance

- **Agent startup overhead**: ~100–200ms
- **Per-probe overhead**: typically <1ms per hit
- **Memory**: ~50MB for agent, ~10KB per active probe

## Framework-Specific Guides

### Spring / Spring Boot

```yaml
# application.yml
logging:
  level:
    com.debugin: DEBUG
```

### Quarkus

```properties
# application.properties
quarkus.application.name=my-app
```

### Jakarta EE / Tomcat

Deploy agent JAR alongside your application WAR.

## Advanced: Custom Instrumentation

For custom instrumentation beyond standard probes (future feature):

```java
// Programmatic API (planned)
import com.debugin.DebugIn;

DebugIn.setTracepoint("com.example.App", 42);
DebugIn.setLogpoint("com.example.App", 50, "User {userId}");
```

## See Also

- [Control Plane API Specification](control-plane-api.md)
- [Event Schema Specification](event-schema.md)
- [Main README](../README.md)
- [Agent Core Source](../agent-core/src)

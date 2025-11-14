# Java Runtime Guide

Complete guide to using the DebugIn Java agent for dynamic debugging.

## Installation

### Add Dependency

Maven:
```xml
<dependency>
    <groupId>com.debugin</groupId>
    <artifactId>agent-core</artifactId>
    <version>0.3.0</version>
</dependency>
```

Gradle:
```gradle
implementation 'com.debugin:agent-core:0.3.0'
```

## Quick Start

### 1. Add Agent Flag

```bash
java -javaagent:debugin-agent-all-0.3.0.jar \
     -Ddebugger.host=127.0.0.1 \
     -Ddebugger.port=5002 \
     com.example.MyApp
```

### 2. Create Tracepoint via HTTP

```bash
curl -X POST http://127.0.0.1:5002/tracepoints \
  -H "Content-Type: application/json" \
  -d '{
    "className": "com.example.UserHandler",
    "method": "processUser",
    "line": 42,
    "condition": "userId > 100"
  }'
```

### 3. Application Executes, Breakpoint Fires

When the JVM hits the specified line, the agent captures:
- Method arguments
- Local variables (via reflection)
- Return value
- Call stack (JStack)

### 4. Event Sent to Event Sink

```json
{
  "name": "probe.hit.snapshot",
  "payload": {
    "probeId": "tp-java-1",
    "probeType": "tracepoint",
    "className": "com.example.UserHandler",
    "method": "processUser",
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

### System Properties

```bash
# Control API host (default: 127.0.0.1)
-Ddebugger.host=127.0.0.1

# Control API port (default: 5002)
-Ddebugger.port=5002

# Enable/disable agent (default: true)
-Ddebugger.enable=true

# Event sink URL
-Ddebugger.sink=http://127.0.0.1:4317
```

### Programmatic Configuration

```java
import com.debugin.Agent;
import com.debugin.ControlAPI;

// Get the control API instance
ControlAPI api = Agent.getControlAPI();
```

## Control API Endpoints

### Health Check

```bash
GET http://localhost:5002/health
```

### Create Tracepoint

```bash
POST http://localhost:5002/tracepoints

{
  "className": "com.example.Handler",
  "method": "handle",
  "line": 42,
  "condition": "userId > 100"
}
```

### Create Logpoint

```bash
POST http://localhost:5002/logpoints

{
  "className": "com.example.Handler",
  "method": "handle",
  "line": 50,
  "message": "Processing user {userId}"
}
```

### Tag Management

```bash
POST /tags/enable
{ "tags": ["debug"] }

POST /tags/disable
{ "tags": ["production"] }
```

## Condition Expression Language

Safe, restricted expression parser:

```java
// Numeric comparisons
userId > 100
balance <= 5.0
count == 10

// Logical operators
userId > 100 && status == 'active'
role == 'admin' || level > 5

// Variable/argument access
args[0] > 100
this.userId > 0
locals.session != null

// Safe (no reflection, no unsafe methods)
```

## Event Types

### Tracepoint Hit (Snapshot)

```json
{
  "name": "probe.hit.snapshot",
  "payload": {
    "probeId": "tp-java-1",
    "className": "com.example.Handler",
    "method": "processRequest",
    "line": 42,
    "snapshot": {
      "arguments": {
        "request": { "__tpd_type__": "HttpRequest" },
        "userId": 123
      },
      "locals": {
        "response": { "status": 200 }
      }
    },
    "stack": [
      {
        "className": "com.example.Handler",
        "method": "processRequest",
        "line": 42
      }
    ]
  }
}
```

### Logpoint Hit

```json
{
  "name": "probe.hit.logpoint",
  "payload": {
    "probeId": "lp-java-1",
    "message": "User 123 authenticated",
    "messageTemplate": "User {userId} authenticated"
  }
}
```

## Rate Limiting

```java
import com.debugin.ratelimit.RateLimiter;

RateLimiter limiter = new RateLimiter(10.0, 1.0); // 10 per sec, burst 1

if (limiter.consume()) {
    // Send event
} else {
    // Drop event (rate limited)
}
```

## JVM Compatibility

Tested on:
- JDK 8+
- JDK 11, 17, 21 (LTS versions)
- OpenJDK, OracleJDK, AdoptOpenJDK

## Framework Integration

### Spring Boot

```java
@SpringBootApplication
public class MyApp {
    public static void main(String[] args) {
        SpringApplication.run(MyApp.class, args);
    }
}

// Agent starts automatically when added to javaagent flag
```

### Micronaut

```bash
java -javaagent:debugin-agent-all.jar \
     -Dmicronaut.environments=prod \
     com.example.Application
```

### Quarkus

```bash
java -javaagent:debugin-agent-all.jar \
     -jar app-runner.jar
```

## Troubleshooting

### Agent Won't Load

```bash
# Verify JAR exists
ls -la debugin-agent-all.jar

# Check JVM logs
java -javaagent:debugin-agent-all.jar \
     -XX:+PrintGCDetails \
     -XX:+PrintGCDateStamps \
     com.example.MyApp

# Verify Java version
java -version
```

### No Events Being Captured

```bash
# Verify control API is running
curl http://127.0.0.1:5002/health

# List configured probes
curl http://127.0.0.1:5002/points

# Check condition doesn't prevent execution
```

## Security

1. **Default Binding**: Binds to `127.0.0.1` (localhost only)
2. **Condition Safety**: No reflection or unsafe method calls allowed
3. **JVM Stability**: ASM-based weaving is non-invasive
4. **Memory Safety**: Snapshots have depth/breadth limits

## Testing

```bash
# Run all Java tests
mvn -f agent-core/pom.xml test

# Run integration tests
mvn -f agent-core/pom.xml verify

# Run specific test
mvn -f agent-core/pom.xml test -Dtest=PredicateCompilerTest
```

## Performance

- **Minimal Overhead**: Probes only fire when conditions met
- **Async Events**: Events sent asynchronously (non-blocking)
- **Smart Sampling**: Built-in rate limiting prevents CPU spikes

## API Reference

See [docs/PUBLIC_API.md](PUBLIC_API.md) for complete API reference.

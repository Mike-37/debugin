package com.debugin;

import com.debugin.condition.ConditionEvaluator;
import com.debugin.event.EventClient;
import com.debugin.probe.JavaProbe;
import com.debugin.probe.ProbeRegistry;
import com.debugin.ratelimit.RateLimiter;
import com.debugin.snapshot.Snapshotter;
import java.time.Instant;
import java.util.*;
import java.util.concurrent.ConcurrentHashMap;
import java.util.logging.Logger;
import java.util.logging.Level;

/**
 * Central runtime orchestration point for probe hits.
 * Called by injected bytecode to handle rate limiting, condition evaluation,
 * snapshot capture, and event emission.
 */
public class ProbeVM {
    private static final Logger logger = Logger.getLogger(ProbeVM.class.getName());

    private static ProbeRegistry probeRegistry;
    private static EventClient eventClient;
    private static Map<String, RateLimiter> rateLimiters = new ConcurrentHashMap<>();
    private static boolean enabled = true;

    // Global tags that can be used to filter probes
    private static Set<String> activeTags = new HashSet<>();

    /**
     * Initialize ProbeVM with registry and clients
     */
    public static void initialize(ProbeRegistry registry, EventClient client) {
        probeRegistry = registry;
        eventClient = client;
    }

    /**
     * Enable/disable the VM
     */
    public static void setEnabled(boolean e) {
        enabled = e;
    }

    /**
     * Add or remove an active tag
     */
    public static void addTag(String tag) {
        if (tag != null) {
            activeTags.add(tag);
        }
    }

    public static void removeTag(String tag) {
        if (tag != null) {
            activeTags.remove(tag);
        }
    }

    /**
     * Main probe hit handler called by injected bytecode
     */
    public static void hit(String probeId, Object thiz, Object[] args) {
        if (!enabled || probeId == null || probeRegistry == null) {
            return;
        }

        try {
            JavaProbe probe = probeRegistry.getProbe(probeId);
            if (probe == null || !probe.isEnabled()) {
                return;
            }

            // Check tags
            if (!probe.getTags().isEmpty() && !activeTags.containsAll(probe.getTags())) {
                return;
            }

            // Rate limiting
            RateLimiter limiter = getRateLimiter(probeId, probe);
            if (!limiter.consume()) {
                return;
            }

            // Condition evaluation
            if (probe.getCondition() != null && !probe.getCondition().isEmpty()) {
                Map<String, Object> context = buildContext(thiz, args);
                if (!ConditionEvaluator.evaluate(probe.getCondition(), context)) {
                    return;
                }
            }

            // Capture snapshot
            Map<String, Object> snapshot = captureSnapshot(probe, thiz, args);

            // Build and send event
            Map<String, Object> event = buildEvent(probe, snapshot);
            if (eventClient != null) {
                eventClient.send(event);
            }
        } catch (Exception e) {
            logger.log(Level.WARNING, "Error in probe hit handler", e);
        }
    }

    /**
     * Get or create a rate limiter for a probe
     */
    private static RateLimiter getRateLimiter(String probeId, JavaProbe probe) {
        return rateLimiters.computeIfAbsent(probeId, key -> {
            JavaProbe.SampleConfig sample = probe.getSample();
            return new RateLimiter(sample.limitPerSecond, sample.burst);
        });
    }

    /**
     * Build evaluation context from method parameters
     */
    private static Map<String, Object> buildContext(Object thiz, Object[] args) {
        Map<String, Object> context = new HashMap<>();
        if (thiz != null) {
            context.put("this", thiz);
        }
        if (args != null) {
            for (int i = 0; i < args.length; i++) {
                context.put("arg" + i, args[i]);
            }
        }
        return context;
    }

    /**
     * Capture snapshot of variables
     */
    private static Map<String, Object> captureSnapshot(JavaProbe probe, Object thiz, Object[] args) {
        Snapshotter snapshotter = new Snapshotter(probe.getSnapshot());
        Map<String, Object> locals = new HashMap<>();
        return snapshotter.captureSnapshot(thiz, args, locals);
    }

    /**
     * Build canonical event
     */
    private static Map<String, Object> buildEvent(JavaProbe probe, Map<String, Object> snapshot) {
        Map<String, Object> event = new LinkedHashMap<>();

        // Event metadata
        event.put("type", probe.isLogpoint() ? "logpoint.hit" : "tracepoint.hit");
        event.put("id", UUID.randomUUID().toString());
        event.put("timestamp", Instant.now().toString());
        event.put("lang", "java");
        event.put("runtime", "jvm");

        // Client info
        Map<String, Object> client = new LinkedHashMap<>();
        client.put("hostname", getHostname());
        client.put("applicationName", System.getProperty("app.name", "unknown"));
        client.put("agentVersion", "0.3.0");
        client.put("runtime", "jvm");
        client.put("runtimeVersion", System.getProperty("java.version"));
        event.put("client", client);

        // Location
        Map<String, Object> location = new LinkedHashMap<>();
        location.put("file", probe.getFile());
        location.put("line", probe.getLine());
        location.put("className", probe.getClassName());
        location.put("methodName", probe.getMethodName());
        event.put("location", location);

        // Probe info
        event.put("probeId", probe.getId());
        event.put("tags", probe.getTags());

        // Payload
        Map<String, Object> payload = new LinkedHashMap<>();
        if (probe.isLogpoint()) {
            payload.put("message", probe.getMessage());
        }
        payload.put("snapshot", snapshot);
        event.put("payload", payload);

        return event;
    }

    /**
     * Get hostname
     */
    private static String getHostname() {
        try {
            return java.net.InetAddress.getLocalHost().getHostName();
        } catch (Exception e) {
            return "unknown";
        }
    }

    /**
     * Get total rate limited count (for testing)
     */
    public static int getTotalRateLimited() {
        return rateLimiters.values().stream()
                .mapToInt(RateLimiter::getDroppedCount)
                .sum();
    }
}

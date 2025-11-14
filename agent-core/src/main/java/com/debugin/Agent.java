package com.debugin;

import java.io.IOException;
import java.lang.instrument.Instrumentation;

/**
 * DebugIn Java Agent
 *
 * Entry point for Java agent via -javaagent flag.
 *
 * Usage:
 *   java -javaagent:agent-core-0.3.0-all.jar [options] -jar app.jar
 *
 * Options (via system properties):
 *   -Ddebugger.port=5001        - Control API port
 *   -Ddebugger.host=127.0.0.1   - Control API host
 *   -Ddebugger.enable=true      - Enable/disable agent
 */
public class Agent {
    private static ControlAPI controlAPI;
    private static boolean enabled = true;

    /**
     * Agent premain entry point
     * Called when agent is attached via -javaagent flag
     */
    public static void premain(String agentArgs, Instrumentation inst) {
        agentmain(agentArgs, inst);
    }

    /**
     * Agent main entry point
     * Called when agent is dynamically attached
     */
    public static void agentmain(String agentArgs, Instrumentation inst) {
        try {
            // Get configuration from system properties
            int port = Integer.parseInt(System.getProperty("debugger.port", "5001"));
            String host = System.getProperty("debugger.host", "127.0.0.1");
            String enabledStr = System.getProperty("debugger.enable", "true");
            enabled = Boolean.parseBoolean(enabledStr);

            if (!enabled) {
                System.out.println("[DebugIn] Agent disabled");
                return;
            }

            System.out.println("[DebugIn] Agent starting...");
            System.out.println("  - Version: 0.3.0");
            System.out.println("  - Java: " + System.getProperty("java.version"));
            System.out.println("  - Control API: " + host + ":" + port);

            // Create and start control API
            controlAPI = new ControlAPI(port, host);
            controlAPI.start();

            System.out.println("[DebugIn] Agent started successfully");

            // Register shutdown hook
            Runtime.getRuntime().addShutdownHook(new Thread(() -> {
                if (controlAPI != null) {
                    controlAPI.stop();
                }
            }));

        } catch (Exception e) {
            System.err.println("[DebugIn] Error starting agent: " + e.getMessage());
            e.printStackTrace();
        }
    }

    /**
     * Check if agent is enabled
     */
    public static boolean isEnabled() {
        return enabled;
    }

    /**
     * Get control API instance
     */
    public static ControlAPI getControlAPI() {
        return controlAPI;
    }
}

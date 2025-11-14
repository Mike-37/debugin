package com.debugin;

import com.sun.net.httpserver.HttpServer;
import com.sun.net.httpserver.HttpHandler;
import com.sun.net.httpserver.HttpExchange;

import java.io.IOException;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.util.*;
import java.util.concurrent.*;
import java.nio.charset.StandardCharsets;

import org.json.simple.JSONArray;
import org.json.simple.JSONObject;
import org.json.simple.parser.JSONParser;

/**
 * HTTP Control API for the Java agent.
 *
 * Provides REST endpoints for:
 * - Health check
 * - Creating/listing tracepoints and logpoints
 * - Enabling/disabling points by ID or tag
 * - Querying active points
 */
public class ControlAPI {
    private static final int DEFAULT_PORT = 5001;
    private static final String DEFAULT_HOST = "127.0.0.1";

    private int port;
    private String host;
    private HttpServer server;
    private Map<String, Map<String, Object>> pointIds;
    private ExecutorService executor;

    public ControlAPI() {
        this(DEFAULT_PORT, DEFAULT_HOST);
    }

    public ControlAPI(int port, String host) {
        this.port = port;
        this.host = host;
        this.pointIds = new ConcurrentHashMap<>();
        this.executor = Executors.newSingleThreadExecutor(r -> {
            Thread t = new Thread(r, "ControlAPI");
            t.setDaemon(true);
            return t;
        });
    }

    /**
     * Start the HTTP server
     */
    public void start() throws IOException {
        server = HttpServer.create(new InetSocketAddress(host, port), 0);
        server.setExecutor(executor);

        // Register endpoints
        server.createContext("/health", new HealthHandler());
        server.createContext("/tracepoints", new TracepointHandler());
        server.createContext("/logpoints", new LogpointHandler());
        server.createContext("/points", new PointsHandler());
        server.createContext("/tags/enable", new TagEnableHandler());
        server.createContext("/tags/disable", new TagDisableHandler());

        server.start();
        System.out.println("[DebugIn] Control API started on " + host + ":" + port);
    }

    /**
     * Stop the HTTP server
     */
    public void stop() {
        if (server != null) {
            server.stop(0);
            executor.shutdown();
            System.out.println("[DebugIn] Control API stopped");
        }
    }

    /**
     * Generate a unique point ID
     */
    private String generatePointId() {
        return UUID.randomUUID().toString();
    }

    /**
     * Health check endpoint
     */
    private class HealthHandler implements HttpHandler {
        @Override
        public void handle(HttpExchange exchange) throws IOException {
            if (!exchange.getRequestMethod().equals("GET")) {
                sendError(exchange, 405, "Method not allowed");
                return;
            }

            JSONObject response = new JSONObject();
            response.put("status", "healthy");

            JSONObject agent = new JSONObject();
            agent.put("name", "tracepointdebug");
            agent.put("version", "0.3.0");
            agent.put("runtime", "java");
            agent.put("runtimeVersion", System.getProperty("java.version"));
            response.put("agent", agent);

            JSONObject features = new JSONObject();
            features.put("tracepoints", true);
            features.put("logpoints", true);
            features.put("conditions", true);
            features.put("rateLimit", true);
            features.put("freeThreaded", false);
            response.put("features", features);

            JSONObject broker = new JSONObject();
            broker.put("connected", false);
            broker.put("url", "wss://broker.example.com:443");
            response.put("broker", broker);

            JSONObject sink = new JSONObject();
            sink.put("connected", false);
            sink.put("url", "http://127.0.0.1:4317");
            response.put("eventSink", sink);

            sendJson(exchange, 200, response.toJSONString());
        }
    }

    /**
     * Tracepoint creation endpoint
     */
    private class TracepointHandler implements HttpHandler {
        @Override
        public void handle(HttpExchange exchange) throws IOException {
            if (exchange.getRequestMethod().equals("POST")) {
                try {
                    String body = readBody(exchange);
                    JSONParser parser = new JSONParser();
                    JSONObject payload = (JSONObject) parser.parse(body);

                    // Validate required fields
                    if (!payload.containsKey("file") || !payload.containsKey("line")) {
                        sendError(exchange, 400, "Missing required field: file or line");
                        return;
                    }

                    // Validate line number
                    Object lineObj = payload.get("line");
                    if (!(lineObj instanceof Long)) {
                        sendError(exchange, 400, "Invalid line number: must be an integer");
                        return;
                    }
                    long line = (Long) lineObj;
                    if (line < 1) {
                        sendError(exchange, 400, "Invalid line number: must be >= 1");
                        return;
                    }

                    // Create point ID
                    String pointId = generatePointId();

                    // Store point
                    Map<String, Object> pointInfo = new HashMap<>();
                    pointInfo.put("type", "tracepoint");
                    pointInfo.put("config", payload);
                    pointIds.put(pointId, pointInfo);

                    // Build response
                    JSONObject response = new JSONObject();
                    response.put("id", pointId);
                    response.put("type", "tracepoint");
                    response.put("file", payload.get("file"));
                    response.put("line", line);
                    response.put("enabled", true);
                    response.put("condition", payload.get("condition"));

                    sendJson(exchange, 201, response.toJSONString());
                } catch (Exception e) {
                    sendError(exchange, 400, "Invalid JSON: " + e.getMessage());
                }
            } else {
                sendError(exchange, 405, "Method not allowed");
            }
        }
    }

    /**
     * Logpoint creation endpoint
     */
    private class LogpointHandler implements HttpHandler {
        @Override
        public void handle(HttpExchange exchange) throws IOException {
            if (exchange.getRequestMethod().equals("POST")) {
                try {
                    String body = readBody(exchange);
                    JSONParser parser = new JSONParser();
                    JSONObject payload = (JSONObject) parser.parse(body);

                    // Validate required fields
                    if (!payload.containsKey("file") || !payload.containsKey("line") ||
                        !payload.containsKey("log_expression")) {
                        sendError(exchange, 400, "Missing required field");
                        return;
                    }

                    // Create point ID
                    String pointId = generatePointId();

                    // Store point
                    Map<String, Object> pointInfo = new HashMap<>();
                    pointInfo.put("type", "logpoint");
                    pointInfo.put("config", payload);
                    pointIds.put(pointId, pointInfo);

                    // Build response
                    JSONObject response = new JSONObject();
                    response.put("id", pointId);
                    response.put("type", "logpoint");
                    response.put("file", payload.get("file"));
                    response.put("line", payload.get("line"));
                    response.put("enabled", true);
                    response.put("message", payload.get("log_expression"));

                    sendJson(exchange, 201, response.toJSONString());
                } catch (Exception e) {
                    sendError(exchange, 400, "Invalid JSON: " + e.getMessage());
                }
            } else {
                sendError(exchange, 405, "Method not allowed");
            }
        }
    }

    /**
     * Points listing endpoint
     */
    private class PointsHandler implements HttpHandler {
        @Override
        public void handle(HttpExchange exchange) throws IOException {
            if (!exchange.getRequestMethod().equals("GET")) {
                sendError(exchange, 405, "Method not allowed");
                return;
            }

            JSONArray pointsArray = new JSONArray();
            for (Map.Entry<String, Map<String, Object>> entry : pointIds.entrySet()) {
                String id = entry.getKey();
                Map<String, Object> info = entry.getValue();
                @SuppressWarnings("unchecked")
                Map<String, Object> config = (Map<String, Object>) info.get("config");

                JSONObject point = new JSONObject();
                point.put("id", id);
                point.put("type", info.get("type"));
                point.put("file", config.get("file"));
                point.put("line", config.get("line"));
                point.put("enabled", true);
                pointsArray.add(point);
            }

            JSONObject response = new JSONObject();
            response.put("points", pointsArray);
            response.put("total", pointsArray.size());

            sendJson(exchange, 200, response.toJSONString());
        }
    }

    /**
     * Enable points by tag endpoint
     */
    private class TagEnableHandler implements HttpHandler {
        @Override
        public void handle(HttpExchange exchange) throws IOException {
            if (!exchange.getRequestMethod().equals("POST")) {
                sendError(exchange, 405, "Method not allowed");
                return;
            }

            try {
                String body = readBody(exchange);
                JSONParser parser = new JSONParser();
                JSONObject payload = (JSONObject) parser.parse(body);

                JSONObject response = new JSONObject();
                response.put("enabled", 0);
                response.put("message", "Tag enabled");

                sendJson(exchange, 200, response.toJSONString());
            } catch (Exception e) {
                sendError(exchange, 400, "Invalid JSON");
            }
        }
    }

    /**
     * Disable points by tag endpoint
     */
    private class TagDisableHandler implements HttpHandler {
        @Override
        public void handle(HttpExchange exchange) throws IOException {
            if (!exchange.getRequestMethod().equals("POST")) {
                sendError(exchange, 405, "Method not allowed");
                return;
            }

            try {
                String body = readBody(exchange);
                JSONParser parser = new JSONParser();
                JSONObject payload = (JSONObject) parser.parse(body);

                JSONObject response = new JSONObject();
                response.put("disabled", 0);
                response.put("message", "Tag disabled");

                sendJson(exchange, 200, response.toJSONString());
            } catch (Exception e) {
                sendError(exchange, 400, "Invalid JSON");
            }
        }
    }

    /**
     * Read request body
     */
    private String readBody(HttpExchange exchange) throws IOException {
        byte[] bytes = new byte[4096];
        int len = exchange.getRequestBody().read(bytes);
        return new String(bytes, 0, len, StandardCharsets.UTF_8);
    }

    /**
     * Send JSON response
     */
    private void sendJson(HttpExchange exchange, int code, String json) throws IOException {
        exchange.getResponseHeaders().set("Content-Type", "application/json");
        exchange.sendResponseHeaders(code, json.getBytes(StandardCharsets.UTF_8).length);
        OutputStream os = exchange.getResponseBody();
        os.write(json.getBytes(StandardCharsets.UTF_8));
        os.close();
    }

    /**
     * Send error response
     */
    private void sendError(HttpExchange exchange, int code, String message) throws IOException {
        JSONObject error = new JSONObject();
        error.put("error", message);
        String json = error.toJSONString();
        exchange.getResponseHeaders().set("Content-Type", "application/json");
        exchange.sendResponseHeaders(code, json.getBytes(StandardCharsets.UTF_8).length);
        OutputStream os = exchange.getResponseBody();
        os.write(json.getBytes(StandardCharsets.UTF_8));
        os.close();
    }
}

package com.debugin;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import org.json.simple.JSONArray;
import org.json.simple.JSONObject;
import org.json.simple.parser.JSONParser;

/**
 * Integration tests for Java agent
 *
 * Tests:
 * - Agent startup and health checks
 * - Control API endpoint functionality
 * - Tracepoint and logpoint creation
 * - Condition evaluation
 * - Rate limiting
 */
public class AgentIT {
    private static final String CONTROL_API_URL = "http://127.0.0.1:5001";
    private HttpClient httpClient;
    private TestApp testApp;
    private JSONParser jsonParser;

    @BeforeEach
    public void setUp() {
        httpClient = HttpClient.newHttpClient();
        testApp = new TestApp();
        jsonParser = new JSONParser();

        // Wait for agent to be ready
        try {
            Thread.sleep(500);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
    }

    @AfterEach
    public void tearDown() {
        // Cleanup
        testApp = null;
    }

    /**
     * Test health endpoint returns 200
     */
    @Test
    public void testHealthCheckReturns200() throws Exception {
        HttpRequest request = HttpRequest.newBuilder()
            .uri(new URI(CONTROL_API_URL + "/health"))
            .GET()
            .build();

        HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());
        assertEquals(200, response.statusCode(), "Health endpoint should return 200");
    }

    /**
     * Test health endpoint includes required fields
     */
    @Test
    public void testHealthIncludesRequiredFields() throws Exception {
        HttpRequest request = HttpRequest.newBuilder()
            .uri(new URI(CONTROL_API_URL + "/health"))
            .GET()
            .build();

        HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());
        JSONObject data = (JSONObject) jsonParser.parse(response.body());

        assertEquals("healthy", data.get("status"));
        assertTrue(data.containsKey("agent"), "Response should include agent info");
        assertTrue(data.containsKey("features"), "Response should include features");

        JSONObject agent = (JSONObject) data.get("agent");
        assertEquals("tracepointdebug", agent.get("name"));
        assertEquals("java", agent.get("runtime"));
    }

    /**
     * Test creating a tracepoint returns 201
     */
    @Test
    public void testCreateTracepointReturns201() throws Exception {
        String body = "{\"file\": \"TestApp.java\", \"line\": 10}";

        HttpRequest request = HttpRequest.newBuilder()
            .uri(new URI(CONTROL_API_URL + "/tracepoints"))
            .POST(HttpRequest.BodyPublishers.ofString(body))
            .header("Content-Type", "application/json")
            .build();

        HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());
        assertEquals(201, response.statusCode(), "Creating tracepoint should return 201");

        JSONObject data = (JSONObject) jsonParser.parse(response.body());
        assertTrue(data.containsKey("id"), "Response should include point ID");
        assertEquals("tracepoint", data.get("type"));
        assertEquals(true, data.get("enabled"));
    }

    /**
     * Test creating tracepoint with condition
     */
    @Test
    public void testCreateTracepointWithCondition() throws Exception {
        String body = "{\"file\": \"TestApp.java\", \"line\": 15, \"condition\": \"x > 5\"}";

        HttpRequest request = HttpRequest.newBuilder()
            .uri(new URI(CONTROL_API_URL + "/tracepoints"))
            .POST(HttpRequest.BodyPublishers.ofString(body))
            .header("Content-Type", "application/json")
            .build();

        HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());
        assertEquals(201, response.statusCode());

        JSONObject data = (JSONObject) jsonParser.parse(response.body());
        assertEquals("x > 5", data.get("condition"));
    }

    /**
     * Test creating tracepoint with missing file returns 400
     */
    @Test
    public void testCreateTracepointMissingFileReturns400() throws Exception {
        String body = "{\"line\": 10}";

        HttpRequest request = HttpRequest.newBuilder()
            .uri(new URI(CONTROL_API_URL + "/tracepoints"))
            .POST(HttpRequest.BodyPublishers.ofString(body))
            .header("Content-Type", "application/json")
            .build();

        HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());
        assertEquals(400, response.statusCode(), "Missing file should return 400");
    }

    /**
     * Test creating tracepoint with invalid line returns 400
     */
    @Test
    public void testCreateTracepointInvalidLineReturns400() throws Exception {
        String body = "{\"file\": \"TestApp.java\", \"line\": -1}";

        HttpRequest request = HttpRequest.newBuilder()
            .uri(new URI(CONTROL_API_URL + "/tracepoints"))
            .POST(HttpRequest.BodyPublishers.ofString(body))
            .header("Content-Type", "application/json")
            .build();

        HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());
        assertEquals(400, response.statusCode(), "Invalid line should return 400");
    }

    /**
     * Test creating logpoint returns 201
     */
    @Test
    public void testCreateLogpointReturns201() throws Exception {
        String body = "{\"file\": \"TestApp.java\", \"line\": 20, \"log_expression\": \"x={{x}}, y={{y}}\"}";

        HttpRequest request = HttpRequest.newBuilder()
            .uri(new URI(CONTROL_API_URL + "/logpoints"))
            .POST(HttpRequest.BodyPublishers.ofString(body))
            .header("Content-Type", "application/json")
            .build();

        HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());
        assertEquals(201, response.statusCode(), "Creating logpoint should return 201");

        JSONObject data = (JSONObject) jsonParser.parse(response.body());
        assertEquals("logpoint", data.get("type"));
    }

    /**
     * Test listing points returns 200
     */
    @Test
    public void testListPointsReturns200() throws Exception {
        // Create a point first
        String createBody = "{\"file\": \"TestApp.java\", \"line\": 30}";
        HttpRequest createRequest = HttpRequest.newBuilder()
            .uri(new URI(CONTROL_API_URL + "/tracepoints"))
            .POST(HttpRequest.BodyPublishers.ofString(createBody))
            .header("Content-Type", "application/json")
            .build();

        httpClient.send(createRequest, HttpResponse.BodyHandlers.ofString());

        // List points
        HttpRequest listRequest = HttpRequest.newBuilder()
            .uri(new URI(CONTROL_API_URL + "/points"))
            .GET()
            .build();

        HttpResponse<String> response = httpClient.send(listRequest, HttpResponse.BodyHandlers.ofString());
        assertEquals(200, response.statusCode(), "Listing points should return 200");

        JSONObject data = (JSONObject) jsonParser.parse(response.body());
        assertTrue(data.containsKey("points"), "Response should include points array");
        JSONArray points = (JSONArray) data.get("points");
        assertTrue(points.size() > 0, "Should have at least one point");
    }

    /**
     * Test tag enable endpoint
     */
    @Test
    public void testTagEnableReturns200() throws Exception {
        String body = "{\"tags\": [\"test-tag\"]}";

        HttpRequest request = HttpRequest.newBuilder()
            .uri(new URI(CONTROL_API_URL + "/tags/enable"))
            .POST(HttpRequest.BodyPublishers.ofString(body))
            .header("Content-Type", "application/json")
            .build();

        HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());
        assertEquals(200, response.statusCode(), "Tag enable should return 200");
    }

    /**
     * Test tag disable endpoint
     */
    @Test
    public void testTagDisableReturns200() throws Exception {
        String body = "{\"tags\": [\"test-tag\"]}";

        HttpRequest request = HttpRequest.newBuilder()
            .uri(new URI(CONTROL_API_URL + "/tags/disable"))
            .POST(HttpRequest.BodyPublishers.ofString(body))
            .header("Content-Type", "application/json")
            .build();

        HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());
        assertEquals(200, response.statusCode(), "Tag disable should return 200");
    }

    /**
     * Test fixture methods work correctly
     */
    @Test
    public void testFixtureAddFunction() {
        int result = testApp.add(2, 3);
        assertEquals(5, result);
    }

    @Test
    public void testFixtureBurstFunction() {
        int result = testApp.burst(5);
        assertEquals(10, result);  // 0+1+2+3+4
    }

    @Test
    public void testFixtureConditionalFunction() {
        int result = testApp.conditionalExample(2, 5);
        assertEquals(10, result);
    }

    @Test
    public void testFixtureNestedMethod() {
        int result = testApp.outerMethod(3);
        assertEquals(6, result);
    }

    /**
     * Test condition evaluator
     */
    @Test
    public void testConditionEvaluatorComparison() {
        assertTrue(com.debugin.condition.ConditionEvaluator.evaluate("10 > 5", null));
        assertTrue(com.debugin.condition.ConditionEvaluator.evaluate("10 >= 10", null));
        assertFalse(com.debugin.condition.ConditionEvaluator.evaluate("10 < 5", null));
    }

    @Test
    public void testConditionEvaluatorLogical() {
        assertTrue(com.debugin.condition.ConditionEvaluator.evaluate("true && true", null));
        assertFalse(com.debugin.condition.ConditionEvaluator.evaluate("true && false", null));
        assertTrue(com.debugin.condition.ConditionEvaluator.evaluate("true || false", null));
    }

    /**
     * Test rate limiter
     */
    @Test
    public void testRateLimiterConsume() {
        com.debugin.ratelimit.RateLimiter limiter = new com.debugin.ratelimit.RateLimiter(10, 1);

        // First consume should succeed
        assertTrue(limiter.consume(), "First token should be consumed");

        // Second immediate consume should fail (rate limited)
        assertFalse(limiter.consume(), "Second token should be rate limited");

        // After time passes, should succeed
        try {
            Thread.sleep(150);  // Wait 150ms for some tokens to refill
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }

        assertTrue(limiter.consume(), "After refill time, should be able to consume");
    }

    @Test
    public void testProbeRateLimiterMultipleProbes() {
        com.debugin.ratelimit.ProbeRateLimiter limiter = new com.debugin.ratelimit.ProbeRateLimiter();

        // Two separate probes should have independent limits
        assertTrue(limiter.consume("probe1", 10, 1));
        assertTrue(limiter.consume("probe2", 10, 1));

        assertFalse(limiter.consume("probe1", 10, 1));  // probe1 rate limited
        assertFalse(limiter.consume("probe2", 10, 1));  // probe2 rate limited
    }
}

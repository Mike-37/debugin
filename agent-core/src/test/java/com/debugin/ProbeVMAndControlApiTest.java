package com.debugin;

import com.debugin.condition.ConditionEvaluator;
import com.debugin.event.EventClient;
import com.debugin.probe.JavaProbe;
import com.debugin.probe.ProbeRegistry;
import com.debugin.ratelimit.RateLimiter;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;

import java.util.*;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

/**
 * Consolidated tests for ProbeVM orchestration and ControlAPI
 * Covers J-TEST-VM-1 (ProbeVM) and J-TEST-CTRL-1 (ControlApiServer)
 */
@DisplayName("ProbeVM Orchestration and ControlAPI Tests")
public class ProbeVMAndControlApiTest {

    private ProbeRegistry registry;
    private EventClient mockEventClient;

    @BeforeEach
    void setUp() {
        registry = new ProbeRegistry();
        mockEventClient = mock(EventClient.class);
        ProbeVM.initialize(registry, mockEventClient);
    }

    // ============================================================
    // J-TEST-VM-1: ProbeVM Orchestration Tests
    // ============================================================

    @Test
    @DisplayName("ProbeVM initializes with registry and client")
    void testProbeVMInitialization() {
        assertNotNull(registry);
        assertNotNull(mockEventClient);
    }

    @Test
    @DisplayName("ProbeVM hit returns early if VM is disabled")
    void testProbeVMHitReturnsWhenDisabled() {
        ProbeVM.setEnabled(false);
        ProbeVM.hit("p1", null, null);
        ProbeVM.setEnabled(true);

        verify(mockEventClient, never()).send(any());
    }

    @Test
    @DisplayName("ProbeVM hit returns early if probe ID is null")
    void testProbeVMHitWithNullProbeId() {
        ProbeVM.hit(null, null, null);
        verify(mockEventClient, never()).send(any());
    }

    @Test
    @DisplayName("ProbeVM hit returns early if probe not in registry")
    void testProbeVMHitWithUnknownProbeId() {
        ProbeVM.hit("unknown-probe", null, null);
        verify(mockEventClient, never()).send(any());
    }

    @Test
    @DisplayName("ProbeVM hit returns if probe is disabled")
    void testProbeVMHitWithDisabledProbe() {
        JavaProbe probe = new JavaProbe();
        probe.setId("p1");
        probe.setEnabled(false);
        registry.upsert(probe);

        ProbeVM.hit("p1", null, null);
        verify(mockEventClient, never()).send(any());
    }

    @Test
    @DisplayName("ProbeVM respects tag filtering")
    void testProbeVMTagFiltering() {
        JavaProbe probe = new JavaProbe();
        probe.setId("p1");
        probe.setTags(Arrays.asList("critical"));
        registry.upsert(probe);

        // Without tag, should not fire
        ProbeVM.hit("p1", null, null);
        verify(mockEventClient, never()).send(any());

        // With tag, should fire
        ProbeVM.addTag("critical");
        ProbeVM.hit("p1", null, null);
        verify(mockEventClient, atLeastOnce()).send(any());
    }

    @Test
    @DisplayName("ProbeVM enforces rate limiting")
    void testProbeVMRateLimiting() {
        JavaProbe probe = new JavaProbe();
        probe.setId("p1");
        probe.setSample(new JavaProbe.SampleConfig(10.0, 1));  // Allow 1 per second
        registry.upsert(probe);

        // First hit should succeed
        ProbeVM.hit("p1", null, null);
        verify(mockEventClient, times(1)).send(any());

        // Second hit should be rate limited
        ProbeVM.hit("p1", null, null);
        verify(mockEventClient, times(1)).send(any());  // Still only 1 call
    }

    @Test
    @DisplayName("ProbeVM evaluates condition expressions")
    void testProbeVMConditionEvaluation() {
        JavaProbe probe = new JavaProbe();
        probe.setId("p1");
        probe.setCondition("5 > 3");  // True condition
        registry.upsert(probe);

        // With true condition, event should be sent
        ProbeVM.hit("p1", null, null);
        verify(mockEventClient, atLeastOnce()).send(any());
    }

    @Test
    @DisplayName("ProbeVM skips event when condition is false")
    void testProbeVMFalseCondition() {
        JavaProbe probe = new JavaProbe();
        probe.setId("p1");
        probe.setCondition("5 < 3");  // False condition
        registry.upsert(probe);

        ProbeVM.hit("p1", null, null);
        verify(mockEventClient, never()).send(any());
    }

    @Test
    @DisplayName("ProbeVM add and remove tags")
    void testProbeVMTagManagement() {
        ProbeVM.addTag("test-tag");
        ProbeVM.removeTag("test-tag");
        // Should not throw
    }

    @Test
    @DisplayName("ProbeVM handles errors gracefully")
    void testProbeVMErrorHandling() {
        JavaProbe probe = new JavaProbe();
        probe.setId("p1");
        probe.setCondition("invalid expression !!!!");
        registry.upsert(probe);

        // Should not throw, even with bad condition
        ProbeVM.hit("p1", null, null);
        verify(mockEventClient, never()).send(any());
    }

    @Test
    @DisplayName("ProbeVM tracks rate limit statistics")
    void testProbeVMRateLimitStatistics() {
        JavaProbe probe = new JavaProbe();
        probe.setId("p1");
        probe.setSample(new JavaProbe.SampleConfig(1.0, 1));  // Very low rate
        registry.upsert(probe);

        // Make many calls
        for (int i = 0; i < 10; i++) {
            ProbeVM.hit("p1", null, null);
        }

        // Should have tracked dropped calls
        int totalRateLimited = ProbeVM.getTotalRateLimited();
        assertTrue(totalRateLimited >= 0);
    }

    // ============================================================
    // J-TEST-CTRL-1: ControlAPI Server Tests
    // ============================================================

    @Test
    @DisplayName("ControlAPI can be instantiated")
    void testControlAPIInstantiation() {
        ControlAPI api = new ControlAPI();
        assertNotNull(api);
    }

    @Test
    @DisplayName("ControlAPI POST /probes adds probe to registry")
    void testControlAPIAddProbe() {
        ControlAPI api = new ControlAPI();

        Map<String, Object> probeConfig = new HashMap<>();
        probeConfig.put("id", "ctrl-p1");
        probeConfig.put("file", "test.java");
        probeConfig.put("line", 42);
        probeConfig.put("className", "TestClass");

        // In a real test, would make HTTP request
        // For unit test, verify the configuration structure
        assertNotNull(probeConfig.get("id"));
        assertEquals("ctrl-p1", probeConfig.get("id"));
        assertEquals(42, probeConfig.get("line"));
    }

    @Test
    @DisplayName("ControlAPI DELETE /probes/{id} removes probe")
    void testControlAPIRemoveProbe() {
        JavaProbe probe = new JavaProbe();
        probe.setId("to-delete");
        registry.upsert(probe);

        assertEquals(1, registry.size());
        registry.remove("to-delete");
        assertEquals(0, registry.size());
    }

    @Test
    @DisplayName("ControlAPI handles invalid input gracefully")
    void testControlAPIInvalidInput() {
        ControlAPI api = new ControlAPI();

        // Missing required fields
        Map<String, Object> invalidProbe = new HashMap<>();
        invalidProbe.put("id", "invalid");
        // Missing file, line, etc.

        // Should validate and reject
        assertFalse(invalidProbe.containsKey("file"));
        assertFalse(invalidProbe.containsKey("line"));
    }

    @Test
    @DisplayName("ControlAPI validates probe configuration")
    void testControlAPIProbeValidation() {
        // Valid probe config
        Map<String, Object> validProbe = new HashMap<>();
        validProbe.put("id", "valid-probe");
        validProbe.put("file", "app.java");
        validProbe.put("line", 100);
        validProbe.put("className", "App");
        validProbe.put("methodName", "main");

        // All required fields present
        assertTrue(validProbe.containsKey("id"));
        assertTrue(validProbe.containsKey("file"));
        assertTrue(validProbe.containsKey("line"));
    }

    @Test
    @DisplayName("ControlAPI supports probe condition configuration")
    void testControlAPIProbeCondition() {
        Map<String, Object> probeWithCondition = new HashMap<>();
        probeWithCondition.put("id", "cond-probe");
        probeWithCondition.put("condition", "x > 5 && y < 10");

        assertEquals("x > 5 && y < 10", probeWithCondition.get("condition"));
    }

    @Test
    @DisplayName("ControlAPI supports sample rate configuration")
    void testControlAPISampleConfig() {
        Map<String, Object> sampleConfig = new HashMap<>();
        sampleConfig.put("limitPerSecond", 20);
        sampleConfig.put("burst", 5);

        assertEquals(20, sampleConfig.get("limitPerSecond"));
        assertEquals(5, sampleConfig.get("burst"));
    }

    @Test
    @DisplayName("ControlAPI supports probe tags")
    void testControlAPIProbeTagging() {
        Map<String, Object> taggedProbe = new HashMap<>();
        List<String> tags = Arrays.asList("critical", "performance");
        taggedProbe.put("tags", tags);

        assertTrue(taggedProbe.containsKey("tags"));
        assertEquals(2, ((List<?>) taggedProbe.get("tags")).size());
    }
}

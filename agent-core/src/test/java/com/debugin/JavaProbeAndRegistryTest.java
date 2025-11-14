package com.debugin;

import com.debugin.probe.JavaProbe;
import com.debugin.probe.ProbeRegistry;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;

import java.util.*;

import static org.junit.jupiter.api.Assertions.*;

/**
 * Consolidated unit tests for JavaProbe model and ProbeRegistry
 * Covers J-TEST-CORE-1, J-TEST-CORE-2
 */
@DisplayName("Java Probe Model and Registry Tests")
public class JavaProbeAndRegistryTest {

    private ProbeRegistry registry;
    private ObjectMapper mapper;

    @BeforeEach
    void setUp() {
        registry = new ProbeRegistry();
        mapper = new ObjectMapper();
    }

    // ============================================================
    // J-TEST-CORE-1: JavaProbe Serialization Tests
    // ============================================================

    @Test
    @DisplayName("Create JavaProbe with required fields")
    void testCreateJavaProbeWithRequiredFields() {
        JavaProbe probe = new JavaProbe();
        probe.setId("probe-1");
        probe.setFile("Test.java");
        probe.setClassName("com.example.Test");
        probe.setMethodName("testMethod");
        probe.setLine(42);

        assertEquals("probe-1", probe.getId());
        assertEquals("Test.java", probe.getFile());
        assertEquals("com.example.Test", probe.getClassName());
        assertEquals("testMethod", probe.getMethodName());
        assertEquals(42, probe.getLine());
        assertTrue(probe.isEnabled());
    }

    @Test
    @DisplayName("Create logpoint with message")
    void testCreateLogpointWithMessage() {
        JavaProbe probe = new JavaProbe();
        probe.setId("lp-1");
        probe.setMessage("User logged in: {user}");
        probe.setLine(10);

        assertTrue(probe.isLogpoint());
        assertEquals("User logged in: {user}", probe.getMessage());
    }

    @Test
    @DisplayName("Probe with condition expression")
    void testProbeWithCondition() {
        JavaProbe probe = new JavaProbe();
        probe.setCondition("x > 5 && y < 10");

        assertEquals("x > 5 && y < 10", probe.getCondition());
    }

    @Test
    @DisplayName("Probe with sample configuration")
    void testProbeWithSampleConfig() {
        JavaProbe probe = new JavaProbe();
        JavaProbe.SampleConfig sample = new JavaProbe.SampleConfig(20.0, 5);
        probe.setSample(sample);

        assertEquals(20.0, probe.getSample().limitPerSecond);
        assertEquals(5, probe.getSample().burst);
    }

    @Test
    @DisplayName("Probe with snapshot configuration")
    void testProbeWithSnapshotConfig() {
        JavaProbe probe = new JavaProbe();
        JavaProbe.SnapshotConfig snapshot = new JavaProbe.SnapshotConfig(true, Arrays.asList("field1", "field2"), true, 3, 25);
        probe.setSnapshot(snapshot);

        assertEquals(3, probe.getSnapshot().maxDepth);
        assertEquals(25, probe.getSnapshot().maxProps);
        assertTrue(probe.getSnapshot().params);
    }

    @Test
    @DisplayName("Probe JSON serialization round-trip")
    void testProbeJsonRoundTrip() throws Exception {
        JavaProbe original = new JavaProbe();
        original.setId("test-id");
        original.setFile("app.java");
        original.setClassName("App");
        original.setMethodName("main");
        original.setLine(100);
        original.setCondition("arg0 != null");
        original.setTags(Arrays.asList("critical", "perf"));

        String json = mapper.writeValueAsString(original);
        JavaProbe restored = mapper.readValue(json, JavaProbe.class);

        assertEquals(original.getId(), restored.getId());
        assertEquals(original.getFile(), restored.getFile());
        assertEquals(original.getClassName(), restored.getClassName());
        assertEquals(original.getCondition(), restored.getCondition());
        assertEquals(original.getTags(), restored.getTags());
    }

    @Test
    @DisplayName("Probe default values")
    void testProbeDefaults() {
        JavaProbe probe = new JavaProbe();

        assertNotNull(probe.getSample());
        assertNotNull(probe.getSnapshot());
        assertNotNull(probe.getTags());
        assertTrue(probe.isEnabled());
        assertFalse(probe.isLogpoint());
    }

    // ============================================================
    // J-TEST-CORE-2: ProbeRegistry Tests
    // ============================================================

    @Test
    @DisplayName("Upsert probe into empty registry")
    void testUpsertProbeIntoEmptyRegistry() {
        JavaProbe probe = new JavaProbe();
        probe.setId("p1");
        probe.setClassName("Test");

        registry.upsert(probe);

        assertEquals(1, registry.size());
        assertEquals(probe, registry.getProbe("p1"));
    }

    @Test
    @DisplayName("Upsert replaces existing probe with same ID")
    void testUpsertReplaceExistingProbe() {
        JavaProbe probe1 = new JavaProbe();
        probe1.setId("p1");
        probe1.setLine(10);

        JavaProbe probe2 = new JavaProbe();
        probe2.setId("p1");
        probe2.setLine(20);

        registry.upsert(probe1);
        registry.upsert(probe2);

        assertEquals(1, registry.size());
        assertEquals(20, registry.getProbe("p1").getLine());
    }

    @Test
    @DisplayName("Get probes by class name")
    void testGetProbesByClassName() {
        JavaProbe p1 = new JavaProbe();
        p1.setId("p1");
        p1.setClassName("TestA");
        p1.setLine(1);

        JavaProbe p2 = new JavaProbe();
        p2.setId("p2");
        p2.setClassName("TestA");
        p2.setLine(2);

        JavaProbe p3 = new JavaProbe();
        p3.setId("p3");
        p3.setClassName("TestB");
        p3.setLine(3);

        registry.upsert(p1);
        registry.upsert(p2);
        registry.upsert(p3);

        List<JavaProbe> testAProbes = registry.getProbesForClass("TestA");
        assertEquals(2, testAProbes.size());
        assertTrue(testAProbes.stream().allMatch(p -> p.getClassName().equals("TestA")));
    }

    @Test
    @DisplayName("Remove probe from registry")
    void testRemoveProbe() {
        JavaProbe probe = new JavaProbe();
        probe.setId("p1");
        probe.setClassName("Test");

        registry.upsert(probe);
        assertEquals(1, registry.size());

        registry.remove("p1");
        assertEquals(0, registry.size());
        assertNull(registry.getProbe("p1"));
    }

    @Test
    @DisplayName("Registry thread safety - concurrent upserts")
    void testRegistryThreadSafety() throws InterruptedException {
        Thread[] threads = new Thread[10];
        for (int i = 0; i < 10; i++) {
            final int id = i;
            threads[i] = new Thread(() -> {
                JavaProbe probe = new JavaProbe();
                probe.setId("p" + id);
                probe.setClassName("Test");
                registry.upsert(probe);
            });
        }

        for (Thread t : threads) {
            t.start();
        }

        for (Thread t : threads) {
            t.join();
        }

        assertEquals(10, registry.size());
    }

    @Test
    @DisplayName("Has probes for class returns correct value")
    void testHasProbesForClass() {
        JavaProbe probe = new JavaProbe();
        probe.setId("p1");
        probe.setClassName("Test");

        assertFalse(registry.hasProbesForClass("Test"));
        registry.upsert(probe);
        assertTrue(registry.hasProbesForClass("Test"));
    }

    @Test
    @DisplayName("Clear registry")
    void testClearRegistry() {
        JavaProbe p1 = new JavaProbe();
        p1.setId("p1");
        p1.setClassName("Test");

        registry.upsert(p1);
        assertEquals(1, registry.size());

        registry.clear();
        assertEquals(0, registry.size());
        assertNull(registry.getProbe("p1"));
    }

    @Test
    @DisplayName("Get all probes")
    void testGetAllProbes() {
        JavaProbe p1 = new JavaProbe();
        p1.setId("p1");

        JavaProbe p2 = new JavaProbe();
        p2.setId("p2");

        registry.upsert(p1);
        registry.upsert(p2);

        Collection<JavaProbe> all = registry.getAllProbes();
        assertEquals(2, all.size());
    }
}

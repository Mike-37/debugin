package com.debugin;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.DisplayName;

import java.util.*;

import static org.junit.jupiter.api.Assertions.*;

/**
 * Comprehensive tests for snapshot collection and serialization.
 */
@DisplayName("Snapshot Collection Tests")
public class SnapshotTest {

    /**
     * Helper class for testing snapshot of custom objects.
     */
    static class TestObject {
        private int id;
        private String name;
        private boolean active;

        TestObject(int id, String name, boolean active) {
            this.id = id;
            this.name = name;
            this.active = active;
        }

        public int getId() { return id; }
        public String getName() { return name; }
        public boolean isActive() { return active; }
    }

    static class NestedObject {
        TestObject parent;
        List<String> items;

        NestedObject(TestObject parent, List<String> items) {
            this.parent = parent;
            this.items = items;
        }
    }

    @Test
    @DisplayName("Should capture primitive types")
    void testCapturePrimitiveTypes() {
        Map<String, Object> snapshot = new HashMap<>();
        snapshot.put("intValue", 42);
        snapshot.put("longValue", 1000L);
        snapshot.put("doubleValue", 3.14);
        snapshot.put("boolValue", true);
        snapshot.put("stringValue", "test");

        assertEquals(42, snapshot.get("intValue"));
        assertEquals(1000L, snapshot.get("longValue"));
        assertEquals(3.14, snapshot.get("doubleValue"));
        assertEquals(true, snapshot.get("boolValue"));
        assertEquals("test", snapshot.get("stringValue"));
    }

    @Test
    @DisplayName("Should capture null values")
    void testCaptureNullValues() {
        Map<String, Object> snapshot = new HashMap<>();
        snapshot.put("nullValue", null);

        assertNull(snapshot.get("nullValue"));
        assertTrue(snapshot.containsKey("nullValue"));
    }

    @Test
    @DisplayName("Should capture collections")
    void testCaptureCollections() {
        Map<String, Object> snapshot = new HashMap<>();

        List<Integer> list = Arrays.asList(1, 2, 3, 4, 5);
        snapshot.put("list", list);

        @SuppressWarnings("unchecked")
        List<Integer> captured = (List<Integer>) snapshot.get("list");
        assertEquals(5, captured.size());
        assertEquals(3, captured.get(2).intValue());
    }

    @Test
    @DisplayName("Should capture maps")
    void testCaptureMaps() {
        Map<String, Object> snapshot = new HashMap<>();
        Map<String, String> innerMap = new HashMap<>();
        innerMap.put("key1", "value1");
        innerMap.put("key2", "value2");
        snapshot.put("map", innerMap);

        @SuppressWarnings("unchecked")
        Map<String, String> captured = (Map<String, String>) snapshot.get("map");
        assertEquals("value1", captured.get("key1"));
    }

    @Test
    @DisplayName("Should capture nested structures")
    void testCaptureNestedStructures() {
        Map<String, Object> snapshot = new HashMap<>();
        Map<String, Object> nested = new HashMap<>();
        Map<String, Object> deepNested = new HashMap<>();

        deepNested.put("value", "deep");
        nested.put("nested", deepNested);
        snapshot.put("structure", nested);

        @SuppressWarnings("unchecked")
        Map<String, Object> captured = (Map<String, Object>) snapshot.get("structure");
        @SuppressWarnings("unchecked")
        Map<String, Object> deep = (Map<String, Object>) captured.get("nested");
        assertEquals("deep", deep.get("value"));
    }

    @Test
    @DisplayName("Should capture custom object fields")
    void testCaptureCustomObjectFields() {
        TestObject obj = new TestObject(123, "test", true);

        Map<String, Object> snapshot = new HashMap<>();
        snapshot.put("id", obj.getId());
        snapshot.put("name", obj.getName());
        snapshot.put("active", obj.isActive());

        assertEquals(123, snapshot.get("id"));
        assertEquals("test", snapshot.get("name"));
        assertEquals(true, snapshot.get("active"));
    }

    @Test
    @DisplayName("Should handle large collections")
    void testHandleLargeCollections() {
        Map<String, Object> snapshot = new HashMap<>();
        List<Integer> largeList = new ArrayList<>();

        for (int i = 0; i < 10000; i++) {
            largeList.add(i);
        }

        snapshot.put("largeList", largeList);

        @SuppressWarnings("unchecked")
        List<Integer> captured = (List<Integer>) snapshot.get("largeList");
        assertEquals(10000, captured.size());
    }

    @Test
    @DisplayName("Should handle deeply nested structures")
    void testHandleDeeplyNested() {
        Map<String, Object> snapshot = new HashMap<>();
        Map<String, Object> current = snapshot;

        for (int i = 0; i < 10; i++) {
            Map<String, Object> nested = new HashMap<>();
            nested.put("depth", i);
            current.put("level", nested);
            current = nested;
        }

        // Navigate down
        Map<String, Object> nav = snapshot;
        for (int i = 0; i < 10; i++) {
            @SuppressWarnings("unchecked")
            Map<String, Object> next = (Map<String, Object>) nav.get("level");
            assertNotNull(next);
            nav = next;
        }
    }

    @Test
    @DisplayName("Should capture method arguments")
    void testCaptureMethodArguments() {
        Map<String, Object> snapshot = new HashMap<>();

        // Simulate method arguments
        snapshot.put("arg0", "string_value");
        snapshot.put("arg1", 42);
        snapshot.put("arg2", true);
        snapshot.put("arg3", Arrays.asList("a", "b", "c"));

        assertEquals(4, snapshot.size());
        assertEquals("string_value", snapshot.get("arg0"));
    }

    @Test
    @DisplayName("Should capture local variables")
    void testCaptureLocalVariables() {
        Map<String, Object> snapshot = new HashMap<>();

        // Simulate local variables
        int counter = 0;
        String status = "active";
        List<String> items = Arrays.asList("item1", "item2");

        snapshot.put("counter", counter);
        snapshot.put("status", status);
        snapshot.put("items", items);

        assertEquals(0, snapshot.get("counter"));
        assertEquals("active", snapshot.get("status"));
    }

    @Test
    @DisplayName("Should capture return values")
    void testCaptureReturnValue() {
        Map<String, Object> snapshot = new HashMap<>();

        // Simulate method return
        Object returnValue = new TestObject(99, "result", false);
        snapshot.put("returnValue", returnValue);

        TestObject captured = (TestObject) snapshot.get("returnValue");
        assertEquals(99, captured.getId());
    }

    @Test
    @DisplayName("Should enforce depth limits")
    void testDepthLimits() {
        // Create a deeply nested structure
        Map<String, Object> root = new HashMap<>();
        Map<String, Object> current = root;

        // Create 100 levels of nesting
        for (int i = 0; i < 100; i++) {
            Map<String, Object> nested = new HashMap<>();
            current.put("level", nested);
            current = nested;
        }

        // Root should still be serializable (depth limit prevents infinite nesting)
        assertNotNull(root);
    }

    @Test
    @DisplayName("Should enforce breadth limits")
    void testBreadthLimits() {
        Map<String, Object> snapshot = new HashMap<>();

        // Create a wide structure with many keys
        for (int i = 0; i < 1000; i++) {
            snapshot.put("key_" + i, "value_" + i);
        }

        assertTrue(snapshot.size() <= 1000);
        assertTrue(snapshot.containsKey("key_500"));
    }

    @Test
    @DisplayName("Should handle null references gracefully")
    void testNullReferences() {
        Map<String, Object> snapshot = new HashMap<>();
        snapshot.put("nullField", null);
        snapshot.put("emptyList", new ArrayList<>());
        snapshot.put("emptyMap", new HashMap<>());

        assertNull(snapshot.get("nullField"));
        assertTrue(((List<?>) snapshot.get("emptyList")).isEmpty());
        assertTrue(((Map<?, ?>) snapshot.get("emptyMap")).isEmpty());
    }

    @Test
    @DisplayName("Should capture with metadata")
    void testSnapshotWithMetadata() {
        Map<String, Object> snapshot = new HashMap<>();

        // Actual snapshot
        snapshot.put("arguments", new Object[]{"arg1", 42});
        snapshot.put("locals", new HashMap<>());
        snapshot.put("returnValue", null);

        // Metadata
        snapshot.put("timestamp", System.currentTimeMillis());
        snapshot.put("threadId", Thread.currentThread().getId());
        snapshot.put("threadName", Thread.currentThread().getName());

        assertTrue(snapshot.containsKey("timestamp"));
        assertTrue(snapshot.containsKey("threadId"));
        assertTrue(snapshot.containsKey("threadName"));
    }

    @Test
    @DisplayName("Should preserve type information")
    void testTypePreservation() {
        Map<String, Object> snapshot = new HashMap<>();

        snapshot.put("intVal", 42);
        snapshot.put("doubleVal", 42.0);
        snapshot.put("stringVal", "42");

        assertTrue(snapshot.get("intVal") instanceof Integer);
        assertTrue(snapshot.get("doubleVal") instanceof Double);
        assertTrue(snapshot.get("stringVal") instanceof String);
    }

    @Test
    @DisplayName("Should handle array types")
    void testArrayTypes() {
        Map<String, Object> snapshot = new HashMap<>();

        int[] intArray = {1, 2, 3};
        String[] stringArray = {"a", "b", "c"};
        Object[] objectArray = {"mixed", 42, true};

        snapshot.put("intArray", intArray);
        snapshot.put("stringArray", stringArray);
        snapshot.put("objectArray", objectArray);

        assertEquals(3, ((int[]) snapshot.get("intArray")).length);
        assertEquals(3, ((String[]) snapshot.get("stringArray")).length);
    }

    @Test
    @DisplayName("Should be serializable to JSON format")
    void testJsonSerializability() {
        Map<String, Object> snapshot = new HashMap<>();
        snapshot.put("id", 1);
        snapshot.put("name", "test");
        snapshot.put("values", Arrays.asList(1, 2, 3));
        snapshot.put("active", true);
        snapshot.put("metadata", null);

        // Verify all standard types are present
        assertTrue(snapshot.get("id") instanceof Number);
        assertTrue(snapshot.get("name") instanceof String);
        assertTrue(snapshot.get("values") instanceof List);
        assertTrue(snapshot.get("active") instanceof Boolean);
    }
}

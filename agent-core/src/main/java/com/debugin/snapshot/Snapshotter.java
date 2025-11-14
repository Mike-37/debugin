package com.debugin.snapshot;

import com.debugin.probe.JavaProbe;
import java.util.*;
import java.util.logging.Logger;

/**
 * Captures snapshots of method parameters, fields, and local variables.
 * Enforces depth and property limits while detecting cycles.
 */
public class Snapshotter {
    private static final Logger logger = Logger.getLogger(Snapshotter.class.getName());

    private final JavaProbe.SnapshotConfig config;
    private final Set<Integer> visitedObjects = new HashSet<>();

    public Snapshotter(JavaProbe.SnapshotConfig config) {
        this.config = config != null ? config : new JavaProbe.SnapshotConfig();
    }

    /**
     * Capture a snapshot of arguments, this, and locals
     */
    public Map<String, Object> captureSnapshot(Object thiz, Object[] args, Map<String, Object> locals) {
        visitedObjects.clear();
        Map<String, Object> snapshot = new LinkedHashMap<>();

        if (config.params && args != null) {
            for (int i = 0; i < args.length; i++) {
                snapshot.put("arg" + i, safeSerialize(args[i], 0));
            }
        }

        if (thiz != null && config.locals) {
            snapshot.put("this", safeSerialize(thiz, 0));
        }

        if (locals != null) {
            for (Map.Entry<String, Object> entry : locals.entrySet()) {
                snapshot.put(entry.getKey(), safeSerialize(entry.getValue(), 0));
            }
        }

        return snapshot;
    }

    /**
     * Safely serialize an object, respecting depth and property limits
     */
    private Object safeSerialize(Object obj, int depth) {
        if (obj == null) {
            return null;
        }

        // Check depth limit
        if (depth >= config.maxDepth) {
            return "[depth limit reached]";
        }

        // Detect cycles
        int objHash = System.identityHashCode(obj);
        if (visitedObjects.contains(objHash)) {
            return "[cyclic reference]";
        }

        // Handle primitives and strings
        if (obj instanceof String || obj instanceof Number || obj instanceof Boolean) {
            return obj;
        }

        visitedObjects.add(objHash);

        try {
            if (obj instanceof Map) {
                return serializeMap((Map<?, ?>) obj, depth);
            } else if (obj instanceof Collection) {
                return serializeCollection((Collection<?>) obj, depth);
            } else if (obj instanceof Object[]) {
                return serializeArray((Object[]) obj, depth);
            } else {
                return serializeObject(obj, depth);
            }
        } finally {
            visitedObjects.remove(objHash);
        }
    }

    private Object serializeMap(Map<?, ?> map, int depth) {
        Map<String, Object> result = new LinkedHashMap<>();
        int count = 0;

        for (Map.Entry<?, ?> entry : map.entrySet()) {
            if (count >= config.maxProps) {
                result.put("__truncated__", true);
                break;
            }
            String key = String.valueOf(entry.getKey());
            result.put(key, safeSerialize(entry.getValue(), depth + 1));
            count++;
        }

        return result;
    }

    private Object serializeCollection(Collection<?> coll, int depth) {
        List<Object> result = new ArrayList<>();
        int count = 0;

        for (Object item : coll) {
            if (count >= config.maxProps) {
                result.add(Collections.singletonMap("__truncated__", true));
                break;
            }
            result.add(safeSerialize(item, depth + 1));
            count++;
        }

        return result;
    }

    private Object serializeArray(Object[] arr, int depth) {
        List<Object> result = new ArrayList<>();
        int count = 0;

        for (Object item : arr) {
            if (count >= config.maxProps) {
                result.add(Collections.singletonMap("__truncated__", true));
                break;
            }
            result.add(safeSerialize(item, depth + 1));
            count++;
        }

        return result;
    }

    private Object serializeObject(Object obj, int depth) {
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("__class__", obj.getClass().getName());

        // Try to get fields using reflection
        try {
            Class<?> clazz = obj.getClass();
            java.lang.reflect.Field[] fields = clazz.getDeclaredFields();
            int count = 0;

            for (java.lang.reflect.Field field : fields) {
                if (count >= config.maxProps) {
                    result.put("__truncated__", true);
                    break;
                }

                // Skip if field is not in snapshot config
                if (!config.fields.isEmpty() && !config.fields.contains(field.getName())) {
                    continue;
                }

                field.setAccessible(true);
                try {
                    Object value = field.get(obj);
                    result.put(field.getName(), safeSerialize(value, depth + 1));
                    count++;
                } catch (IllegalAccessException e) {
                    result.put(field.getName(), "[access denied]");
                }
            }
        } catch (Exception e) {
            result.put("__error__", e.getMessage());
        }

        return result;
    }
}

package com.debugin.probe;

import java.util.*;
import java.util.concurrent.ConcurrentHashMap;

/**
 * Central registry for managing probes, keyed by internal class name and probe ID.
 * Thread-safe for concurrent access.
 */
public class ProbeRegistry {

    // Maps className -> (probeId -> JavaProbe)
    private final Map<String, Map<String, JavaProbe>> probesByClass = new ConcurrentHashMap<>();

    // Maps probeId -> JavaProbe for fast global lookup
    private final Map<String, JavaProbe> probesById = new ConcurrentHashMap<>();

    /**
     * Upsert a probe into the registry
     */
    public synchronized void upsert(JavaProbe probe) {
        if (probe == null || probe.getId() == null) {
            throw new IllegalArgumentException("Probe must have an id");
        }

        String probeId = probe.getId();
        String className = probe.getClassName();

        // Store globally
        probesById.put(probeId, probe);

        // Store by class
        if (className != null) {
            probesByClass.computeIfAbsent(className, k -> new ConcurrentHashMap<>())
                    .put(probeId, probe);
        }
    }

    /**
     * Remove a probe from the registry
     */
    public synchronized void remove(String probeId) {
        if (probeId == null) {
            return;
        }

        JavaProbe removed = probesById.remove(probeId);
        if (removed != null) {
            String className = removed.getClassName();
            if (className != null) {
                Map<String, JavaProbe> classProbes = probesByClass.get(className);
                if (classProbes != null) {
                    classProbes.remove(probeId);
                    if (classProbes.isEmpty()) {
                        probesByClass.remove(className);
                    }
                }
            }
        }
    }

    /**
     * Get all probes for a specific class
     */
    public List<JavaProbe> getProbesForClass(String internalClassName) {
        Map<String, JavaProbe> classProbes = probesByClass.get(internalClassName);
        if (classProbes == null) {
            return Collections.emptyList();
        }
        return new ArrayList<>(classProbes.values());
    }

    /**
     * Get a specific probe by ID
     */
    public JavaProbe getProbe(String probeId) {
        return probesById.get(probeId);
    }

    /**
     * Get all probes
     */
    public Collection<JavaProbe> getAllProbes() {
        return new ArrayList<>(probesById.values());
    }

    /**
     * Check if a class has any probes
     */
    public boolean hasProbesForClass(String internalClassName) {
        Map<String, JavaProbe> classProbes = probesByClass.get(internalClassName);
        return classProbes != null && !classProbes.isEmpty();
    }

    /**
     * Clear all probes
     */
    public synchronized void clear() {
        probesByClass.clear();
        probesById.clear();
    }

    /**
     * Get total probe count
     */
    public int size() {
        return probesById.size();
    }
}

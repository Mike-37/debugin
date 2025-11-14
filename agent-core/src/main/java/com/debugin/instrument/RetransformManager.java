package com.debugin.instrument;

import com.debugin.probe.JavaProbe;
import com.debugin.probe.ProbeRegistry;
import java.lang.instrument.Instrumentation;
import java.lang.instrument.UnmodifiableClassException;
import java.util.*;
import java.util.logging.Logger;
import java.util.logging.Level;

/**
 * Manages class retransformation when probes are added or removed.
 * Uses java.lang.instrument.Instrumentation to trigger class file retransformation.
 */
public class RetransformManager {
    private static final Logger logger = Logger.getLogger(RetransformManager.class.getName());

    private final Instrumentation instrumentation;
    private final ProbeRegistry probeRegistry;

    public RetransformManager(Instrumentation instrumentation, ProbeRegistry probeRegistry) {
        this.instrumentation = instrumentation;
        this.probeRegistry = probeRegistry;
    }

    /**
     * Retransform all classes affected by a probe
     */
    public void retransformForProbe(JavaProbe probe) {
        if (probe == null || probe.getClassName() == null) {
            return;
        }
        retransformForClass(probe.getClassName());
    }

    /**
     * Retransform classes matching the given name
     */
    public void retransformForClass(String className) {
        if (className == null || !instrumentation.isRetransformClassesSupported()) {
            logger.warning("Class retransformation not supported");
            return;
        }

        try {
            // Find all loaded classes matching this name
            Class<?>[] loadedClasses = instrumentation.getAllLoadedClasses();
            List<Class<?>> toRetransform = new ArrayList<>();

            String internalName = className.replace('.', '/');

            for (Class<?> clazz : loadedClasses) {
                if (clazz.getName().equals(className) ||
                    clazz.getName().replace('.', '/').equals(internalName)) {
                    toRetransform.add(clazz);
                }
            }

            if (!toRetransform.isEmpty()) {
                instrumentation.retransformClasses(toRetransform.toArray(new Class<?>[0]));
                logger.info("Retransformed " + toRetransform.size() + " classes for " + className);
            }
        } catch (UnmodifiableClassException e) {
            logger.log(Level.WARNING, "Failed to retransform class: " + className, e);
        }
    }

    /**
     * Retransform all classes that have probes
     */
    public void retransformAll() {
        Collection<JavaProbe> probes = probeRegistry.getAllProbes();
        Set<String> classNames = new HashSet<>();

        for (JavaProbe probe : probes) {
            if (probe.getClassName() != null) {
                classNames.add(probe.getClassName());
            }
        }

        for (String className : classNames) {
            retransformForClass(className);
        }
    }

    /**
     * Check if retransformation is supported
     */
    public boolean isRetransformSupported() {
        return instrumentation.isRetransformClassesSupported();
    }

    /**
     * Get the underlying Instrumentation instance
     */
    public Instrumentation getInstrumentation() {
        return instrumentation;
    }
}

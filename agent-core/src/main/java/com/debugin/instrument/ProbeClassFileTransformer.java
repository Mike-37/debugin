package com.debugin.instrument;

import com.debugin.probe.JavaProbe;
import com.debugin.probe.ProbeRegistry;
import java.lang.instrument.ClassFileTransformer;
import java.lang.instrument.IllegalClassFormatException;
import java.security.ProtectionDomain;
import java.util.List;
import java.util.logging.Logger;
import java.util.logging.Level;

/**
 * A ClassFileTransformer that uses the ProbeRegistry to decide whether to transform a class
 * and delegates to AsmLineProbeWeaver for actual bytecode modifications.
 */
public class ProbeClassFileTransformer implements ClassFileTransformer {
    private static final Logger logger = Logger.getLogger(ProbeClassFileTransformer.class.getName());

    private final ProbeRegistry probeRegistry;

    public ProbeClassFileTransformer(ProbeRegistry probeRegistry) {
        this.probeRegistry = probeRegistry;
    }

    @Override
    public byte[] transform(ClassLoader loader, String className, Class<?> classBeingRedefined,
                           ProtectionDomain protectionDomain, byte[] classfileBuffer)
            throws IllegalClassFormatException {
        try {
            return transformClass(className, classfileBuffer);
        } catch (Exception e) {
            logger.log(Level.WARNING, "Error transforming class " + className, e);
            return null;  // Return null to leave class unchanged on error
        }
    }

    /**
     * Transform a single class if probes exist for it
     */
    private byte[] transformClass(String className, byte[] classfileBuffer) {
        // Convert class name to internal format (dots to slashes)
        String internalName = className.replace('.', '/');

        // Check if there are any probes for this class
        List<JavaProbe> probes = probeRegistry.getProbesForClass(className);
        if (probes.isEmpty()) {
            // No probes for this class, return null to indicate no transformation
            return null;
        }

        try {
            // Use AsmLineProbeWeaver to perform the actual bytecode manipulation
            AsmLineProbeWeaver weaver = new AsmLineProbeWeaver(internalName, probes);
            byte[] transformedBytes = weaver.weave(classfileBuffer);

            logger.info("Transformed class " + className + " with " + probes.size() + " probes");
            return transformedBytes;
        } catch (Exception e) {
            logger.log(Level.WARNING, "Failed to weave probes into class " + className, e);
            return null;
        }
    }

    @Override
    public String toString() {
        return "ProbeClassFileTransformer{" +
                "probes=" + probeRegistry.size() +
                '}';
    }
}

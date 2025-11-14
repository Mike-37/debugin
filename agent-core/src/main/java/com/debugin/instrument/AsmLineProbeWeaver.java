package com.debugin.instrument;

import com.debugin.probe.JavaProbe;
import org.objectweb.asm.ClassReader;
import org.objectweb.asm.ClassWriter;
import org.objectweb.asm.ClassVisitor;
import org.objectweb.asm.MethodVisitor;
import org.objectweb.asm.Opcodes;
import java.util.*;
import java.util.logging.Logger;

/**
 * ASM-based bytecode weaver that injects ProbeVM.hit calls at target line numbers.
 * Inserts probe hit recording at the start of basic blocks for instrumented lines.
 */
public class AsmLineProbeWeaver {
    private static final Logger logger = Logger.getLogger(AsmLineProbeWeaver.class.getName());

    private final String internalClassName;
    private final List<JavaProbe> probes;
    private final Set<Integer> targetLines;

    public AsmLineProbeWeaver(String internalClassName, List<JavaProbe> probes) {
        this.internalClassName = internalClassName;
        this.probes = new ArrayList<>(probes);
        this.targetLines = new HashSet<>();
        for (JavaProbe probe : probes) {
            targetLines.add(probe.getLine());
        }
    }

    /**
     * Perform the bytecode weaving
     */
    public byte[] weave(byte[] classBytes) {
        try {
            ClassReader reader = new ClassReader(classBytes);
            ClassWriter writer = new ClassWriter(ClassWriter.COMPUTE_MAXS);
            ProbeInjectingVisitor visitor = new ProbeInjectingVisitor(writer, internalClassName, probes, targetLines);
            reader.accept(visitor, 0);
            return writer.toByteArray();
        } catch (Exception e) {
            logger.warning("Failed to weave bytecode: " + e.getMessage());
            return classBytes;  // Return original if weaving fails
        }
    }

    /**
     * ClassVisitor that injects probe calls
     */
    private static class ProbeInjectingVisitor extends ClassVisitor {
        private final String internalClassName;
        private final List<JavaProbe> probes;
        private final Set<Integer> targetLines;

        ProbeInjectingVisitor(ClassVisitor cv, String internalClassName, List<JavaProbe> probes, Set<Integer> targetLines) {
            super(Opcodes.ASM9, cv);
            this.internalClassName = internalClassName;
            this.probes = probes;
            this.targetLines = targetLines;
        }

        @Override
        public MethodVisitor visitMethod(int access, String name, String descriptor, String signature, String[] exceptions) {
            MethodVisitor mv = super.visitMethod(access, name, descriptor, signature, exceptions);
            return new ProbeInjectingMethodVisitor(mv, access, name, descriptor, internalClassName, probes, targetLines);
        }
    }

    /**
     * MethodVisitor that injects probe calls at target lines
     */
    private static class ProbeInjectingMethodVisitor extends MethodVisitor {
        private final int access;
        private final String methodName;
        private final String descriptor;
        private final String internalClassName;
        private final List<JavaProbe> probes;
        private final Set<Integer> targetLines;
        private int currentLine = 0;
        private boolean injectedAtLine = false;

        ProbeInjectingMethodVisitor(MethodVisitor mv, int access, String name, String descriptor,
                                   String internalClassName, List<JavaProbe> probes, Set<Integer> targetLines) {
            super(Opcodes.ASM9, mv);
            this.access = access;
            this.methodName = name;
            this.descriptor = descriptor;
            this.internalClassName = internalClassName;
            this.probes = probes;
            this.targetLines = targetLines;
        }

        @Override
        public void visitLineNumber(int line, org.objectweb.asm.Label start) {
            super.visitLineNumber(line, start);
            this.currentLine = line;
            this.injectedAtLine = false;
        }

        @Override
        public void visitCode() {
            super.visitCode();
            // Inject at method entry if line 0 or if first line is a target
            if (targetLines.contains(0) || (currentLine == 0 && !targetLines.isEmpty())) {
                injectProbeCall(null);
            }
        }

        @Override
        public void visitInsn(int opcode) {
            // Inject before instructions at target line
            if (!injectedAtLine && targetLines.contains(currentLine)) {
                injectProbeCall(null);
                injectedAtLine = true;
            }
            super.visitInsn(opcode);
        }

        /**
         * Inject a ProbeVM.hit call
         */
        private void injectProbeCall(String probeId) {
            // Find a probe for the current line
            JavaProbe matchingProbe = null;
            for (JavaProbe probe : probes) {
                if (probe.getLine() == currentLine && probe.getClassName().replace('.', '/').equals(internalClassName)) {
                    matchingProbe = probe;
                    break;
                }
            }

            if (matchingProbe != null) {
                // Push the probe ID
                mv.visitLdcInsn(matchingProbe.getId());
                // Call ProbeVM.hit(probeId, null, null)
                mv.visitInsn(Opcodes.ACONST_NULL);  // this = null for static context
                mv.visitInsn(Opcodes.ACONST_NULL);  // args = null
                mv.visitMethodInsn(Opcodes.INVOKESTATIC,
                        "com/debugin/ProbeVM",
                        "hit",
                        "(Ljava/lang/String;Ljava/lang/Object;[Ljava/lang/Object;)V",
                        false);
            }
        }
    }
}

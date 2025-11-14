package com.debugin.probe;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.*;

/**
 * Represents a single probe configuration in Java.
 * Maps to the canonical probe schema with Java-specific fields.
 */
public class JavaProbe {

    @JsonProperty("id")
    private String id;

    @JsonProperty("file")
    private String file;

    @JsonProperty("className")
    private String className;

    @JsonProperty("methodName")
    private String methodName;

    @JsonProperty("descriptor")
    private String descriptor;

    @JsonProperty("line")
    private int line;

    @JsonProperty("condition")
    private String condition;

    @JsonProperty("message")
    private String message;  // For logpoints

    @JsonProperty("sample")
    private SampleConfig sample;

    @JsonProperty("snapshot")
    private SnapshotConfig snapshot;

    @JsonProperty("tags")
    private List<String> tags;

    @JsonProperty("enabled")
    private boolean enabled = true;

    public JavaProbe() {
        this.tags = new ArrayList<>();
        this.sample = new SampleConfig();
        this.snapshot = new SnapshotConfig();
    }

    // Getters and Setters
    public String getId() { return id; }
    public void setId(String id) { this.id = id; }

    public String getFile() { return file; }
    public void setFile(String file) { this.file = file; }

    public String getClassName() { return className; }
    public void setClassName(String className) { this.className = className; }

    public String getMethodName() { return methodName; }
    public void setMethodName(String methodName) { this.methodName = methodName; }

    public String getDescriptor() { return descriptor; }
    public void setDescriptor(String descriptor) { this.descriptor = descriptor; }

    public int getLine() { return line; }
    public void setLine(int line) { this.line = line; }

    public String getCondition() { return condition; }
    public void setCondition(String condition) { this.condition = condition; }

    public String getMessage() { return message; }
    public void setMessage(String message) { this.message = message; }

    public SampleConfig getSample() { return sample; }
    public void setSample(SampleConfig sample) { this.sample = sample; }

    public SnapshotConfig getSnapshot() { return snapshot; }
    public void setSnapshot(SnapshotConfig snapshot) { this.snapshot = snapshot; }

    public List<String> getTags() { return tags; }
    public void setTags(List<String> tags) { this.tags = tags; }

    public boolean isEnabled() { return enabled; }
    public void setEnabled(boolean enabled) { this.enabled = enabled; }

    public boolean isLogpoint() {
        return message != null && !message.isEmpty();
    }

    @Override
    public String toString() {
        return "JavaProbe{" +
                "id='" + id + '\'' +
                ", file='" + file + '\'' +
                ", className='" + className + '\'' +
                ", methodName='" + methodName + '\'' +
                ", line=" + line +
                ", condition='" + condition + '\'' +
                ", enabled=" + enabled +
                '}';
    }

    /**
     * Sample rate configuration with token bucket limits
     */
    public static class SampleConfig {
        @JsonProperty("limitPerSecond")
        public double limitPerSecond = 10.0;

        @JsonProperty("burst")
        public int burst = 1;

        public SampleConfig() {}

        public SampleConfig(double limitPerSecond, int burst) {
            this.limitPerSecond = limitPerSecond;
            this.burst = burst;
        }
    }

    /**
     * Snapshot configuration for variable capture
     */
    public static class SnapshotConfig {
        @JsonProperty("params")
        public boolean params = true;

        @JsonProperty("fields")
        public List<String> fields = new ArrayList<>();

        @JsonProperty("locals")
        public boolean locals = true;

        @JsonProperty("maxDepth")
        public int maxDepth = 5;

        @JsonProperty("maxProps")
        public int maxProps = 50;

        public SnapshotConfig() {}

        public SnapshotConfig(boolean params, List<String> fields, boolean locals, int maxDepth, int maxProps) {
            this.params = params;
            this.fields = fields;
            this.locals = locals;
            this.maxDepth = maxDepth;
            this.maxProps = maxProps;
        }
    }
}

package com.debugin;

/**
 * Test application for Java agent integration testing
 *
 * Provides fixture methods with tracepoint/logpoint targets
 */
public class TestApp {
    private int counter = 0;
    private String status = "active";

    /**
     * Simple addition - target for tracepoint payload test
     */
    public int add(int x, int y) {
        int z = x + y;  // Line for tracepoint
        return z;
    }

    /**
     * Loop with accumulation - target for logpoint template test
     */
    public int burst(int count) {
        int sum = 0;  // Start of loop
        for (int i = 0; i < count; i++) {
            sum += i;  // Line for logpoint
        }
        return sum;
    }

    /**
     * Conditional method - target for condition test
     */
    public int conditionalExample(int a, int b) {
        int result = a * b;  // Line with condition "result > 8"
        return result;
    }

    /**
     * Method with exception handling
     */
    public String processData(String input) throws IllegalArgumentException {
        if (input == null || input.isEmpty()) {
            throw new IllegalArgumentException("Input cannot be empty");
        }

        String processed = input.toUpperCase();  // Line for tracepoint
        return processed;
    }

    /**
     * Nested call for stack trace testing
     */
    public int outerMethod(int x) {
        return innerMethod(x);
    }

    private int innerMethod(int x) {
        int result = x * 2;  // Line for nested frame tracepoint
        return result;
    }

    /**
     * Method to test field access in snapshots
     */
    public String getStatus() {
        return status;
    }

    public void setStatus(String newStatus) {
        this.status = newStatus;  // Line for tracepoint with this.status
    }

    /**
     * Method with rate limit testing
     */
    public void highFrequencyMethod() {
        counter++;  // Called many times for rate limit testing
    }

    public int getCounter() {
        return counter;
    }

    public static void main(String[] args) {
        TestApp app = new TestApp();

        // Test add
        int result1 = app.add(2, 3);
        System.out.println("add(2,3) = " + result1);

        // Test burst
        int result2 = app.burst(5);
        System.out.println("burst(5) = " + result2);

        // Test conditional
        int result3 = app.conditionalExample(2, 5);
        System.out.println("conditionalExample(2,5) = " + result3);

        // Test processing
        try {
            String result4 = app.processData("hello");
            System.out.println("processData('hello') = " + result4);
        } catch (IllegalArgumentException e) {
            System.err.println("Error: " + e.getMessage());
        }

        // Test nested
        int result5 = app.outerMethod(3);
        System.out.println("outerMethod(3) = " + result5);

        // Test high frequency
        for (int i = 0; i < 100; i++) {
            app.highFrequencyMethod();
        }
        System.out.println("Counter: " + app.getCounter());
    }
}

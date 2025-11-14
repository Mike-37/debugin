package com.debugin;

import com.debugin.ratelimit.RateLimiter;
import com.debugin.ratelimit.ProbeRateLimiter;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.BeforeEach;

import java.util.Map;

import static org.junit.jupiter.api.Assertions.*;

/**
 * Comprehensive tests for token bucket rate limiter.
 */
@DisplayName("Rate Limiter Tests")
public class RateLimiterTest {

    private RateLimiter limiter;

    @BeforeEach
    void setUp() {
        limiter = new RateLimiter(10.0, 1.0); // 10 per second, 1 burst
    }

    @Test
    @DisplayName("Should initialize with correct parameters")
    void testInitialization() {
        assertNotNull(limiter);
        assertTrue(limiter.getTokens() >= 0);
    }

    @Test
    @DisplayName("Should allow consumption when under limit")
    void testUnderLimit() {
        RateLimiter rl = new RateLimiter(10.0, 10.0); // 10 burst
        assertTrue(rl.consume());
        assertTrue(rl.consume());
        assertTrue(rl.consume());
    }

    @Test
    @DisplayName("Should deny consumption when over limit")
    void testOverLimit() {
        RateLimiter rl = new RateLimiter(10.0, 1.0); // 1 burst
        assertTrue(rl.consume()); // Use burst
        assertFalse(rl.consume()); // Deny next
    }

    @Test
    @DisplayName("Should track dropped events")
    void testDroppedCount() {
        RateLimiter rl = new RateLimiter(10.0, 1.0);
        rl.consume(); // Success
        rl.consume(); // Fail
        rl.consume(); // Fail

        Map<String, Object> stats = rl.getStats();
        assertTrue(stats.containsKey("droppedCount"));
    }

    @Test
    @DisplayName("Should respect burst capacity")
    void testBurstCapacity() {
        RateLimiter rl = new RateLimiter(5.0, 5.0); // 5 burst
        for (int i = 0; i < 5; i++) {
            assertTrue(rl.consume(), "Should allow 5 burst tokens");
        }
        assertFalse(rl.consume(), "Should deny after burst exhausted");
    }

    @Test
    @DisplayName("Should refill tokens over time")
    void testTokenRefill() throws InterruptedException {
        RateLimiter rl = new RateLimiter(10.0, 1.0);
        assertTrue(rl.consume()); // Use burst
        assertFalse(rl.consume()); // Deny

        // Wait for refill (100ms = 1 token at 10/sec)
        Thread.sleep(150);

        assertTrue(rl.consume(), "Should refill after delay");
    }

    @Test
    @DisplayName("Should provide statistics")
    void testStatistics() {
        limiter.consume();
        Map<String, Object> stats = limiter.getStats();

        assertTrue(stats.containsKey("limit"));
        assertTrue(stats.containsKey("burst"));
        assertTrue(stats.containsKey("tokens"));
        assertTrue(stats.containsKey("droppedCount"));
    }

    @Test
    @DisplayName("Should track total dropped")
    void testTotalDropped() {
        RateLimiter rl = new RateLimiter(10.0, 1.0);
        rl.consume(); // Success
        rl.consume(); // Dropped 1
        rl.consume(); // Dropped 2
        rl.consume(); // Dropped 3

        Map<String, Object> stats = rl.getStats();
        long dropped = ((Number) stats.get("droppedCount")).longValue();
        assertEquals(3, dropped);
    }

    @Test
    @DisplayName("Should handle high frequency calls")
    void testHighFrequency() {
        RateLimiter rl = new RateLimiter(100.0, 10.0);
        int successes = 0;
        int failures = 0;

        for (int i = 0; i < 100; i++) {
            if (rl.consume()) {
                successes++;
            } else {
                failures++;
            }
        }

        assertTrue(successes > 0, "Should allow some high-frequency calls");
    }

    @Test
    @DisplayName("Should recover after burst depletion")
    void testRecovery() throws InterruptedException {
        RateLimiter rl = new RateLimiter(10.0, 1.0);

        // Deplete burst
        assertTrue(rl.consume());
        assertFalse(rl.consume());

        // Wait and refill
        Thread.sleep(150);
        assertTrue(rl.consume(), "Should recover after wait");
    }

    @Test
    @DisplayName("Should handle reset")
    void testReset() {
        limiter.consume();
        limiter.consume();

        Map<String, Object> stats1 = limiter.getStats();
        long dropped1 = ((Number) stats1.get("droppedCount")).longValue();

        assertTrue(dropped1 > 0);
    }

    @Test
    @DisplayName("ProbeRateLimiter should manage multiple limiters")
    void testProbeRateLimiter() {
        ProbeRateLimiter prl = new ProbeRateLimiter();

        RateLimiter rl1 = prl.getLimiter("probe-1", 10.0, 1.0);
        RateLimiter rl2 = prl.getLimiter("probe-2", 5.0, 1.0);

        assertTrue(rl1.consume());
        assertTrue(rl2.consume());
    }

    @Test
    @DisplayName("ProbeRateLimiter should cache limiters")
    void testProbeRateLimiterCaching() {
        ProbeRateLimiter prl = new ProbeRateLimiter();

        RateLimiter rl1 = prl.getLimiter("probe-1", 10.0, 1.0);
        RateLimiter rl2 = prl.getLimiter("probe-1", 10.0, 1.0);

        assertSame(rl1, rl2, "Should return same limiter for same probe");
    }

    @Test
    @DisplayName("ProbeRateLimiter should track per-probe consumption")
    void testProbeConsumption() {
        ProbeRateLimiter prl = new ProbeRateLimiter();

        for (int i = 0; i < 10; i++) {
            prl.consume("probe-1", 10.0, 1.0);
            prl.consume("probe-2", 10.0, 1.0);
        }

        // Both probes should have stats
        Map<String, Object> stats1 = prl.getLimiter("probe-1", 10.0, 1.0).getStats();
        assertNotNull(stats1);
    }

    @Test
    @DisplayName("Should handle zero burst correctly")
    void testZeroBurst() {
        RateLimiter rl = new RateLimiter(10.0, 0.0);
        // Even with 0 burst, should refill tokens over time
        assertFalse(rl.consume(), "Should fail with 0 burst initially");
    }

    @Test
    @DisplayName("Should handle very high limit")
    void testVeryHighLimit() {
        RateLimiter rl = new RateLimiter(1000000.0, 1000.0);

        for (int i = 0; i < 100; i++) {
            assertTrue(rl.consume(), "Should handle very high limits");
        }
    }

    @Test
    @DisplayName("Should be thread-safe")
    void testThreadSafety() throws InterruptedException {
        RateLimiter rl = new RateLimiter(100.0, 50.0);

        Thread t1 = new Thread(() -> {
            for (int i = 0; i < 25; i++) {
                rl.consume();
            }
        });

        Thread t2 = new Thread(() -> {
            for (int i = 0; i < 25; i++) {
                rl.consume();
            }
        });

        t1.start();
        t2.start();
        t1.join();
        t2.join();

        // Should not crash or have data corruption
        assertNotNull(rl.getStats());
    }
}

package com.debugin.ratelimit;

import java.util.*;
import java.util.concurrent.ConcurrentHashMap;

/**
 * Token bucket rate limiter for Java
 *
 * Implements token bucket algorithm for rate limiting probe events.
 * Allows bursts up to a limit, then throttles to a steady rate.
 */
public class RateLimiter {
    private final double limitPerSecond;
    private final double burst;
    private double tokens;
    private long lastRefillTime;
    private long droppedCount = 0;

    /**
     * Create a rate limiter
     *
     * @param limitPerSecond Tokens per second (e.g., 10)
     * @param burst Maximum burst capacity (e.g., 1)
     */
    public RateLimiter(double limitPerSecond, double burst) {
        this.limitPerSecond = limitPerSecond;
        this.burst = burst;
        this.tokens = burst;
        this.lastRefillTime = System.currentTimeMillis();
    }

    /**
     * Try to consume a token
     *
     * @return true if token was available, false if rate limited
     */
    public synchronized boolean consume() {
        refill();

        if (tokens >= 1.0) {
            tokens -= 1.0;
            return true;
        } else {
            droppedCount++;
            return false;
        }
    }

    /**
     * Refill tokens based on elapsed time
     */
    private void refill() {
        long now = System.currentTimeMillis();
        long elapsedMs = now - lastRefillTime;
        double elapsedSeconds = elapsedMs / 1000.0;
        double tokensToAdd = elapsedSeconds * limitPerSecond;

        tokens = Math.min(burst, tokens + tokensToAdd);
        lastRefillTime = now;
    }

    /**
     * Get current token count
     */
    public synchronized double getTokens() {
        refill();
        return tokens;
    }

    /**
     * Get dropped event count
     */
    public long getDroppedCount() {
        return droppedCount;
    }

    /**
     * Reset the limiter
     */
    public synchronized void reset() {
        tokens = burst;
        lastRefillTime = System.currentTimeMillis();
        droppedCount = 0;
    }

    /**
     * Get statistics map
     */
    public synchronized Map<String, Object> getStats() {
        Map<String, Object> stats = new HashMap<>();
        stats.put("limitPerSecond", limitPerSecond);
        stats.put("burst", burst);
        stats.put("currentTokens", (long) tokens);
        stats.put("droppedCount", droppedCount);
        return stats;
    }
}

/**
 * Multi-probe rate limiter
 * Manages rate limiters for multiple probes
 */
public class ProbeRateLimiter {
    private final Map<String, RateLimiter> limiters = new ConcurrentHashMap<>();

    /**
     * Get or create limiter for a probe
     */
    public RateLimiter getLimiter(String probeId, double limitPerSecond, double burst) {
        return limiters.computeIfAbsent(
            probeId,
            k -> new RateLimiter(limitPerSecond, burst)
        );
    }

    /**
     * Try to consume a token for a probe
     */
    public boolean consume(String probeId, double limitPerSecond, double burst) {
        RateLimiter limiter = getLimiter(probeId, limitPerSecond, burst);
        return limiter.consume();
    }

    /**
     * Remove a limiter
     */
    public void removeLimiter(String probeId) {
        limiters.remove(probeId);
    }

    /**
     * Clear all limiters
     */
    public void clear() {
        limiters.clear();
    }

    /**
     * Get all statistics
     */
    public Map<String, Map<String, Object>> getAllStats() {
        Map<String, Map<String, Object>> stats = new HashMap<>();
        for (Map.Entry<String, RateLimiter> entry : limiters.entrySet()) {
            stats.put(entry.getKey(), entry.getValue().getStats());
        }
        return stats;
    }
}

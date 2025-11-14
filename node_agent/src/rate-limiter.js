/**
 * Token bucket rate limiter for Node.js
 */
class RateLimiter {
    constructor(limitPerSecond = 10, burst = 1) {
        this.limitPerSecond = limitPerSecond;
        this.burst = burst;
        this.tokens = burst;
        this.lastRefill = Date.now();
        this.droppedCount = 0;
    }

    /**
     * Try to consume a token
     */
    consume() {
        this._refill();
        if (this.tokens >= 1) {
            this.tokens -= 1;
            return true;
        }
        this.droppedCount++;
        return false;
    }

    /**
     * Refill tokens based on elapsed time
     */
    _refill() {
        const now = Date.now();
        const elapsed = (now - this.lastRefill) / 1000;
        const tokensToAdd = elapsed * this.limitPerSecond;
        this.tokens = Math.min(this.tokens + tokensToAdd, this.burst);
        this.lastRefill = now;
    }

    /**
     * Get statistics
     */
    getStats() {
        return {
            limitPerSecond: this.limitPerSecond,
            burst: this.burst,
            currentTokens: this.tokens,
            droppedCount: this.droppedCount,
        };
    }

    /**
     * Reset the limiter
     */
    reset() {
        this.tokens = this.burst;
        this.lastRefill = Date.now();
        this.droppedCount = 0;
    }
}

module.exports = RateLimiter;

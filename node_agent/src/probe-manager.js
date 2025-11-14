/**
 * ProbeManager for Node.js - manages probe lifecycle and breakpoint handling
 */
const RateLimiter = require('./rate-limiter');
const ConditionEvaluator = require('./condition-evaluator');
const Snapshotter = require('./snapshotter');

class ProbeManager {
    constructor(options = {}) {
        this.inspector = options.inspector;
        this.eventClient = options.eventClient;
        this.tags = options.tags || [];
        this.probes = new Map();
        this.rateLimiters = new Map();
        this.breakpointMapping = new Map();  // breakpoint ID -> probe ID
        this.enabled = true;
    }

    /**
     * Add a probe
     */
    async addProbe(probeConfig) {
        if (!probeConfig.id) {
            throw new Error('Probe must have an id');
        }

        // Validate probe config
        if (!probeConfig.file || probeConfig.line === undefined) {
            throw new Error('Probe must have file and line');
        }

        // Store probe
        this.probes.set(probeConfig.id, probeConfig);

        // Create rate limiter
        const sample = probeConfig.sample || { limitPerSecond: 10, burst: 1 };
        this.rateLimiters.set(probeConfig.id, new RateLimiter(sample.limitPerSecond, sample.burst));

        // Set breakpoint via inspector if available
        if (this.inspector) {
            try {
                const breakpointId = await this.inspector.setBreakpoint(
                    probeConfig.file,
                    probeConfig.line,
                    probeConfig.id
                );
                this.breakpointMapping.set(breakpointId, probeConfig.id);
            } catch (e) {
                console.warn('[DebugIn] Failed to set breakpoint:', e.message);
            }
        }

        return { ok: true, probeId: probeConfig.id };
    }

    /**
     * Remove a probe
     */
    async removeProbe(probeId) {
        const probe = this.probes.get(probeId);
        if (!probe) {
            return { ok: false, error: 'Probe not found' };
        }

        this.probes.delete(probeId);
        this.rateLimiters.delete(probeId);

        // Remove breakpoint via inspector
        if (this.inspector) {
            try {
                await this.inspector.removeBreakpoint(probeId);
            } catch (e) {
                console.warn('[DebugIn] Failed to remove breakpoint:', e.message);
            }
        }

        return { ok: true };
    }

    /**
     * Get all probes
     */
    getProbes() {
        return Array.from(this.probes.values());
    }

    /**
     * Get probes by tag
     */
    getProbesByTag(tag) {
        return Array.from(this.probes.values()).filter(p =>
            p.tags && p.tags.includes(tag)
        );
    }

    /**
     * Handle a breakpoint pause
     */
    async handlePause(event) {
        if (!this.enabled) {
            return;
        }

        try {
            const breakpointId = event.breakpointId;
            const probeId = this.breakpointMapping.get(breakpointId);
            if (!probeId) {
                return;
            }

            const probe = this.probes.get(probeId);
            if (!probe) {
                return;
            }

            // Check tags
            if (probe.tags && probe.tags.length > 0) {
                if (!probe.tags.every(tag => this.tags.includes(tag))) {
                    return;
                }
            }

            // Rate limiting
            const limiter = this.rateLimiters.get(probeId);
            if (!limiter.consume()) {
                return;
            }

            // Condition evaluation
            if (probe.condition) {
                const context = event.context || {};
                if (!ConditionEvaluator.evaluate(probe.condition, context)) {
                    return;
                }
            }

            // Capture snapshot
            const snapshotter = new Snapshotter(probe.snapshot || {});
            const snapshot = snapshotter.captureSnapshot(event.this, event.args, event.locals);

            // Build and send event
            const probeEvent = this._buildEvent(probe, snapshot);
            if (this.eventClient) {
                await this.eventClient.send(probeEvent);
            }
        } catch (e) {
            console.error('[DebugIn] Error handling pause:', e);
        }
    }

    /**
     * Build canonical event
     */
    _buildEvent(probe, snapshot) {
        return {
            type: probe.message ? 'logpoint.hit' : 'tracepoint.hit',
            id: this._generateId(),
            timestamp: new Date().toISOString(),
            lang: 'node',
            runtime: 'nodejs',
            client: {
                hostname: require('os').hostname(),
                applicationName: process.env.APP_NAME || 'unknown',
                agentVersion: '0.3.0',
                runtime: 'nodejs',
                runtimeVersion: process.version,
            },
            location: {
                file: probe.file,
                line: probe.line,
                method: probe.method || 'unknown',
            },
            probeId: probe.id,
            tags: probe.tags || [],
            payload: {
                message: probe.message,
                snapshot: snapshot,
            },
        };
    }

    /**
     * Generate UUID
     */
    _generateId() {
        return `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    }

    /**
     * Set enabled state
     */
    setEnabled(enabled) {
        this.enabled = enabled;
    }

    /**
     * Stop the probe manager
     */
    async stop() {
        if (this.inspector) {
            for (const probeId of this.probes.keys()) {
                try {
                    await this.inspector.removeBreakpoint(probeId);
                } catch (e) {
                    // ignore
                }
            }
        }
        this.probes.clear();
        this.rateLimiters.clear();
        this.breakpointMapping.clear();
    }
}

module.exports = ProbeManager;

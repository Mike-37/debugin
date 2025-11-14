#!/usr/bin/env node
/**
 * DebugIn Node.js Agent
 *
 * Main entry point for the Node.js runtime agent.
 * Provides probe management, condition evaluation, rate limiting, and event posting.
 *
 * Usage:
 *   const agent = require('./index.js');
 *   await agent.start({ sinkUrl: 'http://localhost:4317' });
 */

const Inspector = require('./lib/inspector');
const ProbeManager = require('./lib/probe-manager');
const ConditionEvaluator = require('./lib/condition-evaluator');
const RateLimiter = require('./lib/rate-limiter');
const Snapshotter = require('./lib/snapshotter');
const EventClient = require('./lib/event-client');
const ControlAPI = require('./lib/control-api');

class DebugInAgent {
    constructor(options = {}) {
        this.options = {
            sinkUrl: options.sinkUrl || process.env.DEBUGIN_SINK_URL || 'http://localhost:4317',
            controlApiPort: options.controlApiPort || parseInt(process.env.DEBUGIN_CONTROL_API_PORT || '5001'),
            controlApiHost: options.controlApiHost || process.env.DEBUGIN_CONTROL_API_HOST || '127.0.0.1',
            enabled: options.enabled !== false,
            tags: options.tags || [],
        };

        this.inspector = null;
        this.probeManager = null;
        this.eventClient = null;
        this.controlAPI = null;
    }

    /**
     * Start the agent
     */
    async start() {
        if (!this.options.enabled) {
            console.log('[DebugIn] Agent disabled');
            return;
        }

        try {
            console.log('[DebugIn] Agent starting...');
            console.log('  - Version: 0.3.0');
            console.log('  - Node: ' + process.version);
            console.log('  - Sink URL: ' + this.options.sinkUrl);

            // Initialize components
            this.eventClient = new EventClient(this.options.sinkUrl);
            this.probeManager = new ProbeManager({
                inspector: null,  // Will be set up on demand
                eventClient: this.eventClient,
                tags: this.options.tags,
            });

            // Start control API if enabled
            if (this.options.controlApiPort) {
                this.controlAPI = new ControlAPI(this, {
                    host: this.options.controlApiHost,
                    port: this.options.controlApiPort,
                });
                await this.controlAPI.start();
                console.log('[DebugIn] Control API listening on ' +
                    this.options.controlApiHost + ':' + this.options.controlApiPort);
            }

            console.log('[DebugIn] Agent started successfully');
        } catch (e) {
            console.error('[DebugIn] Failed to start agent:', e);
            throw e;
        }
    }

    /**
     * Stop the agent
     */
    async stop() {
        try {
            if (this.probeManager) {
                await this.probeManager.stop();
            }
            if (this.inspector) {
                await this.inspector.close();
            }
            if (this.controlAPI) {
                await this.controlAPI.stop();
            }
            console.log('[DebugIn] Agent stopped');
        } catch (e) {
            console.error('[DebugIn] Error stopping agent:', e);
        }
    }

    /**
     * Add a probe
     */
    async addProbe(probeConfig) {
        if (!this.probeManager) {
            throw new Error('Agent not started');
        }
        return this.probeManager.addProbe(probeConfig);
    }

    /**
     * Remove a probe
     */
    async removeProbe(probeId) {
        if (!this.probeManager) {
            throw new Error('Agent not started');
        }
        return this.probeManager.removeProbe(probeId);
    }

    /**
     * Get all probes
     */
    getProbes() {
        if (!this.probeManager) {
            return [];
        }
        return this.probeManager.getProbes();
    }

    /**
     * Enable/disable agent
     */
    setEnabled(enabled) {
        this.options.enabled = enabled;
        if (this.probeManager) {
            this.probeManager.setEnabled(enabled);
        }
    }

    /**
     * Add/remove tags
     */
    addTag(tag) {
        this.options.tags.push(tag);
    }

    removeTag(tag) {
        this.options.tags = this.options.tags.filter(t => t !== tag);
    }
}

// Singleton instance
let agentInstance = null;

/**
 * Start the agent (exported function)
 */
async function start(options) {
    if (agentInstance) {
        return agentInstance;
    }
    agentInstance = new DebugInAgent(options);
    await agentInstance.start();
    return agentInstance;
}

/**
 * Stop the agent (exported function)
 */
async function stop() {
    if (agentInstance) {
        await agentInstance.stop();
        agentInstance = null;
    }
}

module.exports = {
    start,
    stop,
    getInstance: () => agentInstance,
    DebugInAgent,
    // Export components for testing
    Inspector,
    ProbeManager,
    ConditionEvaluator,
    RateLimiter,
    Snapshotter,
    EventClient,
    ControlAPI,
};

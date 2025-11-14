/**
 * Control API HTTP server for probe management
 */
const http = require('http');

class ControlAPI {
    constructor(agent, options = {}) {
        this.agent = agent;
        this.host = options.host || '127.0.0.1';
        this.port = options.port || 5001;
        this.server = null;
    }

    /**
     * Start the control API server
     */
    async start() {
        return new Promise((resolve, reject) => {
            this.server = http.createServer((req, res) => {
                this._handleRequest(req, res).catch(e => {
                    console.error('[DebugIn] Control API error:', e);
                    res.writeHead(500, { 'Content-Type': 'application/json' });
                    res.end(JSON.stringify({ ok: false, error: e.message }));
                });
            });

            this.server.listen(this.port, this.host, resolve);
            this.server.on('error', reject);
        });
    }

    /**
     * Stop the control API server
     */
    async stop() {
        return new Promise((resolve) => {
            if (this.server) {
                this.server.close(resolve);
            } else {
                resolve();
            }
        });
    }

    /**
     * Handle HTTP requests
     */
    async _handleRequest(req, res) {
        const { method, url: path } = req;

        // CORS
        res.setHeader('Access-Control-Allow-Origin', '*');
        res.setHeader('Access-Control-Allow-Methods', 'GET, POST, DELETE, OPTIONS');
        res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

        if (method === 'OPTIONS') {
            res.writeHead(200);
            res.end();
            return;
        }

        // POST /probes - create/upsert probe
        if (method === 'POST' && path === '/probes') {
            let body = '';
            req.on('data', chunk => { body += chunk; });
            req.on('end', async () => {
                try {
                    const probeConfig = JSON.parse(body);
                    const result = await this.agent.addProbe(probeConfig);
                    res.writeHead(200, { 'Content-Type': 'application/json' });
                    res.end(JSON.stringify(result));
                } catch (e) {
                    res.writeHead(400, { 'Content-Type': 'application/json' });
                    res.end(JSON.stringify({ ok: false, error: e.message }));
                }
            });
            return;
        }

        // DELETE /probes/:id - remove probe
        if (method === 'DELETE' && path.startsWith('/probes/')) {
            const probeId = path.substring('/probes/'.length);
            try {
                const result = await this.agent.removeProbe(probeId);
                res.writeHead(result.ok ? 200 : 404, { 'Content-Type': 'application/json' });
                res.end(JSON.stringify(result));
            } catch (e) {
                res.writeHead(500, { 'Content-Type': 'application/json' });
                res.end(JSON.stringify({ ok: false, error: e.message }));
            }
            return;
        }

        // GET /probes - list probes
        if (method === 'GET' && path === '/probes') {
            const probes = this.agent.getProbes();
            res.writeHead(200, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify({ ok: true, probes }));
            return;
        }

        // 404
        res.writeHead(404, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ ok: false, error: 'Not found' }));
    }
}

module.exports = ControlAPI;

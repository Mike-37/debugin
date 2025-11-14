/**
 * HTTP client for sending events to the event sink
 */
const http = require('http');
const https = require('https');
const url = require('url');

class EventClient {
    constructor(sinkUrl) {
        this.sinkUrl = sinkUrl;
        this.maxRetries = 3;
    }

    /**
     * Send an event to the sink
     */
    async send(event) {
        if (!this.sinkUrl) {
            console.warn('[DebugIn] Event sink URL not configured');
            return false;
        }

        for (let attempt = 0; attempt < this.maxRetries; attempt++) {
            try {
                const result = await this._sendRequest(event);
                if (result) {
                    return true;
                }
            } catch (e) {
                if (attempt < this.maxRetries - 1) {
                    // Exponential backoff
                    await new Promise(resolve => setTimeout(resolve, Math.pow(2, attempt) * 100));
                } else {
                    console.error('[DebugIn] Failed to send event after retries:', e.message);
                }
            }
        }
        return false;
    }

    /**
     * Send HTTP POST request
     */
    _sendRequest(event) {
        return new Promise((resolve, reject) => {
            try {
                const targetUrl = this.sinkUrl.endsWith('/') ?
                    this.sinkUrl + 'api/events' :
                    this.sinkUrl + '/api/events';

                const parsed = url.parse(targetUrl);
                const client = parsed.protocol === 'https:' ? https : http;
                const body = JSON.stringify(event);

                const options = {
                    hostname: parsed.hostname,
                    port: parsed.port,
                    path: parsed.path,
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Content-Length': Buffer.byteLength(body),
                    },
                    timeout: 5000,
                };

                const req = client.request(options, (res) => {
                    const statusCode = res.statusCode;
                    if (statusCode >= 200 && statusCode < 300) {
                        resolve(true);
                    } else if (statusCode >= 400 && statusCode < 500) {
                        console.warn('[DebugIn] Client error sending event:', statusCode);
                        resolve(false);
                    } else {
                        reject(new Error(`Server error: ${statusCode}`));
                    }
                });

                req.on('error', reject);
                req.on('timeout', () => {
                    req.destroy();
                    reject(new Error('Request timeout'));
                });

                req.write(body);
                req.end();
            } catch (e) {
                reject(e);
            }
        });
    }
}

module.exports = EventClient;

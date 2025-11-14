/**
 * Node.js Integration Tests for DebugIn Agent
 *
 * Tests:
 * - Control API endpoint responses
 * - Tracepoint and logpoint creation
 * - Condition evaluation
 * - Rate limiting
 * - Tag management
 */

const http = require('http');
const assert = require('assert');

const CONTROL_API_URL = 'http://127.0.0.1:5001';

/**
 * Helper to make HTTP requests
 */
function makeRequest(method, path, body = null) {
    return new Promise((resolve, reject) => {
        const url = new URL(path, CONTROL_API_URL);
        const options = {
            hostname: url.hostname,
            port: url.port,
            path: url.pathname,
            method: method,
            headers: {
                'Content-Type': 'application/json'
            }
        };

        const req = http.request(options, (res) => {
            let data = '';
            res.on('data', chunk => data += chunk);
            res.on('end', () => {
                try {
                    const json = data ? JSON.parse(data) : {};
                    resolve({ status: res.statusCode, body: json });
                } catch (e) {
                    resolve({ status: res.statusCode, body: data });
                }
            });
        });

        req.on('error', reject);

        if (body) {
            req.write(JSON.stringify(body));
        }
        req.end();
    });
}

/**
 * Test health endpoint
 */
async function testHealthCheckReturns200() {
    const response = await makeRequest('GET', '/health');
    assert.strictEqual(response.status, 200, 'Health endpoint should return 200');
    console.log('✓ Health check returns 200');
}

async function testHealthIncludesRequiredFields() {
    const response = await makeRequest('GET', '/health');
    const data = response.body;

    assert.strictEqual(data.status, 'healthy');
    assert(data.agent, 'Should include agent info');
    assert.strictEqual(data.agent.name, 'tracepointdebug');
    assert.strictEqual(data.agent.runtime, 'node');
    assert(data.features, 'Should include features');
    assert.strictEqual(data.features.tracepoints, true);
    console.log('✓ Health includes required fields');
}

/**
 * Test tracepoint creation
 */
async function testCreateTracepointReturns201() {
    const response = await makeRequest('POST', '/tracepoints', {
        file: 'test.js',
        line: 10
    });

    assert.strictEqual(response.status, 201, 'Creating tracepoint should return 201');
    assert(response.body.id, 'Response should include ID');
    assert.strictEqual(response.body.type, 'tracepoint');
    console.log('✓ Create tracepoint returns 201');
}

async function testCreateTracepointWithCondition() {
    const response = await makeRequest('POST', '/tracepoints', {
        file: 'test.js',
        line: 15,
        condition: 'args[0] > 5'
    });

    assert.strictEqual(response.status, 201);
    assert.strictEqual(response.body.condition, 'args[0] > 5');
    console.log('✓ Create tracepoint with condition');
}

async function testCreateTracepointWithTags() {
    const response = await makeRequest('POST', '/tracepoints', {
        file: 'test.js',
        line: 20,
        tags: ['debug', 'test']
    });

    assert.strictEqual(response.status, 201);
    console.log('✓ Create tracepoint with tags');
}

async function testCreateTracepointMissingFileReturns400() {
    const response = await makeRequest('POST', '/tracepoints', {
        line: 10
    });

    assert.strictEqual(response.status, 400, 'Missing file should return 400');
    console.log('✓ Missing file returns 400');
}

async function testCreateTracepointInvalidLineReturns400() {
    const response = await makeRequest('POST', '/tracepoints', {
        file: 'test.js',
        line: -1
    });

    assert.strictEqual(response.status, 400, 'Invalid line should return 400');
    console.log('✓ Invalid line returns 400');
}

/**
 * Test logpoint creation
 */
async function testCreateLogpointReturns201() {
    const response = await makeRequest('POST', '/logpoints', {
        file: 'test.js',
        line: 25,
        message: 'User {user.id} called function'
    });

    assert.strictEqual(response.status, 201);
    assert.strictEqual(response.body.type, 'logpoint');
    console.log('✓ Create logpoint returns 201');
}

async function testCreateLogpointWithCondition() {
    const response = await makeRequest('POST', '/logpoints', {
        file: 'test.js',
        line: 30,
        message: 'Value: {value}',
        condition: 'value > 100'
    });

    assert.strictEqual(response.status, 201);
    console.log('✓ Create logpoint with condition');
}

/**
 * Test listing points
 */
async function testListPointsReturns200() {
    const response = await makeRequest('GET', '/points');
    assert.strictEqual(response.status, 200);
    assert(Array.isArray(response.body.points), 'Should return array of points');
    console.log('✓ List points returns 200');
}

/**
 * Test point enable/disable
 */
async function testEnablePointReturns200() {
    // Create a point first
    const createResp = await makeRequest('POST', '/tracepoints', {
        file: 'test.js',
        line: 35
    });
    const pointId = createResp.body.id;

    // Enable it
    const response = await makeRequest('POST', `/points/${pointId}/enable`);
    assert.strictEqual(response.status, 200);
    console.log('✓ Enable point returns 200');
}

async function testDisablePointReturns200() {
    // Create a point first
    const createResp = await makeRequest('POST', '/tracepoints', {
        file: 'test.js',
        line: 40
    });
    const pointId = createResp.body.id;

    // Disable it
    const response = await makeRequest('POST', `/points/${pointId}/disable`);
    assert.strictEqual(response.status, 200);
    console.log('✓ Disable point returns 200');
}

async function testDeletePointReturns204() {
    // Create a point first
    const createResp = await makeRequest('POST', '/tracepoints', {
        file: 'test.js',
        line: 45
    });
    const pointId = createResp.body.id;

    // Delete it
    const response = await makeRequest('DELETE', `/points/${pointId}`);
    assert.strictEqual(response.status, 204);
    console.log('✓ Delete point returns 204');
}

/**
 * Test tag management
 */
async function testEnableTagReturns200() {
    const response = await makeRequest('POST', '/tags/enable', {
        tags: ['debug']
    });

    assert.strictEqual(response.status, 200);
    console.log('✓ Enable tag returns 200');
}

async function testDisableTagReturns200() {
    const response = await makeRequest('POST', '/tags/disable', {
        tags: ['debug']
    });

    assert.strictEqual(response.status, 200);
    console.log('✓ Disable tag returns 200');
}

/**
 * Test condition evaluator
 */
async function testConditionEvaluator() {
    const ConditionEvaluator = require('../lib/condition_evaluator');
    const evaluator = new ConditionEvaluator();

    // Comparison
    assert(evaluator.evaluate('10 > 5', {}));
    assert(!evaluator.evaluate('10 < 5', {}));
    console.log('✓ Condition evaluator - comparison');

    // Variable access
    const scope = { args: [15, 20], this: { enabled: true } };
    assert(evaluator.evaluate('args[0] > 10', scope));
    assert(evaluator.evaluate('this.enabled', scope));
    console.log('✓ Condition evaluator - variable access');

    // Logical operators
    assert(evaluator.evaluate('true && true', {}));
    assert(!evaluator.evaluate('true && false', {}));
    assert(evaluator.evaluate('true || false', {}));
    console.log('✓ Condition evaluator - logical operators');
}

/**
 * Test rate limiter
 */
async function testRateLimiter() {
    const { RateLimiter, ProbeRateLimiter } = require('../lib/rate_limiter');

    // Single limiter
    const limiter = new RateLimiter(10, 1);
    const first = limiter.consume();
    assert.strictEqual(first.allowed, true);
    const second = limiter.consume();
    assert.strictEqual(second.allowed, false);
    console.log('✓ Rate limiter - token bucket');

    // Multi-probe limiter
    const multiLimiter = new ProbeRateLimiter();
    const result1 = multiLimiter.consume('probe1', 10, 1);
    const result2 = multiLimiter.consume('probe2', 10, 1);
    assert.strictEqual(result1.allowed, true);
    assert.strictEqual(result2.allowed, true);
    console.log('✓ Rate limiter - multi-probe');
}

/**
 * Test agent start/stop
 */
async function testAgentStartStop() {
    const debugin = require('../lib/index.js');

    // Agent should already be started from beforeEach
    const instance = debugin.getInstance();
    assert(instance, 'Agent instance should exist');
    assert(instance.isRunning(), 'Agent should be running');
    console.log('✓ Agent is running');

    // Can create points
    const agent = instance;
    const result = await makeRequest('GET', '/health');
    assert.strictEqual(result.status, 200);
    console.log('✓ Agent methods work');
}

/**
 * Run all tests
 */
async function runAllTests() {
    const tests = [
        testHealthCheckReturns200,
        testHealthIncludesRequiredFields,
        testCreateTracepointReturns201,
        testCreateTracepointWithCondition,
        testCreateTracepointWithTags,
        testCreateTracepointMissingFileReturns400,
        testCreateTracepointInvalidLineReturns400,
        testCreateLogpointReturns201,
        testCreateLogpointWithCondition,
        testListPointsReturns200,
        testEnablePointReturns200,
        testDisablePointReturns200,
        testDeletePointReturns204,
        testEnableTagReturns200,
        testDisableTagReturns200,
        testConditionEvaluator,
        testRateLimiter,
        testAgentStartStop
    ];

    console.log('\n=== Node.js Integration Tests ===\n');

    let passed = 0;
    let failed = 0;

    for (const test of tests) {
        try {
            await test();
            passed++;
        } catch (err) {
            console.error(`✗ ${test.name}: ${err.message}`);
            failed++;
        }
    }

    console.log(`\n=== Results ===`);
    console.log(`Passed: ${passed}`);
    console.log(`Failed: ${failed}`);
    console.log(`Total: ${tests.length}`);

    process.exit(failed > 0 ? 1 : 0);
}

// Start agent before tests
const debugin = require('../lib/index.js');
debugin.start({
    controlApiPort: 5001,
    controlApiHost: '127.0.0.1'
});

// Give server time to start
setTimeout(runAllTests, 500);

module.exports = {
    testHealthCheckReturns200,
    testCreateTracepointReturns201,
    testConditionEvaluator,
    testRateLimiter
};

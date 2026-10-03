// ================================================================
// OPC Monitor — Load Test
// ================================================================
// Load profile: ramp-up 30s → 100 RPS for 2m → ramp-down 30s
//
// Usage:
//   k6 run tests/load/k6-test.js
//   k6 run --out experimental-prometheus-rw tests/load/k6-test.js
//
// Environment overrides:
//   BASE_URL       (default: http://localhost:5000)
//   ADMIN_USER     (default: admin)
//   ADMIN_PASSWORD (default: change_me_secure_admin_password)
// ================================================================

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';

// ----------------------------------------------------------------
// Configuration
// ----------------------------------------------------------------
const BASE_URL       = __ENV.BASE_URL       || 'http://localhost:5000';
const ADMIN_USER     = __ENV.ADMIN_USER     || 'admin';
const ADMIN_PASSWORD = __ENV.ADMIN_PASSWORD || 'change_me_secure_admin_password';

// Custom metrics — visible in k6 output and in Prometheus remote-write
const errorRate = new Rate('custom_errors');
const healthLatency = new Trend('custom_health_latency', true);
const latestLatency = new Trend('custom_latest_latency', true);
const historyLatency = new Trend('custom_history_latency', true);

// ----------------------------------------------------------------
// Load profile
// ----------------------------------------------------------------
export const options = {
    scenarios: {
        smoke: {
            executor: 'constant-vus',
            vus: 1,
            duration: '10s',
            startTime: '0s',
            tags: { scenario: 'smoke' },
        },
        load: {
            executor: 'ramping-arrival-rate',
            startRate: 10,
            timeUnit: '1s',
            preAllocatedVUs: 50,
            maxVUs: 200,
            stages: [
                { target: 100, duration: '30s' },   // ramp up to 100 RPS
                { target: 100, duration: '2m' },    // steady state
                { target: 10,  duration: '30s' },   // ramp down
            ],
            startTime: '15s',
            tags: { scenario: 'load' },
        },
    },
    thresholds: {
        // HTTP-level: p95 < 500 ms, p99 < 1 s, error rate < 1%
        'http_req_duration{scenario:load}': ['p(95)<500', 'p(99)<1000'],
        'http_req_failed{scenario:load}': ['rate<0.01'],

        // Custom per-endpoint thresholds
        'custom_health_latency':  ['p(95)<100'],
        'custom_latest_latency':  ['p(95)<500'],
        'custom_history_latency': ['p(95)<800'],

        // General
        'checks': ['rate>0.99'],
    },
    summaryTrendStats: ['avg', 'min', 'med', 'p(90)', 'p(95)', 'p(99)', 'max'],
};

// ----------------------------------------------------------------
// Setup — runs ONCE before VUs start
// ----------------------------------------------------------------
export function setup() {
    const res = http.post(
        `${BASE_URL}/api/auth/login`,
        JSON.stringify({ username: ADMIN_USER, password: ADMIN_PASSWORD }),
        { headers: { 'Content-Type': 'application/json' } }
    );

    if (res.status !== 200) {
        throw new Error(`Login failed: ${res.status} ${res.body}`);
    }

    const token = res.json('access_token');
    if (!token) {
        throw new Error('Login response did not contain access_token');
    }

    console.log(`✅ Login OK — token length: ${token.length}`);
    return { token };
}

// ----------------------------------------------------------------
// Default function — runs for every VU iteration
// ----------------------------------------------------------------
export default function (data) {
    const authHeaders = {
        headers: {
            'Authorization': `Bearer ${data.token}`,
            'Content-Type': 'application/json',
        },
    };

    // 1. Health check (public, no auth)
    const healthRes = http.get(`${BASE_URL}/health`, { tags: { endpoint: 'health' } });
    healthLatency.add(healthRes.timings.duration);
    check(healthRes, {
        'health: status 200 or 503': (r) => r.status === 200 || r.status === 503,
        'health: has JSON body':     (r) => r.body && r.body.includes('"status"'),
    }) || errorRate.add(1);

    // 2. Latest measurement (auth, hits DB + Redis)
    const latestRes = http.get(`${BASE_URL}/api/latest`, {
        ...authHeaders,
        tags: { endpoint: 'latest' },
    });
    latestLatency.add(latestRes.timings.duration);
    check(latestRes, {
        'latest: status 200': (r) => r.status === 200,
    }) || errorRate.add(1);

    // 3. History (auth, heavier DB query)
    const historyRes = http.get(`${BASE_URL}/api/history?limit=50`, {
        ...authHeaders,
        tags: { endpoint: 'history' },
    });
    historyLatency.add(historyRes.timings.duration);
    check(historyRes, {
        'history: status 200': (r) => r.status === 200,
        'history: is array':   (r) => Array.isArray(r.json()),
    }) || errorRate.add(1);

    // No sleep — arrival-rate executor controls the pace
}

// ----------------------------------------------------------------
// Teardown — runs ONCE after all VUs stop
// ----------------------------------------------------------------
export function teardown(data) {
    console.log('✅ Load test complete');
}
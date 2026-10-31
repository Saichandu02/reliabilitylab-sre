// Bounded k6 load for ReliabilityLab. Run where k6 is available:
//   k6 run -e BASE_URL=http://127.0.0.1:8000 load/k6.js
// It is intentionally small: a local sanity load, not a capacity test.
import http from 'k6/http';
import { check } from 'k6';

const BASE = __ENV.BASE_URL || 'http://127.0.0.1:8000';

export const options = {
  scenarios: {
    orders: {
      executor: 'constant-arrival-rate',
      rate: 20, timeUnit: '1s', duration: '30s',
      preAllocatedVUs: 5, maxVUs: 20,
    },
  },
  thresholds: {
    http_req_failed: ['rate<0.01'],
    http_req_duration: ['p(95)<500'],
  },
};

export default function () {
  const payload = JSON.stringify({
    item: 'k6-widget', quantity: 1,
    unit_price_minor: 100, customer_ref: 'k6',
  });
  const res = http.post(`${BASE}/api/orders`, payload, {
    headers: { 'Content-Type': 'application/json' },
  });
  check(res, { 'created': (r) => r.status === 201 });
  const status = http.get(`${BASE}/api/status`);
  check(status, { 'status ok': (r) => r.status === 200 });
}

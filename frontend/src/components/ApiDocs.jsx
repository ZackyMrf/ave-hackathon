const API_BASE = import.meta.env.VITE_API_BASE || 'https://api.avetrace.xyz';
const WS_BASE = import.meta.env.VITE_WS_BASE || 'wss://api.avetrace.xyz';

/* ── Endpoint data ─────────────────────────────────────── */
const ENDPOINTS = [
  // 1. Core Engine
  {
    id: 'analyze-token',
    method: 'GET',
    path: '/api/analyze',
    title: 'Analyze Single Token',
    desc: 'Performs deep analysis (risk & accumulation) on a specific token.',
    params: [
      { name: 'token', required: true, desc: 'Token symbol or contract address (e.g. jup).' },
      { name: 'chain', required: true, desc: 'Blockchain network name (e.g. solana).' },
    ],
    curlExample: `curl "${API_BASE}/api/analyze?token=jup&chain=solana"`,
    jsExample: `const res = await fetch("${API_BASE}/api/analyze?token=jup&chain=solana");\nconst data = await res.json();\nconsole.log(data);`,
    responseExample: `{ "score": { "risk_adjusted": 85 }, "signals": { "whale_score": "High" } }`
  },
  {
    id: 'market-sweep',
    method: 'GET',
    path: '/api/sweep',
    title: 'Market Sweep',
    desc: 'Runs batch analysis based on category to find potential tokens.',
    params: [
      { name: 'category', required: true, desc: 'Filter category (e.g. trending, new_pairs).' },
      { name: 'chain', required: true, desc: 'Blockchain network name.' },
      { name: 'top', required: false, desc: 'Maximum number of potential tokens (default fallback applies).' },
    ],
    curlExample: `curl "${API_BASE}/api/sweep?category=trending&chain=solana&top=5"`,
    jsExample: `const res = await fetch("${API_BASE}/api/sweep?category=trending&chain=solana&top=5");\nconst data = await res.json();\nconsole.log(data);`,
    responseExample: `[ { "token": "jup", "score": 85 }, { "token": "bonk", "score": 72 } ]`
  },

  // 2. Telegram Integration
  {
    id: 'telegram-status',
    method: 'GET',
    path: '/api/telegram/status',
    title: 'Check Telegram Bot Status',
    desc: 'Checks if the Telegram bot is active and connected properly.',
    params: [],
    curlExample: `curl ${API_BASE}/api/telegram/status`,
    jsExample: `const res = await fetch("${API_BASE}/api/telegram/status");\nconst data = await res.json();\nconsole.log(data);`,
    responseExample: `{ "connected": true, "bot_username": "your_bot_name", "status": "ok" }`,
  },
  {
    id: 'telegram-connection',
    method: 'GET',
    path: '/api/telegram/connection',
    title: 'Check User Telegram Connection',
    desc: 'Checks if a specific Telegram user is connected to the system.',
    params: [
      { name: 'chat_id', required: true, desc: 'Numeric ID of the Telegram user' },
    ],
    curlExample: `curl "${API_BASE}/api/telegram/connection?chat_id=123456789"`,
    jsExample: `const res = await fetch("${API_BASE}/api/telegram/connection?chat_id=123456789");\nconst data = await res.json();\nconsole.log(data);`,
    responseExample: `{ "connected": true, "chat_id": "123456789" }`,
  },
  {
    id: 'telegram-test',
    method: 'POST',
    path: '/api/telegram/test',
    title: 'Send Test Message',
    desc: 'Sends a test notification message to the Telegram user to validate the hook.',
    params: [],
    curlExample: `curl -X POST "${API_BASE}/api/telegram/test" -H "Content-Type: application/json" -d '{"chat_id": 123456789}'`,
    jsExample: `const res = await fetch("${API_BASE}/api/telegram/test", {\n  method: "POST",\n  headers: { "Content-Type": "application/json" },\n  body: JSON.stringify({ chat_id: 123456789 })\n});`,
    responseExample: `{ "status": "sent" }`
  },

  // 3. Alerts System
  {
    id: 'alerts-user',
    method: 'GET',
    path: '/api/alerts/user/{chat_id}',
    title: 'Get User Alerts',
    desc: 'Retrieves the list of all active alerts belonging to a specific user / chat_id.',
    params: [],
    curlExample: `curl "${API_BASE}/api/alerts/user/123456789"`,
    jsExample: `const res = await fetch("${API_BASE}/api/alerts/user/123456789");\nconst data = await res.json();\nconsole.log(data);`,
    responseExample: `[ { "id": "1", "token": "jup", "condition": ">", "threshold": 1.5 } ]`
  },
  {
    id: 'alerts-create',
    method: 'POST',
    path: '/api/alerts/create',
    title: 'Create Alert',
    desc: 'Creates a new alert rule / notification.',
    params: [],
    curlExample: `curl -X POST "${API_BASE}/api/alerts/create" -H "Content-Type: application/json" -d '{"user_id":123,"token":"jup","chain":"solana","alert_type":"PRICE","condition":">","threshold":1.2}'`,
    jsExample: `const res = await fetch("${API_BASE}/api/alerts/create", {\n  method: "POST",\n  headers: { "Content-Type": "application/json" },\n  body: JSON.stringify({\n    user_id: 123456789,\n    token: "jup",\n    chain: "solana",\n    alert_type: "PRICE",\n    condition: ">",\n    threshold: 1.5,\n    notify_telegram: true,\n    notify_web: true\n  })\n});`,
    responseExample: `{ "success": true, "alert_id": "1" }`
  },
  {
    id: 'alerts-toggle',
    method: 'PUT',
    path: '/api/alerts/{alert_id}/toggle',
    title: 'Toggle Alert Status',
    desc: 'Temporarily turns on (true) or off (false) an alert.',
    params: [],
    curlExample: `curl -X PUT "${API_BASE}/api/alerts/1/toggle" -H "Content-Type: application/json" -d 'true'`,
    jsExample: `const res = await fetch("${API_BASE}/api/alerts/1/toggle", {\n  method: "PUT",\n  headers: { "Content-Type": "application/json" },\n  body: JSON.stringify(true)\n});`,
    responseExample: `{ "success": true, "active": true }`
  },
  {
    id: 'alerts-delete',
    method: 'DELETE',
    path: '/api/alerts/{alert_id}',
    title: 'Delete Alert',
    desc: 'Permanently deletes an alert from the database.',
    params: [],
    curlExample: `curl -X DELETE "${API_BASE}/api/alerts/1"`,
    jsExample: `const res = await fetch("${API_BASE}/api/alerts/1", { method: "DELETE" });\nconst data = await res.json();`,
    responseExample: `{ "success": true }`
  },

  // 4. Market Data (Pricing)
  {
    id: 'prices-live',
    method: 'GET',
    path: '/api/prices/live',
    title: 'Get Live Token Price',
    desc: 'Gets live prices of multiple tokens at once in a single request.',
    params: [
      { name: 'tokens', required: true, desc: 'Comma-separated token list, e.g. jup,sol,ray' },
      { name: 'chain', required: true, desc: 'Blockchain network name: solana, ethereum, bsc, base, etc.' },
    ],
    curlExample: `curl "${API_BASE}/api/prices/live?tokens=jup,sol&chain=solana"`,
    jsExample: `const res = await fetch("${API_BASE}/api/prices/live?tokens=jup,sol&chain=solana");\nconst data = await res.json();\nconsole.log(data);`,
    responseExample: `{ "chain": "solana", "prices": { "jup": 1.24, "sol": 142.87 } }`,
  },
  {
    id: 'klines',
    method: 'GET',
    path: '/api/klines',
    title: 'Get Chart / Klines Data',
    desc: 'Fetches historical OHLCV candle data for specific token charting.',
    params: [
      { name: 'token', required: true, desc: 'Token symbol, e.g. jup, sol' },
      { name: 'chain', required: true, desc: 'Target chain name' },
      { name: 'days', required: false, desc: 'Number of historical data days (default: 7)' },
      { name: 'interval', required: false, desc: 'Candle interval in minutes, e.g. 60 = 1 hour' },
    ],
    curlExample: `curl "${API_BASE}/api/klines?token=jup&chain=solana&days=30&interval=60"`,
    jsExample: `const url = "${API_BASE}/api/klines?token=jup&chain=solana&days=30&interval=60";\nconst res = await fetch(url);\nconst klines = await res.json();\nconsole.log(klines);`,
    responseExample: `[ { "time": 1712908800, "open": 1.12, "high": 1.18, "low": 1.10, "close": 1.15, "volume": 123456 } ]`,
  },
];

const ERRORS = [
  {
    title: 'CORS Error',
    icon: '🚫',
    desc: 'Frontend cannot access backend from the browser. Ensure backend allows frontend origin.',
    origins: ['https://www.avetrace.xyz', 'https://avetrace.vercel.app'],
  },
  {
    title: 'WebSocket Keeps Reconnecting',
    icon: '🔁',
    desc: 'Usually caused by one of the following conditions:',
    bullets: [
      'Incorrect WebSocket URL',
      'Still using ws:// when it should be wss://',
      'Incorrect endpoint path (e.g. /ws, should be /ws/live-buysell)',
      'Nginx Proxy does not support WebSocket upgrade yet',
      'Backend is not sending data',
    ],
  },
  {
    title: '404 Not Found',
    icon: '❓',
    desc: 'Incorrect endpoint path. Make sure to use the correct path according to this documentation.',
  },
];

const METHOD_CLASS = { GET: 'method-get', POST: 'method-post', PUT: 'method-put', DELETE: 'method-delete' };

/* ── Sub-components ───────────────────────────────────── */
function CodeBlock({ lang, code }) {
  return (
    <div className="apidoc-code-wrap">
      <span className="apidoc-code-lang">{lang}</span>
      <pre className="apidoc-code"><code>{code}</code></pre>
    </div>
  );
}

function EndpointCard({ ep }) {
  return (
    <div className="api-card glass" id={ep.id}>
      <div className="api-card-header">
        <span className={`method-badge ${METHOD_CLASS[ep.method]}`}>{ep.method}</span>
        <code className="api-path">{ep.path}</code>
      </div>
      <p className="api-desc">{ep.desc}</p>

      {ep.params.length > 0 && (
        <div className="api-params">
          <div className="api-params-title">Parameters</div>
          <div className="api-params-list">
            {ep.params.map((p) => (
              <div key={p.name} className="api-param-row">
                <div className="api-param-left">
                  <code className="param-name">{p.name}</code>
                  <span className={`param-required ${p.required ? 'req' : 'opt'}`}>
                    {p.required ? 'required' : 'optional'}
                  </span>
                </div>
                <div className="api-param-desc">{p.desc}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="apidoc-examples">
        <CodeBlock lang="curl" code={ep.curlExample} />
        <CodeBlock lang="javascript" code={ep.jsExample} />
        <CodeBlock lang="response" code={ep.responseExample} />
      </div>
    </div>
  );
}

/* ── Main component ───────────────────────────────────── */
export default function ApiDocs() {
  return (
    <section className="glass mini-section api-docs-section">
      {/* Header */}
      <div className="table-header">
        <h2>API Reference — AVE Trace</h2>
        <span className="api-base-badge">{API_BASE}</span>
      </div>
      <p className="helper">
        Complete backend API endpoint documentation for AVE Trace. Covering Analysis Engine, Live Feeds, Telegram, Alert Management.
      </p>

      {/* Production URLs */}
      <div className="apidoc-urls-grid">
        <div className="apidoc-url-card">
          <span className="apidoc-url-label">🌐 Frontend</span>
          <code>https://www.avetrace.xyz</code>
        </div>
        <div className="apidoc-url-card">
          <span className="apidoc-url-label">⚡ API</span>
          <code>https://api.avetrace.xyz</code>
        </div>
        <div className="apidoc-url-card">
          <span className="apidoc-url-label">🔌 WebSocket</span>
          <code>wss://api.avetrace.xyz/ws/live-buysell</code>
        </div>
      </div>

      {/* HTTP Endpoints */}
      <div className="api-group">
        <h3 className="api-group-title">📡 HTTP Endpoints</h3>
        <div className="api-cards">
          {ENDPOINTS.map((ep) => (
            <EndpointCard key={ep.id} ep={ep} />
          ))}
        </div>
      </div>

      {/* WebSocket */}
      <div className="api-group">
        <h3 className="api-group-title">🔌 WebSocket Live Feed</h3>

        <div className="api-card glass">
          <div className="api-card-header">
            <span className="method-badge method-ws">WS</span>
            <code className="api-path">/ws/live-buysell</code>
          </div>
          <p className="api-desc">
            Receives filtered DEX transaction live feeds in realtime. The endpoint supports query parameters <code>?sample=4&max_rows=75</code>
          </p>

          <div className="apidoc-examples">
            <CodeBlock lang="auto-reconnect" code={`function connectWebSocket() {
  const ws = new WebSocket("${WS_BASE}/ws/live-buysell?sample=4&max_rows=75");

  ws.onopen = () => { console.log("Connected to live feed"); };

  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      if (data.type === 'ready') console.log("Tracked tokens:", data.tracked_tokens);
      else if (data.type === 'row') console.log("Incoming TX:", data.row);
    } catch {
      console.log(event.data);
    }
  };

  ws.onclose = () => { setTimeout(connectWebSocket, 3000); };
}
connectWebSocket();`} />
          </div>
        </div>
      </div>

      {/* Quick Reference */}
      <div className="api-group">
        <h3 className="api-group-title">📋 Endpoints Summary</h3>
        <div className="api-card glass">
          <CodeBlock lang="HTTP" code={`GET    /api/analyze?token=<token>&chain=<chain>
GET    /api/sweep?category=<cat>&chain=<chain>&top=<num>
GET    /api/prices/live?tokens=<tokens>&chain=<chain>
GET    /api/klines?token=<t>&chain=<c>&days=<d>&interval=<i>
GET    /api/telegram/status
GET    /api/telegram/connection?chat_id=<id>
POST   /api/telegram/test
GET    /api/alerts/user/<chat_id>
POST   /api/alerts/create
PUT    /api/alerts/<id>/toggle
DELETE /api/alerts/<id>`} />
          <CodeBlock lang="WebSocket" code={`wss://api.avetrace.xyz/ws/live-buysell`} />
        </div>
      </div>

      {/* Don't use */}
      <div className="apidoc-warning-box" style={{ marginTop: '30px' }}>
        <span className="apidoc-warning-icon">⛔</span>
        <div>
          <strong>Do not use in production:</strong>
          <div className="apidoc-warning-list">
            {['localhost', '127.0.0.1', 'Direct VPS IP (e.g. 159.223.x.x)', 'ws:// for HTTPS frontend'].map((x) => (
              <code key={x} className="apidoc-warning-code">{x}</code>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

import { Fragment, useEffect, useMemo, useRef, useState } from 'react';
import { LightChartViewer } from './TradingViewChart';

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000';
const PAIR_CACHE_KEY = 'ave_pair_cache_v1';

const CHAINS = ['solana', 'ethereum', 'bsc', 'base', 'arbitrum', 'optimism', 'polygon', 'avalanche'];

function buildPairCacheKey(tokenAddress, chain) {
  const addr = String(tokenAddress || '').trim().toLowerCase();
  const ch = String(chain || '').trim().toLowerCase();
  if (!addr || !ch) return '';
  return `${addr}-${ch}`;
}

function getIntervalMinutes(days) {
  return days <= 7 ? 60 : days <= 30 ? 120 : 240;
}

function formatMoney(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '-';
  const n = Number(value);
  if (Math.abs(n) >= 1_000_000_000) return `$${(n / 1_000_000_000).toFixed(2)}B`;
  if (Math.abs(n) >= 1_000_000) return `$${(n / 1_000_000).toFixed(2)}M`;
  if (Math.abs(n) >= 1_000) return `$${(n / 1_000).toFixed(2)}K`;
  return `$${n.toFixed(4)}`;
}

function scoreTone(score) {
  if (score >= 75) return 'tone-red';
  if (score >= 55) return 'tone-orange';
  if (score >= 35) return 'tone-yellow';
  return 'tone-green';
}

function buildTrendCacheKey(item, chain) {
  const addr = String(item?.address || item?.ca || '').trim().toLowerCase();
  const tok = String(item?.token || '').trim().toLowerCase();
  const ch = String(chain || '').trim().toLowerCase();
  if (!ch) return '';
  if (addr) return `${addr}-${ch}`;
  if (tok) return `${tok}-${ch}`;
  return '';
}

function normalizeKlinePoints(points = []) {
  return (points || [])
    .map((p) => {
      const tRaw = Number(p.time);
      const t = tRaw > 10_000_000_000 ? Math.floor(tRaw / 1000) : Math.floor(tRaw);
      const open = Number(p.open);
      const high = Number(p.high);
      const low = Number(p.low);
      const close = Number(p.close);
      const volume = Number(p.volume || 0);
      return { time: t, open, high, low, close, volume };
    })
    .filter(
      (p) =>
        Number.isFinite(p.time) &&
        p.time > 0 &&
        Number.isFinite(p.open) &&
        Number.isFinite(p.high) &&
        Number.isFinite(p.low) &&
        Number.isFinite(p.close) &&
        p.high >= p.low
    )
    .sort((a, b) => a.time - b.time);
}

function buildTrendSnapshotFromKlines(validPoints = []) {
  if (!validPoints.length) return null;

  const latest = validPoints[validPoints.length - 1];
  const latestClose = Number(latest.close);
  const cutoff = Number(latest.time) - 24 * 60 * 60;

  let basePoint = validPoints[0];
  for (let i = validPoints.length - 1; i >= 0; i -= 1) {
    if (Number(validPoints[i].time) <= cutoff) {
      basePoint = validPoints[i];
      break;
    }
  }

  const baseClose = Number(basePoint?.close || 0);
  const change24h = baseClose > 0 ? ((latestClose - baseClose) / baseClose) * 100 : 0;
  const sparkline = validPoints.slice(-24).map((p) => Number(p.close));

  return {
    latestClose,
    change24h,
    sparkline,
    updatedAt: Date.now(),
    latestTime: latest.time,
  };
}

function Sparkline({ points = [] }) {
  if (!points.length) return <div className="spark-empty">no trend</div>;
  const max = Math.max(...points);
  const min = Math.min(...points);
  const range = max - min || 1;
  const d = points
    .map((p, i) => {
      const x = (i / (points.length - 1 || 1)) * 100;
      const y = 38 - ((p - min) / range) * 32;
      return `${i === 0 ? 'M' : 'L'} ${x.toFixed(2)} ${y.toFixed(2)}`;
    })
    .join(' ');

  return (
    <svg viewBox="0 0 100 40" preserveAspectRatio="none" className="sparkline" aria-hidden="true">
      <defs>
        <linearGradient id="sparkFill" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stopColor="rgba(71, 240, 255, 0.5)" />
          <stop offset="100%" stopColor="rgba(71, 240, 255, 0)" />
        </linearGradient>
      </defs>
      <path d={`${d} L 100 40 L 0 40 Z`} fill="url(#sparkFill)" />
      <path d={d} fill="none" stroke="#4bf0ff" strokeWidth="1.4" />
    </svg>
  );
}

function buildSMA(values, period) {
  const out = new Array(values.length).fill(null);
  if (period <= 1) return values;
  let sum = 0;
  for (let i = 0; i < values.length; i += 1) {
    sum += values[i];
    if (i >= period) sum -= values[i - period];
    if (i >= period - 1) out[i] = sum / period;
  }
  return out;
}

function buildEMA(values, period) {
  const out = new Array(values.length).fill(null);
  if (!values.length) return out;
  const k = 2 / (period + 1);
  let ema = values[0];
  for (let i = 0; i < values.length; i += 1) {
    ema = i === 0 ? values[0] : values[i] * k + ema * (1 - k);
    if (i >= period - 1) out[i] = ema;
  }
  return out;
}

function buildLinePath(series, xOf, yOf) {
  let started = false;
  const segments = [];
  for (let i = 0; i < series.length; i += 1) {
    const v = series[i];
    if (v === null || v === undefined || Number.isNaN(v)) continue;
    const cmd = started ? 'L' : 'M';
    started = true;
    segments.push(`${cmd} ${xOf(i).toFixed(2)} ${yOf(v).toFixed(2)}`);
  }
  return segments.join(' ');
}

function TradingChart({ data, chartType, showMA, showEMA }) {
  const [hoverIndex, setHoverIndex] = useState(-1);
  if (!data.length) return <p className="empty-note">No chart data.</p>;

  const highs = data.map((d) => d.high);
  const lows = data.map((d) => d.low);
  const closes = data.map((d) => d.close);
  const volumes = data.map((d) => d.volume || 0);
  const max = Math.max(...highs);
  const min = Math.min(...lows);
  const range = max - min || 1;
  const maxVolume = Math.max(...volumes, 1);

  const yOf = (v) => 95 - ((v - min) / range) * 90;
  const xOf = (idx) => 4 + (idx / (data.length - 1 || 1)) * 92;
  const yVol = (v) => 94 - (v / maxVolume) * 88;

  const ma20 = buildSMA(closes, 20);
  const ema20 = buildEMA(closes, 20);
  const maPath = showMA ? buildLinePath(ma20, xOf, yOf) : '';
  const emaPath = showEMA ? buildLinePath(ema20, xOf, yOf) : '';

  const safeHover = hoverIndex >= 0 && hoverIndex < data.length ? hoverIndex : -1;
  const hoverCandle = safeHover >= 0 ? data[safeHover] : null;
  const hoverX = safeHover >= 0 ? xOf(safeHover) : null;
  const hoverY = safeHover >= 0 ? yOf(data[safeHover].close) : null;

  if (chartType === 'line' || chartType === 'area') {
    const linePath = data
      .map((d, i) => `${i === 0 ? 'M' : 'L'} ${xOf(i).toFixed(2)} ${yOf(d.close).toFixed(2)}`)
      .join(' ');
    const areaPath = `${linePath} L 96 95 L 4 95 Z`;

    return (
      <div className="tv-chart-stack">
        <div className="tv-main-wrap">
          <svg
            viewBox="0 0 100 100"
            preserveAspectRatio="none"
            className="tv-chart-svg"
            onMouseMove={(e) => {
              const rect = e.currentTarget.getBoundingClientRect();
              const relX = (e.clientX - rect.left) / rect.width;
              const idx = Math.round(relX * (data.length - 1));
              setHoverIndex(Math.max(0, Math.min(data.length - 1, idx)));
            }}
            onMouseLeave={() => setHoverIndex(-1)}
          >
            <defs>
              <linearGradient id="tvArea" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="rgba(75,240,255,0.45)" />
                <stop offset="100%" stopColor="rgba(75,240,255,0)" />
              </linearGradient>
            </defs>
            {chartType === 'area' ? <path d={areaPath} fill="url(#tvArea)" /> : null}
            <path d={linePath} fill="none" stroke="#66e6ff" strokeWidth="0.8" />
            {showMA && maPath ? <path d={maPath} fill="none" stroke="#ffd166" strokeWidth="0.52" /> : null}
            {showEMA && emaPath ? <path d={emaPath} fill="none" stroke="#b388ff" strokeWidth="0.52" /> : null}
            {safeHover >= 0 ? (
              <>
                <line x1={hoverX} y1="4" x2={hoverX} y2="96" stroke="rgba(200,225,255,0.5)" strokeWidth="0.2" />
                <line x1="4" y1={hoverY} x2="96" y2={hoverY} stroke="rgba(200,225,255,0.32)" strokeWidth="0.2" />
              </>
            ) : null}
          </svg>
          {hoverCandle ? (
            <div className="tv-tooltip">
              <span>O {hoverCandle.open.toFixed(6)}</span>
              <span>H {hoverCandle.high.toFixed(6)}</span>
              <span>L {hoverCandle.low.toFixed(6)}</span>
              <span>C {hoverCandle.close.toFixed(6)}</span>
            </div>
          ) : null}
        </div>

        <div className="tv-volume-wrap">
          <svg viewBox="0 0 100 100" preserveAspectRatio="none" className="tv-volume-svg">
            {data.map((d, i) => {
              const x = xOf(i);
              const w = Math.max(0.2, Math.min(1.1, 70 / Math.max(data.length, 1)));
              const y = yVol(d.volume || 0);
              const bullish = d.close >= d.open;
              return (
                <rect
                  key={`v-${d.time}-${i}`}
                  x={x - w / 2}
                  y={y}
                  width={w}
                  height={94 - y}
                  fill={bullish ? 'rgba(62,255,181,0.55)' : 'rgba(255,95,132,0.55)'}
                />
              );
            })}
          </svg>
        </div>
      </div>
    );
  }

  const candleWidth = Math.max(0.28, Math.min(1.1, 70 / Math.max(data.length, 1)));

  return (
    <div className="tv-chart-stack">
      <div className="tv-main-wrap">
        <svg
          viewBox="0 0 100 100"
          preserveAspectRatio="none"
          className="tv-chart-svg"
          onMouseMove={(e) => {
            const rect = e.currentTarget.getBoundingClientRect();
            const relX = (e.clientX - rect.left) / rect.width;
            const idx = Math.round(relX * (data.length - 1));
            setHoverIndex(Math.max(0, Math.min(data.length - 1, idx)));
          }}
          onMouseLeave={() => setHoverIndex(-1)}
        >
          {data.map((d, i) => {
            const x = xOf(i);
            const yOpen = yOf(d.open);
            const yClose = yOf(d.close);
            const yHigh = yOf(d.high);
            const yLow = yOf(d.low);
            const bullish = d.close >= d.open;
            const top = Math.min(yOpen, yClose);
            const height = Math.max(0.7, Math.abs(yOpen - yClose));
            return (
              <g key={`${d.time}-${i}`}>
                <line
                  x1={x}
                  y1={yHigh}
                  x2={x}
                  y2={yLow}
                  stroke={bullish ? '#3effb5' : '#ff5f84'}
                  strokeWidth="0.22"
                />
                <rect
                  x={x - candleWidth / 2}
                  y={top}
                  width={candleWidth}
                  height={height}
                  fill={bullish ? 'rgba(62,255,181,0.8)' : 'rgba(255,95,132,0.85)'}
                  stroke={bullish ? '#3effb5' : '#ff5f84'}
                  strokeWidth="0.08"
                />
              </g>
            );
          })}
          {showMA && maPath ? <path d={maPath} fill="none" stroke="#ffd166" strokeWidth="0.52" /> : null}
          {showEMA && emaPath ? <path d={emaPath} fill="none" stroke="#b388ff" strokeWidth="0.52" /> : null}
          {safeHover >= 0 ? (
            <>
              <line x1={hoverX} y1="4" x2={hoverX} y2="96" stroke="rgba(200,225,255,0.5)" strokeWidth="0.2" />
              <line x1="4" y1={hoverY} x2="96" y2={hoverY} stroke="rgba(200,225,255,0.32)" strokeWidth="0.2" />
            </>
          ) : null}
        </svg>
        {hoverCandle ? (
          <div className="tv-tooltip">
            <span>O {hoverCandle.open.toFixed(6)}</span>
            <span>H {hoverCandle.high.toFixed(6)}</span>
            <span>L {hoverCandle.low.toFixed(6)}</span>
            <span>C {hoverCandle.close.toFixed(6)}</span>
          </div>
        ) : null}
      </div>

      <div className="tv-volume-wrap">
        <svg viewBox="0 0 100 100" preserveAspectRatio="none" className="tv-volume-svg">
          {data.map((d, i) => {
            const x = xOf(i);
            const w = Math.max(0.2, Math.min(1.1, 70 / Math.max(data.length, 1)));
            const y = yVol(d.volume || 0);
            const bullish = d.close >= d.open;
            return (
              <rect
                key={`v-${d.time}-${i}`}
                x={x - w / 2}
                y={y}
                width={w}
                height={94 - y}
                fill={bullish ? 'rgba(62,255,181,0.55)' : 'rgba(255,95,132,0.55)'}
              />
            );
          })}
        </svg>
      </div>
    </div>
  );
}

export default function App() {
  const [token, setToken] = useState('jup');
  const [chain, setChain] = useState('solana');
  const [category, setCategory] = useState('all');
  const [top, setTop] = useState(6);

  const [report, setReport] = useState(null);
  const [sweep, setSweep] = useState([]);
  const [trendCache, setTrendCache] = useState({});
  const [status, setStatus] = useState('Idle');
  const [error, setError] = useState('');
  const [activeNav, setActiveNav] = useState('Dashboard');
  const [selectedToken, setSelectedToken] = useState('');
  const [selectedPairAddress, setSelectedPairAddress] = useState('');
  const [selectedTokenAddress, setSelectedTokenAddress] = useState('');
  const [selectedRowKey, setSelectedRowKey] = useState('');
  const [chartData, setChartData] = useState([]);
  const [chartLoading, setChartLoading] = useState(false);
  const [chartError, setChartError] = useState('');
  const [timeframe, setTimeframe] = useState(30);
  const [chartType, setChartType] = useState('candlestick');
  const [showMA, setShowMA] = useState(true);
  const [showEMA, setShowEMA] = useState(true);
  const [alerts, setAlerts] = useState([]);
  const [alertsTab, setAlertsTab] = useState('create');
  const [alertsStats, setAlertsStats] = useState({ total: 0, enabled: 0, monitored_tokens: 0, by_type: {} });
  const userId = 1; // Mock user ID - replace with actual user context
  const sweepRef = useRef([]);
  const pairCacheRef = useRef({});

  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(PAIR_CACHE_KEY);
      pairCacheRef.current = raw ? JSON.parse(raw) : {};
    } catch {
      pairCacheRef.current = {};
    }
  }, []);

  function cachePairAddress(tokenAddr, chainName, pairAddr) {
    const key = buildPairCacheKey(tokenAddr, chainName);
    const pair = String(pairAddr || '').trim();
    if (!key || !pair) return;

    if (pairCacheRef.current[key] === pair) return;
    pairCacheRef.current = {
      ...pairCacheRef.current,
      [key]: pair,
    };

    try {
      window.localStorage.setItem(PAIR_CACHE_KEY, JSON.stringify(pairCacheRef.current));
    } catch {
      // Ignore storage errors and keep runtime cache only.
    }
  }

  function getCachedPairAddress(tokenAddr, chainName) {
    const key = buildPairCacheKey(tokenAddr, chainName);
    if (!key) return '';
    return String(pairCacheRef.current[key] || '');
  }

  const sectionRefs = {
    Dashboard: useRef(null),
    Assets: useRef(null),
    'Signal Engine': useRef(null),
    'Whale Feed': useRef(null),
    'Risk Matrix': useRef(null),
  };

  const navItems = ['Dashboard', 'Assets', 'Signal Engine', 'Whale Feed', 'Risk Matrix'];

  const watchlistMock = useMemo(
    () => [
      { symbol: 'JUP', amount: '$7,689.00', chain: 'solana' },
      { symbol: 'AVAX', amount: '$1,340.00', chain: 'avalanche' },
      { symbol: 'MATIC', amount: '$540.00', chain: 'polygon' },
      { symbol: 'SEI', amount: '$980.00', chain: 'solana' },
    ],
    []
  );

  useEffect(() => {
    sweepRef.current = sweep;
  }, [sweep]);

  useEffect(() => {
    if (!sweep.length) return undefined;

    let disposed = false;

    async function refreshLivePrices() {
      const tokenList = Array.from(
        new Set(
          (sweepRef.current || [])
            .map((item) => String(item?.token || '').trim().toLowerCase())
            .filter(Boolean)
        )
      ).slice(0, 20);

      if (!tokenList.length) return;

      try {
        const query = new URLSearchParams({
          tokens: tokenList.join(','),
          chain: String(chain),
        });
        const res = await fetch(`${API_BASE}/api/prices/live?${query.toString()}`);
        const payload = await res.json();
        if (!res.ok) throw new Error(payload.detail || 'Live price request failed');
        if (disposed) return;

        const quotes = payload.quotes || {};
        setSweep((prev) =>
          prev.map((item) => {
            const key = String(item?.token || '').toLowerCase();
            const quote = quotes[key];
            if (!quote) return item;
            return {
              ...item,
              price: Number(quote.price ?? item.price),
              price_change_24h: Number(quote.price_change_24h ?? item.price_change_24h),
            };
          })
        );

        setReport((prev) => {
          if (!prev) return prev;
          const key = String(prev.token || token || '').toLowerCase();
          const quote = quotes[key];
          if (!quote) return prev;
          return {
            ...prev,
            price: Number(quote.price ?? prev.price),
            price_change_24h: Number(quote.price_change_24h ?? prev.price_change_24h),
          };
        });
      } catch (err) {
        console.error('Live price update error:', err);
      }
    }

    refreshLivePrices();
    const intervalId = window.setInterval(refreshLivePrices, 5000);

    return () => {
      disposed = true;
      window.clearInterval(intervalId);
    };
  }, [chain, sweep.length, token]);

  async function analyzeToken() {
    setStatus('Analyzing token...');
    setError('');
    try {
      const res = await fetch(`${API_BASE}/api/analyze?token=${encodeURIComponent(token)}&chain=${encodeURIComponent(chain)}`);
      const payload = await res.json();
      if (!res.ok) throw new Error(payload.detail || 'Analyze failed');
      setReport(payload);
      setStatus(`Analysis complete for ${payload.token?.toUpperCase?.() || token.toUpperCase()}`);
    } catch (err) {
      setError(err.message);
      setStatus('Analysis failed');
    }
  }

  async function syncSweepWithChartKlines(items, chainName) {
    const rows = Array.isArray(items) ? items.slice(0, 20) : [];
    if (!rows.length) return;

    const updates = {};
    for (const item of rows) {
      const tokenSymbol = String(item?.token || '').trim();
      if (!tokenSymbol) continue;

      try {
        const tokenAddress = String(item?.address || item?.ca || '').trim();
        const cachedPair = getCachedPairAddress(tokenAddress, chainName);
        const pairAddress = String(item?.pair_address || item?.pair || item?.pair_id || cachedPair || '').trim();

        const query = new URLSearchParams({
          token: tokenSymbol,
          chain: String(chainName),
          days: '2',
          interval: '60',
          strict_live: 'true',
        });
        if (pairAddress) query.set('pair_address', pairAddress);
        if (tokenAddress) query.set('token_address', tokenAddress);

        const res = await fetch(`${API_BASE}/api/klines?${query.toString()}`);
        const payload = await res.json();
        if (!res.ok) continue;

        const validPoints = normalizeKlinePoints(payload.points || []);
        const snapshot = buildTrendSnapshotFromKlines(validPoints);
        if (!snapshot) continue;

        const resolvedTokenAddress = String(payload.token_address || tokenAddress || '').trim();
        const resolvedPairAddress = String(payload.pair_address || pairAddress || '').trim();
        if (resolvedPairAddress) {
          cachePairAddress(resolvedTokenAddress || tokenAddress, chainName, resolvedPairAddress);
        }

        const key = buildTrendCacheKey(
          {
            token: tokenSymbol,
            address: resolvedTokenAddress || tokenAddress,
            ca: resolvedTokenAddress || tokenAddress,
          },
          chainName
        );
        if (!key) continue;
        updates[key] = snapshot;
      } catch (err) {
        console.error(`Trend snapshot sync failed for ${tokenSymbol}:`, err);
      }
    }

    if (Object.keys(updates).length) {
      setTrendCache((prev) => ({ ...prev, ...updates }));
    }
  }

  async function runSweep() {
    const scopeLabel = category === 'all' ? `${chain} network-wide` : `${chain} (${category} filter)`;
    setStatus(`Running sweep: ${scopeLabel}...`);
    setError('');
    try {
      const res = await fetch(
        `${API_BASE}/api/sweep?category=${encodeURIComponent(category)}&chain=${encodeURIComponent(chain)}&top=${top}`
      );
      const payload = await res.json();
      if (!res.ok) throw new Error(payload.detail || 'Sweep failed');
      const results = payload.results || [];
      setSweep(results);
      syncSweepWithChartKlines(results, chain);
      setStatus(`Sweep complete (${scopeLabel}): ${(payload.results || []).length} assets`);
    } catch (err) {
      setError(err.message);
      setStatus('Sweep failed');
    }
  }

  // Alert Management Functions
  async function loadTokenAlerts(tok, cn) {
    try {
      const res = await fetch(`${API_BASE}/api/alerts/token/${tok}?chain=${cn}`);
      const data = await res.json();
      setAlerts(data.alerts || []);
    } catch (err) {
      console.error('Error loading alerts:', err);
      setAlerts([]);
    }
  }

  async function loadAlertsStats() {
    try {
      const res = await fetch(`${API_BASE}/api/alerts/stats`);
      const data = await res.json();
      setAlertsStats(data);
    } catch (err) {
      console.error('Error loading stats:', err);
    }
  }

  async function createAlert(alertData) {
    try {
      const res = await fetch(`${API_BASE}/api/alerts/create`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          ...alertData,
          notify_telegram: true,
          notify_web: true,
        }),
      });
      if (!res.ok) throw new Error('Failed to create alert');
      await loadTokenAlerts(alertData.token, alertData.chain);
      await loadAlertsStats();
      setStatus('✅ Alert created successfully');
    } catch (err) {
      setError(`Alert creation failed: ${err.message}`);
    }
  }

  async function deleteAlert(alertId) {
    try {
      const res = await fetch(`${API_BASE}/api/alerts/${alertId}`, { method: 'DELETE' });
      if (!res.ok) throw new Error('Failed to delete alert');
      await loadTokenAlerts(token, chain);
      await loadAlertsStats();
      setStatus('✅ Alert deleted');
    } catch (err) {
      setError(`Delete failed: ${err.message}`);
    }
  }

  async function toggleAlert(alertId, enabled) {
    try {
      const res = await fetch(`${API_BASE}/api/alerts/${alertId}/toggle`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(enabled),
      });
      if (!res.ok) throw new Error('Failed to toggle alert');
      await loadTokenAlerts(token, chain);
      await loadAlertsStats();
      setStatus(`✅ Alert ${enabled ? 'enabled' : 'disabled'}`);
    } catch (err) {
      setError(`Toggle failed: ${err.message}`);
    }
  }

  function handleNavigate(label) {
    setActiveNav(label);
    sectionRefs[label]?.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  async function openTokenChart(item, rowKey) {
    if (!item?.token) return;

    if (selectedRowKey === rowKey) {
      setSelectedRowKey('');
      setSelectedToken('');
      setSelectedPairAddress('');
      setSelectedTokenAddress('');
      setChartData([]);
      setChartError('');
      return;
    }

    setSelectedRowKey(rowKey);
    setSelectedToken(item.token);
    const tokenAddress = item.address || item.ca || '';
    setSelectedTokenAddress(String(tokenAddress || ''));
    const cachedPair = getCachedPairAddress(tokenAddress, chain);
    const pairAddress = item.pair_address || item.pair || item.pair_id || cachedPair || '';
    setSelectedPairAddress(pairAddress);
    if (!pairAddress) {
      setStatus(`Pair address not provided for ${String(item.token).toUpperCase()}; backend resolver will be used.`);
    }
    setChartLoading(true);
    setChartError('');
    try {
      const interval = getIntervalMinutes(timeframe);
      const query = new URLSearchParams({
        token: String(item.token),
        chain: String(chain),
        days: String(timeframe),
        interval: String(interval),
        strict_live: 'true',
      });
      if (pairAddress) query.set('pair_address', pairAddress);
      if (tokenAddress) query.set('token_address', tokenAddress);

      const res = await fetch(
        `${API_BASE}/api/klines?${query.toString()}`
      );
      const payload = await res.json();
      console.log('histori response', payload);
      
      if (!res.ok) throw new Error(payload.detail || 'Chart request failed');

      const resolvedPairAddress = String(payload.pair_address || pairAddress || '');
      if (resolvedPairAddress) {
        setSelectedPairAddress(resolvedPairAddress);
        cachePairAddress(payload.token_address || tokenAddress, chain, resolvedPairAddress);
      }

      const resolvedTokenAddress = String(payload.token_address || tokenAddress || '');
      if (resolvedTokenAddress) {
        setSelectedTokenAddress(resolvedTokenAddress);
      }
      
      const points = payload.points || [];
      console.log(`Chart loaded: ${item.token} - ${points.length} candles`, points.slice(0, 3));
      
      if (!points.length) {
        setChartError('No chart data received');
        setChartData([]);
      } else {
        const validPoints = normalizeKlinePoints(points);

        console.log('candles length', validPoints.length);
        if (!validPoints.length) {
          setChartError('Invalid chart data format');
          setChartData([]);
        } else {
          const snapshot = buildTrendSnapshotFromKlines(validPoints);
          const trendKey = buildTrendCacheKey(
            {
              token: item.token,
              address: resolvedTokenAddress || tokenAddress,
              ca: resolvedTokenAddress || tokenAddress,
            },
            chain
          );
          if (snapshot && trendKey) {
            setTrendCache((prev) => ({ ...prev, [trendKey]: snapshot }));
          }

          setChartData(validPoints);
          setStatus(`Chart loaded: ${String(item.token).toUpperCase()} (${timeframe}D) - ${validPoints.length} candles`);
          setChartError('');
        }
      }
    } catch (err) {
      console.error('Chart error:', err);
      setChartError(err.message || 'Failed to load chart');
      setChartData([]);
      setStatus(`Chart error: ${err.message}`);
    } finally {
      setChartLoading(false);
    }
  }

  async function reloadChartForTimeframe(nextDays) {
    setTimeframe(nextDays);
    if (!selectedToken) return;
    setChartLoading(true);
    setChartError('');
    setChartData([]); // Clear old data immediately for UI consistency
    try {
      const interval = getIntervalMinutes(nextDays);
      const query = new URLSearchParams({
        token: String(selectedToken),
        chain: String(chain),
        days: String(nextDays),
        interval: String(interval),
        strict_live: 'true',
      });
      if (selectedPairAddress) query.set('pair_address', selectedPairAddress);
      if (selectedTokenAddress) query.set('token_address', selectedTokenAddress);

      const res = await fetch(
        `${API_BASE}/api/klines?${query.toString()}`
      );
      const payload = await res.json();
      console.log('histori response', payload);
      
      if (!res.ok) throw new Error(payload.detail || 'Chart request failed');

      const resolvedPairAddress = String(payload.pair_address || selectedPairAddress || '');
      if (resolvedPairAddress) {
        setSelectedPairAddress(resolvedPairAddress);
        cachePairAddress(payload.token_address || selectedTokenAddress, chain, resolvedPairAddress);
      }

      const resolvedTokenAddress = String(payload.token_address || selectedTokenAddress || '');
      if (resolvedTokenAddress) {
        setSelectedTokenAddress(resolvedTokenAddress);
      }
      
      const points = payload.points || [];
      console.log(`Timeframe changed: ${nextDays}D - ${points.length} candles`);
      
      if (!points.length) {
        setChartError('No data for this timeframe');
        setChartData([]);
      } else {
        const validPoints = normalizeKlinePoints(points);

        console.log('candles length', validPoints.length);
        if (!validPoints.length) {
          setChartError('Invalid data format');
          setChartData([]);
        } else {
          const snapshot = buildTrendSnapshotFromKlines(validPoints);
          const trendKey = buildTrendCacheKey(
            {
              token: selectedToken,
              address: resolvedTokenAddress || selectedTokenAddress,
              ca: resolvedTokenAddress || selectedTokenAddress,
            },
            chain
          );
          if (snapshot && trendKey) {
            setTrendCache((prev) => ({ ...prev, [trendKey]: snapshot }));
          }

          setChartData(validPoints);
          setChartError('');
          setStatus(`Chart reloaded: ${nextDays}D - ${validPoints.length} candles`);
        }
      }
    } catch (err) {
      console.error('Timeframe reload error:', err);
      setChartError(err.message || 'Failed to reload chart');
      setChartData([]);
    } finally {
      setChartLoading(false);
    }
  }

  return (
    <div className="page-shell">
      <div className="bg-grid" />
      <aside className="left-rail">
        <div className="brand">Ave Claw</div>
        <div className="rail-section">Navigation</div>
        {navItems.map((item) => (
          <button
            key={item}
            className={`nav-item ${activeNav === item ? 'active' : ''}`}
            onClick={() => handleNavigate(item)}
          >
            {item}
          </button>
        ))}

        <div className="rail-section margin-top">Active Tracking</div>
        <div className="watchlist-stack">
          {watchlistMock.map((item) => (
            <div key={item.symbol} className="watch-item">
              <div>
                <strong>{item.symbol}</strong>
                <p>{item.chain}</p>
              </div>
              <span>{item.amount}</span>
            </div>
          ))}
        </div>
      </aside>

      <main className="main-pane">
        <header className="topbar">
          <div>
            <h1>Accumulation Command Center</h1>
            <p>Detect quiet smart-money accumulation before market ignition.</p>
          </div>
          <div className="status-pill">{status}</div>
        </header>

        <section className="hero-grid" ref={sectionRefs.Dashboard}>
          <article className="glass card analyze-card">
            <h2>Single Token Probe</h2>
            <div className="control-grid">
              <label>
                Token
                <input value={token} onChange={(e) => setToken(e.target.value)} placeholder="jup" />
              </label>
              <label>
                Chain
                <select value={chain} onChange={(e) => setChain(e.target.value)}>
                  {CHAINS.map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <button onClick={analyzeToken} className="btn-primary">Analyze Now</button>

            {report ? (
              <div className="report-grid">
                <div className="metric-box">
                  <span>Price</span>
                  <strong>{formatMoney(report.price)}</strong>
                </div>
                <div className="metric-box">
                  <span>24h Move</span>
                  <strong>{Number(report.price_change_24h || 0).toFixed(2)}%</strong>
                </div>
                <div className="metric-box">
                  <span>TVL</span>
                  <strong>{formatMoney(report.tvl)}</strong>
                </div>
                <div className="metric-box">
                  <span>Holders</span>
                  <strong>{Number(report.holders || 0).toLocaleString()}</strong>
                </div>
                <div style={{ gridColumn: '1 / -1', marginTop: '8px' }}>
                  <button
                    className="btn-trade"
                    style={{ width: '100%', padding: '8px 12px' }}
                    onClick={() => {
                      const ca = report.address || report.ca || token;
                      window.open(`https://pro.ave.ai/token/${ca}-${chain}`, '_blank');
                    }}
                  >
                    🚀 Trade on Ave
                  </button>
                </div>
              </div>
            ) : (
              <p className="empty-note">Run one token to fill this panel.</p>
            )}
          </article>

          <article className="glass card score-card">
            <h2>Risk-Adjusted Score</h2>
            {report ? (
              <>
                <div className={`score-orb ${scoreTone(report.score?.risk_adjusted || 0)}`}>
                  {report.score?.risk_adjusted || 0}
                </div>
                <p className="phase-line">Market phase: {(report.score?.market_phase || '-').toUpperCase()}</p>
                <div className="signal-list">
                  <div><span>Volume Divergence</span><b>{report.signals?.volume_divergence ?? '-'}</b></div>
                  <div><span>Volume Momentum</span><b>{report.signals?.volume_momentum ?? '-'}</b></div>
                  <div><span>TVL Stability</span><b>{report.signals?.tvl_stability ?? '-'}</b></div>
                  <div><span>Holder Distribution</span><b>{report.signals?.holder_distribution ?? '-'}</b></div>
                  <div><span>Whale Score</span><b>{report.signals?.whale_score ?? '-'}</b></div>
                </div>
              </>
            ) : (
              <p className="empty-note">No score yet.</p>
            )}
          </article>

          <article className="glass card action-card">
            <h2>Market Sweep</h2>
            <div className="control-grid single">
              <label>
                Category Filter
                <select value={category} onChange={(e) => setCategory(e.target.value)}>
                  <option value="all">all (network-wide)</option>
                  <option value="trending">trending</option>
                  <option value="meme">meme</option>
                  <option value="defi">defi</option>
                  <option value="gaming">gaming</option>
                  <option value="ai">ai</option>
                </select>
              </label>
              <label>
                Top
                <input
                  value={top}
                  onChange={(e) => setTop(Number(e.target.value || 1))}
                  min={1}
                  max={20}
                  type="number"
                />
              </label>
            </div>
            <button onClick={runSweep} className="btn-ghost">Run Sweep</button>
            <p className="helper">Sweep scans the selected chain first; category is optional and acts as a soft filter.</p>
          </article>
        </section>

        <section className="glass table-section" ref={sectionRefs.Assets}>
          <div className="table-header">
            <h2>Top Signal Candidates</h2>
            <span>{sweep.length} assets</span>
          </div>

          {sweep.length ? (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>#</th>
                    <th>Token</th>
                    <th>Price</th>
                    <th>24h</th>
                    <th>Risk Adj</th>
                    <th>Alert</th>
                    <th>Trend</th>
                    <th>Trade</th>
                  </tr>
                </thead>
                <tbody>
                  {sweep.map((item, idx) => {
                    const rowKey = `${item.token}-${idx}`;
                    const trendKey = buildTrendCacheKey(item, chain);
                    const trendSnapshot = trendCache[trendKey];
                    const displayPrice = Number.isFinite(Number(trendSnapshot?.latestClose))
                      ? Number(trendSnapshot.latestClose)
                      : Number(item.price || 0);
                    const displayChange24h = Number.isFinite(Number(trendSnapshot?.change24h))
                      ? Number(trendSnapshot.change24h)
                      : Number(item.price_change_24h || 0);
                    const trendPoints = Array.isArray(trendSnapshot?.sparkline) && trendSnapshot.sparkline.length
                      ? trendSnapshot.sparkline
                      : [
                          item.price_change_24h || 0,
                          (item.signals?.volume_divergence || 0) / 3,
                          (item.signals?.whale_score || 0) / 4,
                          item.score?.risk_adjusted || 0,
                        ];
                    return (
                      <Fragment key={rowKey}>
                        <tr className="clickable-row" onClick={() => openTokenChart(item, rowKey)}>
                          <td>{idx + 1}</td>
                          <td>
                            <span className="token-link">{(item.token || '-').toUpperCase()}</span>
                          </td>
                          <td>{formatMoney(displayPrice)}</td>
                          <td className={displayChange24h >= 0 ? 'up' : 'down'}>
                            {displayChange24h.toFixed(2)}%
                          </td>
                          <td>{item.score?.risk_adjusted ?? '-'}</td>
                          <td>
                            <span className={`alert-dot ${scoreTone(item.score?.risk_adjusted || 0)}`} />
                            {(item.score?.alert_level || '-').toUpperCase()}
                          </td>
                          <td><Sparkline points={trendPoints} /></td>
                          <td>
                            <button
                              className="btn-trade"
                              onClick={(e) => {
                                e.stopPropagation();
                                const ca = item.address || item.ca || item.token;
                                const url = `https://pro.ave.ai/token/${ca}-${chain}`;
                                window.open(url, '_blank');
                              }}
                            >
                              🚀 Trade
                            </button>
                          </td>
                        </tr>

                        {selectedRowKey === rowKey ? (
                          <tr className="chart-inline-row">
                            <td colSpan={8} className="chart-inline-cell">
                              <div className="tv-toolbar inline">
                                <div className="tv-control-group">
                                  <span>Timeframe</span>
                                  {[7, 14, 30, 90].map((d) => (
                                    <button
                                      key={d}
                                      className={`tv-chip ${timeframe === d ? 'active' : ''}`}
                                      onClick={(e) => {
                                        e.stopPropagation();
                                        reloadChartForTimeframe(d);
                                      }}
                                    >
                                      {d}D
                                    </button>
                                  ))}
                                </div>
                                <div className="tv-control-group">
                                  <span>Type</span>
                                  {['candlestick', 'line', 'area'].map((type) => (
                                    <button
                                      key={type}
                                      className={`tv-chip ${chartType === type ? 'active' : ''}`}
                                      onClick={(e) => {
                                        e.stopPropagation();
                                        setChartType(type);
                                      }}
                                    >
                                      {type}
                                    </button>
                                  ))}
                                </div>
                                <div className="tv-control-group">
                                  <span>Indicators</span>
                                  <button
                                    className={`tv-chip ${showMA ? 'active' : ''}`}
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      setShowMA((v) => !v);
                                    }}
                                  >
                                    MA20
                                  </button>
                                  <button
                                    className={`tv-chip ${showEMA ? 'active' : ''}`}
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      setShowEMA((v) => !v);
                                    }}
                                  >
                                    EMA20
                                  </button>
                                </div>
                              </div>

                              <div className="tv-chart-panel inline">
                                {chartLoading ? <p className="empty-note">Loading chart...</p> : null}
                                {chartError ? <div className="error-banner">{chartError}</div> : null}
                                {!chartLoading && !chartError && chartData.length ? (
                                  <LightChartViewer
                                    data={chartData}
                                    token={selectedToken}
                                    chain={chain}
                                    pairAddress={selectedPairAddress}
                                    tokenAddress={selectedTokenAddress}
                                    intervalMinutes={getIntervalMinutes(timeframe)}
                                    chartType={chartType}
                                    showMA={showMA}
                                    showEMA={showEMA}
                                    onPairDiscovered={(pair) => {
                                      if (!pair) return;
                                      setSelectedPairAddress((prev) => (prev === pair ? prev : pair));
                                      cachePairAddress(selectedTokenAddress, chain, pair);
                                    }}
                                  />
                                ) : null}
                              </div>

                              {chartData.length ? (
                                <div className="chart-stats">
                                  <span>{selectedToken.toUpperCase()} · {chain}</span>
                                  <span>Open: {formatMoney(chartData[chartData.length - 1]?.open)}</span>
                                  <span>High: {formatMoney(chartData[chartData.length - 1]?.high)}</span>
                                  <span>Low: {formatMoney(chartData[chartData.length - 1]?.low)}</span>
                                  <span>Close: {formatMoney(chartData[chartData.length - 1]?.close)}</span>
                                </div>
                              ) : null}
                            </td>
                          </tr>
                        ) : null}
                      </Fragment>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="empty-note">Run category sweep to populate live opportunities.</p>
          )}
        </section>

        <section className="glass mini-section" ref={sectionRefs['Signal Engine']}>
          <div className="table-header">
            <h2>Signal Engine</h2>
          </div>
          <p className="empty-note">
            Gunakan Analyze dan Sweep untuk menghasilkan signal. Klik token pada Top Signal Candidates untuk membuka chart.
          </p>
        </section>

        <section className="glass mini-section" ref={sectionRefs['Whale Feed']}>
          <div className="table-header">
            <h2>Whale Feed</h2>
          </div>
          <p className="empty-note">
            Integrasi trade API tersedia di dokumentasi resmi Ave Bot API.
          </p>
          <a className="doc-link" href="https://docs-bot-api.ave.ai/" target="_blank" rel="noreferrer">
            Buka Trade API Docs
          </a>
        </section>

        <section className="glass mini-section" ref={sectionRefs['Risk Matrix']}>
          <div className="table-header">
            <h2>Risk Matrix</h2>
          </div>
          <p className="empty-note">
            Risk matrix dihitung dari Risk-Adjusted Score, whale concentration, dan anomali volume pada panel utama.
          </p>
        </section>

        {error ? <div className="error-banner">{error}</div> : null}
      </main>
    </div>
  );
}

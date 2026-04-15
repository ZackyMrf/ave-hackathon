import { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import LandingScreen from './components/LandingScreen';
import PlatformTopNav from './components/PlatformTopNav';
import DashboardSection from './components/sections/DashboardSection';
import SignalEngineSection from './components/sections/SignalEngineSection';
import WhaleFeedSection from './components/sections/WhaleFeedSection';
import RiskMatrixSection from './components/sections/RiskMatrixSection';
import ApiDocs from './components/ApiDocs';
import { CHAINS, SIGNAL_PRESETS } from './constants/monitoring';
import {
  buildPairCacheKey,
  buildTrendCacheKey,
  buildTrendSnapshotFromKlines,
  getIntervalMinutes,
  getRiskTier,
  normalizeKlinePoints,
} from './utils/monitoring';
import { useMonitoringFetchActions } from './hooks/useMonitoringFetchActions';

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000';
const PAIR_CACHE_KEY = 'ave_pair_cache_v1';
const TELEGRAM_CHAT_ID_KEY = 'ave_telegram_chat_id_v1';
const WATCHLIST_STORAGE_KEY = 'ave_watchlist_v1';

export default function App() {
  const [token, setToken] = useState('jup');
  const [tokenSearchMode, setTokenSearchMode] = useState('symbol');
  const [chain, setChain] = useState('solana');
  const [sweepChain, setSweepChain] = useState('solana');
  const [category, setCategory] = useState('trending');
  const [top, setTop] = useState(6);

  const [report, setReport] = useState(null);
  const [sweep, setSweep] = useState([]);
  const [trendCache, setTrendCache] = useState({});
  const [status, setStatus] = useState('Idle');
  const [error, setError] = useState('');
  // ── URL-based routing ────────────────────────────────────────────────────
  const navigate = useNavigate();
  const location = useLocation();

  const PATH_TO_NAV = {
    '/':           'home',
    '/home':       'home',
    '/dashboard':  'Dashboard',
    '/signal':     'Signal Engine',
    '/whale-feed': 'Whale Feed',
    '/risk-matrix':'Risk Matrix',
    '/api-docs':   'ApiDocs',
  };

  const NAV_TO_PATH = {
    'home':          '/home',
    'Dashboard':     '/dashboard',
    'Signal Engine': '/signal',
    'Whale Feed':    '/whale-feed',
    'Risk Matrix':   '/risk-matrix',
    'ApiDocs':       '/api-docs',
  };

  const activeNav = PATH_TO_NAV[location.pathname] ?? 'Dashboard';

  function setActiveNav(navKey) {
    navigate(NAV_TO_PATH[navKey] ?? '/dashboard');
  }
  // ────────────────────────────────────────────────────────────────────────────
  const [selectedToken, setSelectedToken] = useState('');
  const [selectedPairAddress, setSelectedPairAddress] = useState('');
  const [selectedTokenAddress, setSelectedTokenAddress] = useState('');
  const [selectedRowKey, setSelectedRowKey] = useState('');
  const [selectedChartChain, setSelectedChartChain] = useState('solana');
  const [chartData, setChartData] = useState([]);
  const [chartLoading, setChartLoading] = useState(false);
  const [chartError, setChartError] = useState('');
  const [timeframe, setTimeframe] = useState(30);
  const [showMA, setShowMA] = useState(true);
  const [showEMA, setShowEMA] = useState(true);
  const [alerts, setAlerts] = useState([]);
  const [alertsTab, setAlertsTab] = useState('create');
  const [alertsStats, setAlertsStats] = useState({ total: 0, enabled: 0, monitored_tokens: 0, by_type: {} });
  const [enginePreset, setEnginePreset] = useState('Swing');
  const [engineMinRisk, setEngineMinRisk] = useState(55);
  const [engineMinWhale, setEngineMinWhale] = useState(12);
  const [engineRequireUptrend, setEngineRequireUptrend] = useState(false);
  const [whaleToken, setWhaleToken] = useState('jup');
  const [whaleChain, setWhaleChain] = useState('solana');
  const [whaleLoading, setWhaleLoading] = useState(false);
  const [whaleError, setWhaleError] = useState('');
  const [whaleReport, setWhaleReport] = useState(null);
  const [selectedWhaleWallet, setSelectedWhaleWallet] = useState('');
  const [whaleWalletHistory, setWhaleWalletHistory] = useState({});
  const [sweepLoading, setSweepLoading] = useState(false);
  const showHome = activeNav === 'home';
  const [telegramChatIdInput, setTelegramChatIdInput] = useState(() => {
    try {
      return window.localStorage.getItem(TELEGRAM_CHAT_ID_KEY) || '';
    } catch {
      return '';
    }
  });
  const [telegramStatus, setTelegramStatus] = useState({
    tokenConfigured: false,
    botReachable: false,
    botUsername: '',
  });
  const [telegramActionLoading, setTelegramActionLoading] = useState(false);
  const [telegramConnection, setTelegramConnection] = useState({
    checked: false,
    userConnected: false,
    detail: '',
    chatType: '',
    chatDisplay: '',
    username: '',
    firstName: '',
    profilePhotoUrl: '',
  });
  const [telegramDeepLink, setTelegramDeepLink] = useState({
    code: '',
    url: '',
    status: 'idle',
    detail: '',
    expiresAt: 0,
  });
  const [telegramMenuOpen, setTelegramMenuOpen] = useState(false);
  const [telegramMenuAlerts, setTelegramMenuAlerts] = useState([]);
  const [telegramMenuAlertsLoading, setTelegramMenuAlertsLoading] = useState(false);
  const [telegramMenuWatchlist, setTelegramMenuWatchlist] = useState([]);

  const parsedTelegramChatId = Number.parseInt(String(telegramChatIdInput || '').trim(), 10);
  const hasValidTelegramChatId = Number.isInteger(parsedTelegramChatId) && parsedTelegramChatId !== 0;
  const telegramConnected = Boolean(telegramConnection.userConnected && hasValidTelegramChatId);
  const telegramAvatarFallback = String(
    telegramConnection.firstName || telegramConnection.username || telegramConnection.chatDisplay || 'TG'
  )
    .trim()
    .slice(0, 2)
    .toUpperCase();
  const sweepRef = useRef([]);
  const pairCacheRef = useRef({});
  const mainPaneRef = useRef(null);
  const sweepAbortControllerRef = useRef(null);
  const telegramDeepLinkPollRef = useRef(null);

  function stopTelegramDeepLinkPolling() {
    if (telegramDeepLinkPollRef.current) {
      window.clearInterval(telegramDeepLinkPollRef.current);
      telegramDeepLinkPollRef.current = null;
    }
  }

  useEffect(() => () => {
    stopTelegramDeepLinkPolling();
  }, []);

  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(PAIR_CACHE_KEY);
      pairCacheRef.current = raw ? JSON.parse(raw) : {};
    } catch {
      pairCacheRef.current = {};
    }
  }, []);

  useEffect(() => {
    loadTelegramMenuWatchlist();
  }, []);

  useEffect(() => {
    try {
      const nextValue = String(telegramChatIdInput || '').trim();
      if (nextValue) {
        window.localStorage.setItem(TELEGRAM_CHAT_ID_KEY, nextValue);
      } else {
        window.localStorage.removeItem(TELEGRAM_CHAT_ID_KEY);
      }
    } catch {
      // Ignore storage write failures.
    }
  }, [telegramChatIdInput]);

  useEffect(() => {
    let ignore = false;

    async function loadTelegramStatus() {
      try {
        const res = await fetch(`${API_BASE}/api/telegram/status`);
        const payload = await res.json();
        if (!res.ok) throw new Error(payload.detail || 'Failed to load Telegram status');
        if (ignore) return;
        setTelegramStatus({
          tokenConfigured: Boolean(payload.token_configured),
          botReachable: Boolean(payload.bot_reachable),
          botUsername: String(payload.bot_username || ''),
        });
      } catch (err) {
        if (ignore) return;
        console.error('Error loading Telegram status:', err);
        setTelegramStatus({ tokenConfigured: false, botReachable: false, botUsername: '' });
      }
    }

    loadTelegramStatus();
    return () => {
      ignore = true;
    };
  }, []);

  async function refreshTelegramStatus() {
    try {
      const res = await fetch(`${API_BASE}/api/telegram/status`);
      const payload = await res.json();
      if (!res.ok) throw new Error(payload.detail || 'Failed to load Telegram status');
      const next = {
        tokenConfigured: Boolean(payload.token_configured),
        botReachable: Boolean(payload.bot_reachable),
        botUsername: String(payload.bot_username || ''),
      };
      setTelegramStatus(next);
      return next;
    } catch (err) {
      console.error('Error refreshing Telegram status:', err);
      const fallback = { tokenConfigured: false, botReachable: false, botUsername: '' };
      setTelegramStatus(fallback);
      return fallback;
    }
  }

  useEffect(() => {
    if (!telegramStatus.tokenConfigured || !hasValidTelegramChatId) return;
    checkTelegramUserConnection(parsedTelegramChatId);
  }, [telegramStatus.tokenConfigured, hasValidTelegramChatId, parsedTelegramChatId]);

  useEffect(() => {
    if (!telegramConnected && telegramMenuOpen) {
      setTelegramMenuOpen(false);
    }
  }, [telegramConnected, telegramMenuOpen]);

  useEffect(() => {
    if (!telegramMenuOpen || !telegramConnected || !hasValidTelegramChatId) return;
    loadTelegramMenuAlerts(parsedTelegramChatId);
    loadTelegramMenuWatchlist();
  }, [telegramMenuOpen, telegramConnected, hasValidTelegramChatId, parsedTelegramChatId]);

  async function checkTelegramUserConnection(chatIdValue = parsedTelegramChatId) {
    if (!Number.isInteger(chatIdValue) || chatIdValue === 0) {
      setTelegramConnection({
        checked: false,
        userConnected: false,
        detail: 'Invalid chat ID',
        chatType: '',
        chatDisplay: '',
        username: '',
        firstName: '',
        profilePhotoUrl: '',
      });
      return null;
    }

    try {
      const res = await fetch(`${API_BASE}/api/telegram/connection?chat_id=${chatIdValue}`);
      const payload = await res.json();
      if (!res.ok) throw new Error(payload.detail || 'Failed to check Telegram connection');

      const next = {
        checked: true,
        userConnected: Boolean(payload.user_connected),
        detail: String(payload.detail || ''),
        chatType: String(payload.chat_type || ''),
        chatDisplay: String(payload.chat_display || ''),
        username: String(payload.username || ''),
        firstName: String(payload.first_name || ''),
        profilePhotoUrl: String(payload.profile_photo_url || ''),
      };
      setTelegramConnection(next);
      return payload;
    } catch (err) {
      setTelegramConnection({
        checked: true,
        userConnected: false,
        detail: String(err?.message || 'Failed to check Telegram connection'),
        chatType: '',
        chatDisplay: '',
        username: '',
        firstName: '',
        profilePhotoUrl: '',
      });
      return null;
    }
  }

  async function pollTelegramDeepLinkSession(codeValue) {
    const code = String(codeValue || '').trim();
    if (!code) return;

    try {
      const res = await fetch(`${API_BASE}/api/telegram/deeplink/session/${encodeURIComponent(code)}`);
      const payload = await res.json();
      if (!res.ok) throw new Error(payload.detail || 'Failed to poll Telegram login status');

      if (payload.expired) {
        setTelegramDeepLink((prev) => ({
          ...prev,
          status: 'expired',
          detail: 'Login session expired. Generate a new Telegram link.',
        }));
        stopTelegramDeepLinkPolling();
        return;
      }

      if (payload.claimed && payload.chat_id) {
        const claimedChatId = Number.parseInt(String(payload.chat_id), 10);
        if (Number.isInteger(claimedChatId)) {
          setTelegramChatIdInput(String(claimedChatId));
          await checkTelegramUserConnection(claimedChatId);
          setStatus(`✅ Telegram linked to chat ${claimedChatId}`);
        }

        const displayName = String(payload.first_name || payload.username || '').trim();
        setTelegramDeepLink((prev) => ({
          ...prev,
          status: 'claimed',
          detail: displayName ? `Connected as ${displayName}` : 'Connected',
        }));
        stopTelegramDeepLinkPolling();
        return;
      }

      setTelegramDeepLink((prev) => ({
        ...prev,
        status: 'waiting',
        detail: 'Waiting for /start confirmation from Telegram...',
      }));
    } catch (err) {
      setTelegramDeepLink((prev) => ({
        ...prev,
        status: 'error',
        detail: String(err?.message || 'Failed to poll Telegram login status'),
      }));
      stopTelegramDeepLinkPolling();
    }
  }

  async function startTelegramDeepLinkLogin() {
    setTelegramActionLoading(true);
    try {
      const latestStatus = await refreshTelegramStatus();
      if (!latestStatus.tokenConfigured || !latestStatus.botReachable) {
        setError('Bot token is not ready or bot is unreachable.');
        return;
      }

      const res = await fetch(`${API_BASE}/api/telegram/deeplink/session`, {
        method: 'POST',
      });
      const payload = await res.json();
      if (!res.ok) throw new Error(payload.detail || 'Failed to create Telegram login link');

      const deepLink = String(payload.deep_link || '').trim();
      const code = String(payload.code || '').trim();
      const expiresAt = Number(payload.expires_at || 0);

      if (!deepLink || !code) {
        throw new Error('Invalid Telegram deep-link payload');
      }

      setTelegramDeepLink({
        code,
        url: deepLink,
        status: 'waiting',
        detail: 'Open link and press Start in Telegram bot.',
        expiresAt,
      });
      setError('');
      setStatus('Open Telegram link, then press Start to complete login.');

      window.open(deepLink, '_blank', 'noopener,noreferrer');

      stopTelegramDeepLinkPolling();
      await pollTelegramDeepLinkSession(code);
      telegramDeepLinkPollRef.current = window.setInterval(() => {
        pollTelegramDeepLinkSession(code);
      }, 2500);
    } catch (err) {
      setTelegramDeepLink({
        code: '',
        url: '',
        status: 'error',
        detail: String(err?.message || 'Failed to create Telegram deep-link'),
        expiresAt: 0,
      });
      setError(`Telegram login link failed: ${err.message}`);
    } finally {
      setTelegramActionLoading(false);
    }
  }

  function disconnectTelegram() {
    stopTelegramDeepLinkPolling();
    setTelegramChatIdInput('');
    setTelegramConnection({
      checked: false,
      userConnected: false,
      detail: '',
      chatType: '',
      chatDisplay: '',
      username: '',
      firstName: '',
      profilePhotoUrl: '',
    });
    setTelegramDeepLink({
      code: '',
      url: '',
      status: 'idle',
      detail: '',
      expiresAt: 0,
    });
    setError('');
    setStatus('Telegram disconnected');
    setTelegramMenuOpen(false);
    setTelegramMenuAlerts([]);
    setTelegramMenuWatchlist([]);
  }

  async function loadTelegramMenuAlerts(chatIdValue = parsedTelegramChatId) {
    if (!Number.isInteger(chatIdValue) || chatIdValue === 0) {
      setTelegramMenuAlerts([]);
      return;
    }

    setTelegramMenuAlertsLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/alerts/user/${chatIdValue}`);
      const payload = await res.json();
      if (!res.ok) throw new Error(payload.detail || 'Failed to load user alerts');
      setTelegramMenuAlerts(Array.isArray(payload.alerts) ? payload.alerts : []);
    } catch (err) {
      console.error('Telegram menu alerts load failed:', err);
      setTelegramMenuAlerts([]);
    } finally {
      setTelegramMenuAlertsLoading(false);
    }
  }

  function loadTelegramMenuWatchlist() {
    try {
      const raw = window.localStorage.getItem(WATCHLIST_STORAGE_KEY);
      const parsed = raw ? JSON.parse(raw) : [];
      setTelegramMenuWatchlist(Array.isArray(parsed) ? parsed : []);
    } catch (err) {
      console.error('Telegram menu watchlist load failed:', err);
      setTelegramMenuWatchlist([]);
    }
  }

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

  const navItems = useMemo(
    () => [
      { key: 'home', label: 'Home' },
      { key: 'Dashboard', label: 'Dashboard' },
      { key: 'Signal Engine', label: 'Signal Engine' },
      { key: 'Whale Feed', label: 'Whale Feed' },
      { key: 'Risk Matrix', label: 'Risk Matrix' },
      { key: 'ApiDocs', label: 'API Docs' },
    ],
    []
  );

  const signalKpis = useMemo(() => {
    const total = sweep.length;
    const highConviction = sweep.filter((item) => Number(item?.score?.risk_adjusted || 0) >= 75).length;
    const withTrend = sweep.filter((item) => {
      const key = buildTrendCacheKey(item, sweepChain);
      return Boolean(key && trendCache[key]);
    }).length;
    const latestRisk = Number(report?.score?.risk_adjusted || 0);

    return {
      total,
      highConviction,
      withTrend,
      latestRisk,
    };
  }, [sweep, trendCache, sweepChain, report]);

  const signalEngineRows = useMemo(() => {
    const minRisk = Number(engineMinRisk || 0);
    const minWhale = Number(engineMinWhale || 0);

    return (sweep || [])
      .map((item, idx) => {
        const riskAdj = Number(item?.score?.risk_adjusted || 0);
        const whaleScore = Number(item?.signals?.whale_score || 0);
        const trendKey = buildTrendCacheKey(item, sweepChain);
        const trend = Number(trendCache[trendKey]?.change24h ?? item?.price_change_24h ?? 0);
        const passTrend = engineRequireUptrend ? trend > 0 : true;
        const passed = riskAdj >= minRisk && whaleScore >= minWhale && passTrend;
        const action = passed && riskAdj >= 75 && whaleScore >= 20 ? 'TRIGGER' : passed ? 'WATCH' : 'IGNORE';

        return {
          id: `sig-${idx}`,
          token: String(item?.token || '-').toUpperCase(),
          riskAdj,
          whaleScore,
          trend,
          action,
          passed,
        };
      })
      .filter((row) => row.passed)
      .sort((a, b) => (b.riskAdj + b.whaleScore) - (a.riskAdj + a.whaleScore))
      .slice(0, 20);
  }, [sweep, sweepChain, trendCache, engineMinRisk, engineMinWhale, engineRequireUptrend]);

  const whaleFeedRows = useMemo(() => {
    const whales = Array.isArray(whaleReport?.whales) ? whaleReport.whales : [];
    return whales.slice(0, 20).map((w, idx) => ({
      id: `wf-${idx}`,
      address: String(w.address || '').trim(),
      ratio: Number(w.balance_ratio || 0),
      delta: Number(w.change_24h || 0),
      isNew: Boolean(w.is_new),
    }));
  }, [whaleReport]);

  const selectedWhaleTimeline = useMemo(() => {
    const key = String(selectedWhaleWallet || '').trim().toLowerCase();
    if (!key) return [];
    const rows = Array.isArray(whaleWalletHistory[key]) ? whaleWalletHistory[key] : [];
    return [...rows].sort((a, b) => Number(b.capturedAt || 0) - Number(a.capturedAt || 0)).slice(0, 30);
  }, [selectedWhaleWallet, whaleWalletHistory]);

  const riskRows = useMemo(() => {
    if (sweep.length) {
      return sweep.slice(0, 12).map((item, idx) => {
        const riskAdj = Number(item?.score?.risk_adjusted || 0);
        return {
          id: `risk-${idx}`,
          token: String(item?.token || '-').toUpperCase(),
          riskAdj,
          tier: getRiskTier(riskAdj),
          whaleScore: Number(item?.signals?.whale_score || 0),
          volDiv: Number(item?.signals?.volume_divergence || 0),
        };
      });
    }

    if (report?.token) {
      const riskAdj = Number(report?.score?.risk_adjusted || 0);
      return [
        {
          id: 'risk-single',
          token: String(report.token).toUpperCase(),
          riskAdj,
          tier: getRiskTier(riskAdj),
          whaleScore: Number(report?.signals?.whale_score || 0),
          volDiv: Number(report?.signals?.volume_divergence || 0),
        },
      ];
    }

    return [];
  }, [sweep, report]);

  const riskSummary = useMemo(() => {
    const summary = { high: 0, elevated: 0, watch: 0, low: 0 };
    for (const row of riskRows) {
      summary[row.tier] = (summary[row.tier] || 0) + 1;
    }
    return summary;
  }, [riskRows]);

  const homeMetrics = useMemo(
    () => ({
      tracked: sweep.length,
      enabledAlerts: Number(alertsStats?.enabled || 0),
      chains: CHAINS.length,
      lastRisk: Number(report?.score?.risk_adjusted || 0),
    }),
    [sweep.length, alertsStats, report]
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
          chain: String(sweepChain),
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
  }, [sweepChain, sweep.length]);

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

  const { analyzeToken, runSweep, runWhaleFeedAnalysis } = useMonitoringFetchActions({
    API_BASE,
    token,
    tokenSearchMode,
    chain,
    sweepChain,
    category,
    top,
    whaleToken,
    whaleChain,
    selectedWhaleWallet,
    setTop,
    setStatus,
    setError,
    setReport,
    setSweep,
    setSweepLoading,
    setWhaleLoading,
    setWhaleError,
    setWhaleReport,
    setWhaleWalletHistory,
    setSelectedWhaleWallet,
    sweepAbortControllerRef,
    syncSweepWithChartKlines,
  });

  // Alert Management Functions
  async function saveTelegramSettings() {
    if (!hasValidTelegramChatId) {
      setError('Telegram Chat ID is not valid. Send /start to bot first, then enter the numeric chat ID.');
      return;
    }

    setTelegramActionLoading(true);
    try {
      const latestStatus = await refreshTelegramStatus();
      if (!latestStatus.tokenConfigured) {
        setError('TELEGRAM_BOT_TOKEN is not set on backend.');
        return;
      }

      const checked = await checkTelegramUserConnection(parsedTelegramChatId);
      setError('');
      if (checked?.user_connected) {
        setStatus(`✅ Telegram connected: ${parsedTelegramChatId}`);
      } else {
        setStatus(`⚠️ Chat ID saved, but bot cannot access chat ${parsedTelegramChatId} yet. Send /start to bot and check again.`);
      }
    } catch (err) {
      setError(`Telegram check failed: ${err.message}`);
    } finally {
      setTelegramActionLoading(false);
    }
  }

  async function sendTelegramTestMessage() {
    if (!hasValidTelegramChatId) {
      setError('Isi Telegram Chat ID dulu sebelum kirim test message.');
      return;
    }

    const latestStatus = await refreshTelegramStatus();
    if (!latestStatus.tokenConfigured) {
      setError('TELEGRAM_BOT_TOKEN is not set on backend.');
      return;
    }

    setTelegramActionLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/telegram/test`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ chat_id: parsedTelegramChatId }),
      });
      const payload = await res.json();
      if (!res.ok) throw new Error(payload.detail || 'Telegram test failed');
      await checkTelegramUserConnection(parsedTelegramChatId);
      setError('');
      setStatus(`✅ Test message sent to chat ${parsedTelegramChatId}`);
    } catch (err) {
      setError(`Telegram test failed: ${err.message}`);
    } finally {
      setTelegramActionLoading(false);
    }
  }

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
      if (!hasValidTelegramChatId) {
        throw new Error('Set Telegram Chat ID first in Telegram Settings panel');
      }

      const res = await fetch(`${API_BASE}/api/alerts/create`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: parsedTelegramChatId,
          ...alertData,
          notify_telegram: true,
          notify_web: true,
        }),
      });
      if (!res.ok) throw new Error('Failed to create alert');
      await loadTokenAlerts(alertData.token, alertData.chain);
      await loadAlertsStats();
      setStatus('✅ Alert created successfully');
      return true;
    } catch (err) {
      setError(`Alert creation failed: ${err.message}`);
      return false;
    }
  }

  async function deleteAlert(alertId) {
    try {
      const res = await fetch(`${API_BASE}/api/alerts/${alertId}`, { method: 'DELETE' });
      if (!res.ok) throw new Error('Failed to delete alert');
      await loadTokenAlerts(token, chain);
      await loadAlertsStats();
      setStatus('✅ Alert deleted');
      return true;
    } catch (err) {
      setError(`Delete failed: ${err.message}`);
      return false;
    }
  }

  async function deleteAlertFromTelegramMenu(alertId) {
    const ok = await deleteAlert(alertId);
    if (!ok) return;
    await loadTelegramMenuAlerts(parsedTelegramChatId);
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

  function addToWatchlist(item) {
    const tokenValue = String(item?.token || '').trim().toUpperCase();
    const chainValue = String(item?.chain || '').trim().toLowerCase();
    const addressValue = String(item?.address || '').trim();

    if (!tokenValue || !chainValue) {
      setError('Invalid watchlist data.');
      return false;
    }

    try {
      const raw = window.localStorage.getItem(WATCHLIST_STORAGE_KEY);
      const parsed = raw ? JSON.parse(raw) : [];
      const current = Array.isArray(parsed) ? parsed : [];

      const exists = current.some(
        (w) => String(w?.token || '').toUpperCase() === tokenValue
          && String(w?.chain || '').toLowerCase() === chainValue
      );

      if (exists) {
        setStatus(`⚠️ ${tokenValue} is already in watchlist ${chainValue}.`);
        return true;
      }

      const next = [
        ...current,
        {
          token: tokenValue,
          chain: chainValue,
          address: addressValue,
          added_at: new Date().toISOString(),
        },
      ];

      window.localStorage.setItem(WATCHLIST_STORAGE_KEY, JSON.stringify(next));
      setTelegramMenuWatchlist(next);
      setStatus(`✅ ${tokenValue} added to watchlist (${chainValue}).`);
      return true;
    } catch (err) {
      setError(`Watchlist save failed: ${err.message}`);
      return false;
    }
  }

  function removeFromWatchlist(item) {
    const tokenValue = String(item?.token || '').trim().toUpperCase();
    const chainValue = String(item?.chain || '').trim().toLowerCase();

    if (!tokenValue || !chainValue) {
      setError('Invalid watchlist data.');
      return false;
    }

    try {
      const raw = window.localStorage.getItem(WATCHLIST_STORAGE_KEY);
      const parsed = raw ? JSON.parse(raw) : [];
      const current = Array.isArray(parsed) ? parsed : [];
      const next = current.filter(
        (w) => !(
          String(w?.token || '').toUpperCase() === tokenValue
          && String(w?.chain || '').toLowerCase() === chainValue
        )
      );

      window.localStorage.setItem(WATCHLIST_STORAGE_KEY, JSON.stringify(next));
      setTelegramMenuWatchlist(next);
      setStatus(`✅ ${tokenValue} removed from watchlist (${chainValue}).`);
      return true;
    } catch (err) {
      setError(`Watchlist delete failed: ${err.message}`);
      return false;
    }
  }

  function isTokenInWatchlist(item) {
    const tokenValue = String(item?.token || '').trim().toUpperCase();
    const chainValue = String(item?.chain || '').trim().toLowerCase();
    if (!tokenValue || !chainValue) return false;

    return telegramMenuWatchlist.some(
      (w) => String(w?.token || '').toUpperCase() === tokenValue
        && String(w?.chain || '').toLowerCase() === chainValue
    );
  }

  function toggleWatchlist(item) {
    if (isTokenInWatchlist(item)) {
      return removeFromWatchlist(item);
    }
    return addToWatchlist(item);
  }

  function handleNavigate(label) {
    navigate(NAV_TO_PATH[label] ?? '/dashboard');
    mainPaneRef.current?.scrollTo({ top: 0, behavior: 'smooth' });
  }

  function applySignalPreset(name) {
    const preset = SIGNAL_PRESETS[name];
    if (!preset) return;
    setEnginePreset(name);
    setEngineMinRisk(preset.minRisk);
    setEngineMinWhale(preset.minWhale);
    setEngineRequireUptrend(preset.uptrendOnly);
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
    const activeSweepChain = String(sweepChain || 'solana');
    setSelectedChartChain(activeSweepChain);
    const tokenAddress = item.address || item.ca || '';
    setSelectedTokenAddress(String(tokenAddress || ''));
    const cachedPair = getCachedPairAddress(tokenAddress, activeSweepChain);
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
        chain: activeSweepChain,
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
        cachePairAddress(payload.token_address || tokenAddress, activeSweepChain, resolvedPairAddress);
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
            activeSweepChain
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
        chain: String(selectedChartChain),
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
        cachePairAddress(payload.token_address || selectedTokenAddress, selectedChartChain, resolvedPairAddress);
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
            selectedChartChain
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

  if (showHome) {
    return (
      <LandingScreen
        status={status}
        metrics={homeMetrics}
        apiBase={API_BASE}
        onEnterDashboard={() => handleNavigate('Dashboard')}
        onRunQuickSweep={() => {
          handleNavigate('Dashboard');
          runSweep();
        }}
        onOpenNav={(navLabel) => handleNavigate(navLabel)}
        token={token}
        setToken={setToken}
        tokenSearchMode={tokenSearchMode}
        setTokenSearchMode={setTokenSearchMode}
        chain={chain}
        setChain={setChain}
        onAnalyzeToken={analyzeToken}
        report={report}
        analysisError={error}
        setStatus={setStatus}
        refreshTelegramStatus={refreshTelegramStatus}
        telegramChatIdInput={telegramChatIdInput}
        setTelegramChatIdInput={setTelegramChatIdInput}
        telegramTokenConfigured={telegramStatus.tokenConfigured}
        telegramBotReachable={telegramStatus.botReachable}
        telegramBotUsername={telegramStatus.botUsername}
        startTelegramDeepLinkLogin={startTelegramDeepLinkLogin}
        telegramDeepLinkUrl={telegramDeepLink.url}
        telegramDeepLinkStatus={telegramDeepLink.status}
        telegramDeepLinkDetail={telegramDeepLink.detail}
        saveTelegramSettings={saveTelegramSettings}
        sendTelegramTestMessage={sendTelegramTestMessage}
        telegramActionLoading={telegramActionLoading}
        telegramConnectionChecked={telegramConnection.checked}
        telegramUserConnected={telegramConnection.userConnected}
        telegramConnectionDetail={telegramConnection.detail}
        telegramConnectionChatType={telegramConnection.chatType}
        telegramConnectionChatDisplay={telegramConnection.chatDisplay}
        telegramConnectionUsername={telegramConnection.username}
        telegramConnectionFirstName={telegramConnection.firstName}
        telegramConnectionProfilePhotoUrl={telegramConnection.profilePhotoUrl}
        disconnectTelegram={disconnectTelegram}
      />
    );
  }

  return (
    <div className="app-shell">
      <div className="bg-grid" />
      <PlatformTopNav
        activeItem={activeNav}
        sectionItems={navItems}
        onGoHome={() => navigate('/home')}
        onSelect={(key) => {
          if (key === 'home') { navigate('/home'); } else { handleNavigate(key); }
        }}
        primaryActionLabel={telegramActionLoading ? 'Connecting...' : 'Connect Telegram'}
        onPrimaryAction={startTelegramDeepLinkLogin}
        primaryConnected={telegramConnected}
        primaryAvatarUrl={telegramConnection.profilePhotoUrl}
        primaryAvatarFallback={telegramAvatarFallback}
        primaryAvatarTitle={telegramConnection.chatDisplay || 'Connected Telegram'}
        primaryMenuOpen={telegramMenuOpen}
        onPrimaryToggleMenu={() => setTelegramMenuOpen((prev) => !prev)}
        primaryAlerts={telegramMenuAlerts}
        primaryAlertsLoading={telegramMenuAlertsLoading}
        primaryWatchlist={telegramMenuWatchlist}
        onPrimaryDeleteAlert={deleteAlertFromTelegramMenu}
        onPrimaryDeleteWatchlist={removeFromWatchlist}
        onPrimaryDisconnect={disconnectTelegram}
      />

      <main className="app-main-pane" ref={mainPaneRef}>
        <div className="app-status-pill">Engine: {status}</div>

        {activeNav === 'Dashboard' && (
          <DashboardSection
            token={token}
            setToken={setToken}
            tokenSearchMode={tokenSearchMode}
            setTokenSearchMode={setTokenSearchMode}
            chain={chain}
            setChain={setChain}
            analyzeToken={analyzeToken}
            report={report}
            setStatus={setStatus}
            category={category}
            setCategory={setCategory}
            sweepChain={sweepChain}
            setSweepChain={setSweepChain}
            top={top}
            setTop={setTop}
            sweepLoading={sweepLoading}
            runSweep={runSweep}
            signalKpis={signalKpis}
            sweep={sweep}
            trendCache={trendCache}
            openTokenChart={openTokenChart}
            selectedRowKey={selectedRowKey}
            timeframe={timeframe}
            reloadChartForTimeframe={reloadChartForTimeframe}
            showMA={showMA}
            setShowMA={setShowMA}
            showEMA={showEMA}
            setShowEMA={setShowEMA}
            chartLoading={chartLoading}
            chartError={chartError}
            chartData={chartData}
            selectedToken={selectedToken}
            selectedChartChain={selectedChartChain}
            selectedPairAddress={selectedPairAddress}
            selectedTokenAddress={selectedTokenAddress}
            setSelectedPairAddress={setSelectedPairAddress}
            cachePairAddress={cachePairAddress}
            createAlert={createAlert}
            addToWatchlist={addToWatchlist}
            toggleWatchlist={toggleWatchlist}
            isTokenInWatchlist={isTokenInWatchlist}
          />
        )}

        {activeNav === 'Signal Engine' && (
          <SignalEngineSection
            signalEngineRows={signalEngineRows}
            enginePreset={enginePreset}
            applySignalPreset={applySignalPreset}
            engineMinRisk={engineMinRisk}
            setEngineMinRisk={setEngineMinRisk}
            engineMinWhale={engineMinWhale}
            setEngineMinWhale={setEngineMinWhale}
            engineRequireUptrend={engineRequireUptrend}
            setEngineRequireUptrend={setEngineRequireUptrend}
            setEnginePreset={setEnginePreset}
            runSweep={runSweep}
            handleNavigate={handleNavigate}
          />
        )}

        {activeNav === 'Whale Feed' && (
          <WhaleFeedSection
            whaleFeedRows={whaleFeedRows}
            whaleToken={whaleToken}
            setWhaleToken={setWhaleToken}
            whaleChain={whaleChain}
            setWhaleChain={setWhaleChain}
            runWhaleFeedAnalysis={runWhaleFeedAnalysis}
            whaleLoading={whaleLoading}
            whaleError={whaleError}
            selectedWhaleWallet={selectedWhaleWallet}
            setSelectedWhaleWallet={setSelectedWhaleWallet}
            whaleReport={whaleReport}
            selectedWhaleTimeline={selectedWhaleTimeline}
          />
        )}

        {activeNav === 'Risk Matrix' && (
          <RiskMatrixSection riskRows={riskRows} riskSummary={riskSummary} />
        )}

        {activeNav === 'ApiDocs' && (
          <div style={{width: '100%', minHeight: '60vh'}}>
            <ApiDocs />
          </div>
        )}

        {error ? <div className="error-banner">{error}</div> : null}
      </main>
    </div>
  );
}

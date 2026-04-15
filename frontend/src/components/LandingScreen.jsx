import { useEffect, useMemo, useRef, useState } from 'react';
import PlatformTopNav from './PlatformTopNav';
import { CHAINS } from '../constants/monitoring';
import { formatMoney, getAveProUrl, getBubbleMapUrl, isLikelyAddress, scoreTone, getTxExplorerUrl } from '../utils/monitoring';

const RECENT_PAGE_SIZE = 15;
const MAX_RECENT_PAGES = 5;
const MAX_RECENT_ROWS = RECENT_PAGE_SIZE * MAX_RECENT_PAGES;

function toWsUrl(apiBase) {
  const fallback = 'ws://localhost:8000/ws/live-buysell';
  const base = String(apiBase || '').trim();
  if (!base) return fallback;

  try {
    const url = new URL(base);
    const protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
    return `${protocol}//${url.host}/ws/live-buysell`;
  } catch {
    return fallback;
  }
}

function formatRelativeTime(tsInput) {
  const raw = Number(tsInput || 0);
  if (!Number.isFinite(raw) || raw <= 0) return '-';
  const ts = raw > 10_000_000_000 ? Math.floor(raw / 1000) : Math.floor(raw);
  const now = Math.floor(Date.now() / 1000);
  const diff = now - ts;

  if (diff <= 1) return 'just now';
  if (diff < 60) return `${diff}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

function shortWallet(wallet) {
  const text = String(wallet || '').trim();
  if (!text) return '-';
  if (text.length <= 12) return text;
  return `${text.slice(0, 6)}...${text.slice(-4)}`;
}

function formatUsd(usd) {
  const value = Number(usd || 0);
  if (!Number.isFinite(value)) return '$0.00';
  if (value >= 1_000_000) return `$${(value / 1_000_000).toFixed(2)}M`;
  if (value >= 1_000) return `$${(value / 1_000).toFixed(2)}K`;
  return `$${value.toFixed(2)}`;
}

export default function LandingScreen({
  status,
  metrics,
  apiBase,
  onEnterDashboard,
  onRunQuickSweep,
  onOpenNav,
  token,
  setToken,
  tokenSearchMode,
  setTokenSearchMode,
  chain,
  setChain,
  onAnalyzeToken,
  report,
  analysisError,
  setStatus,
  refreshTelegramStatus,
  telegramChatIdInput,
  setTelegramChatIdInput,
  telegramTokenConfigured,
  telegramBotReachable,
  telegramBotUsername,
  startTelegramDeepLinkLogin,
  telegramDeepLinkUrl,
  telegramDeepLinkStatus,
  telegramDeepLinkDetail,
  saveTelegramSettings,
  sendTelegramTestMessage,
  telegramActionLoading,
  telegramConnectionChecked,
  telegramUserConnected,
  telegramConnectionDetail,
  telegramConnectionChatType,
  telegramConnectionChatDisplay,
  telegramConnectionUsername,
  telegramConnectionFirstName,
  telegramConnectionProfilePhotoUrl,
  disconnectTelegram,
}) {
  const landingNavItems = [
    { key: 'home', label: 'Home' },
    { key: 'Dashboard', label: 'Dashboard' },
    { key: 'Signal Engine', label: 'Signal Engine' },
    { key: 'Whale Feed', label: 'Whale Feed' },
    { key: 'Risk Matrix', label: 'Risk Matrix' },
    { key: 'ApiDocs', label: 'API Docs' },
  ];

  const [homeAnalyzing, setHomeAnalyzing] = useState(false);
  const [showAnalyzeModal, setShowAnalyzeModal] = useState(false);
  const [showTelegramMenu, setShowTelegramMenu] = useState(false);
  const [recentRows, setRecentRows] = useState([]);
  const [txFilter, setTxFilter] = useState('all');
  const [txChainFilter, setTxChainFilter] = useState('all');
  const [feedState, setFeedState] = useState('connecting');
  const [feedError, setFeedError] = useState('');
  const [trackedTokens, setTrackedTokens] = useState([]);
  const [currentPage, setCurrentPage] = useState(1);

  const wsRef = useRef(null);
  const reconnectTimerRef = useRef(0);
  const retryDelayRef = useRef(1000);

  useEffect(() => {
    if (!showTelegramMenu) return undefined;

    function closeMenuOnOutsideClick(event) {
      const target = event.target;
      if (!(target instanceof Element)) return;
      if (target.closest('.platform-primary-profile-wrap')) return;
      setShowTelegramMenu(false);
    }

    window.addEventListener('click', closeMenuOnOutsideClick);
    return () => {
      window.removeEventListener('click', closeMenuOnOutsideClick);
    };
  }, [showTelegramMenu]);

  useEffect(() => {
    let disposed = false;
    const wsUrl = toWsUrl(apiBase);

    function upsertIncomingRow(payload) {
      const row = payload?.type === 'row' ? payload.row : payload;
      if (!row || typeof row !== 'object') return;
      const txHash = String(row.txHash || '').trim();
      const tokenAddress = String(row.tokenAddress || '').trim();
      const dedupeKey = String(row.id || `${txHash}:${tokenAddress}`).trim();
      if (!txHash || !dedupeKey) return;
      if (row.usd === null || row.usd === undefined) return;

      setRecentRows((prev) => {
        if (prev.some((item) => String(item.id || '') === dedupeKey)) return prev;
        const next = [{ ...row, id: dedupeKey }, ...prev];
        next.sort((a, b) => Number(b.time || 0) - Number(a.time || 0));
        return next.slice(0, MAX_RECENT_ROWS);
      });
    }

    function connect() {
      if (disposed) return;
      setFeedState('connecting');
      const ws = new window.WebSocket(`${wsUrl}?sample=4&max_rows=${MAX_RECENT_ROWS}`);
      wsRef.current = ws;

      ws.onopen = () => {
        if (disposed) return;
        retryDelayRef.current = 1000;
        setFeedState('live');
        setFeedError('');
      };

      ws.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data);
          if (payload?.type === 'ready') {
            setTrackedTokens(Array.isArray(payload.tracked_tokens) ? payload.tracked_tokens : []);
            return;
          }
          if (payload?.type === 'error') {
            setFeedError(String(payload.message || 'Live feed error'));
            return;
          }
          if (payload?.type === 'pong') {
            return;
          }
          upsertIncomingRow(payload);
        } catch {
          // Skip malformed payloads.
        }
      };

      ws.onerror = () => {
        if (disposed) return;
        setFeedState('error');
      };

      ws.onclose = () => {
        if (disposed) return;
        setFeedState('reconnecting');
        const delay = retryDelayRef.current;
        retryDelayRef.current = Math.min(delay * 2, 30_000);
        reconnectTimerRef.current = window.setTimeout(connect, delay);
      };
    }

    connect();

    return () => {
      disposed = true;
      if (reconnectTimerRef.current) {
        window.clearTimeout(reconnectTimerRef.current);
      }
      const ws = wsRef.current;
      if (ws && ws.readyState < 2) {
        ws.close();
      }
      wsRef.current = null;
    };
  }, [apiBase]);

  const availableChains = useMemo(() => {
    const list = Array.from(
      new Set(
        recentRows
          .map((row) => String(row?.chain || '').trim().toLowerCase())
          .filter(Boolean)
      )
    );
    return ['all', ...list];
  }, [recentRows]);

  const visibleRows = useMemo(() => {
    const filtered = recentRows.filter((row) => {
      const usd = Number(row?.usd || 0);
      const side = String(row?.side || '').toUpperCase();
      const chainValue = String(row?.chain || '').toLowerCase();

      if (txChainFilter !== 'all' && chainValue !== txChainFilter) return false;
      if (txFilter === 'usd1' && usd <= 1) return false;
      if (txFilter === 'usd10' && usd <= 10) return false;
      if (txFilter === 'buy' && side !== 'BUY') return false;
      if (txFilter === 'sell' && side !== 'SELL') return false;
      return true;
    });

    return filtered
      .slice()
      .sort((a, b) => Number(b?.time || 0) - Number(a?.time || 0));
  }, [recentRows, txChainFilter, txFilter]);

  useEffect(() => {
    setCurrentPage(1);
  }, [txFilter, txChainFilter]);

  const totalPages = useMemo(() => {
    return Math.max(1, Math.ceil(visibleRows.length / RECENT_PAGE_SIZE));
  }, [visibleRows.length]);

  const safePage = useMemo(() => {
    return Math.min(Math.max(1, currentPage), totalPages);
  }, [currentPage, totalPages]);

  useEffect(() => {
    if (currentPage !== safePage) {
      setCurrentPage(safePage);
    }
  }, [currentPage, safePage]);

  const pagedRows = useMemo(() => {
    const start = (safePage - 1) * RECENT_PAGE_SIZE;
    const end = start + RECENT_PAGE_SIZE;
    return visibleRows.slice(start, end);
  }, [safePage, visibleRows]);

  const pageNumbers = useMemo(() => {
    const pages = [];
    for (let page = 1; page <= totalPages; page += 1) {
      pages.push(page);
    }
    return pages;
  }, [totalPages]);

  async function handleHomeAnalyze(e) {
    e?.preventDefault();
    if (!onAnalyzeToken) return;
    setHomeAnalyzing(true);
    const payload = await onAnalyzeToken();
    setHomeAnalyzing(false);
    if (payload) {
      setShowAnalyzeModal(true);
    }
  }

  const telegramProfileName = String(
    telegramConnectionChatDisplay || telegramConnectionFirstName || telegramConnectionUsername || 'Telegram User'
  ).trim();
  const telegramAvatarFallback = telegramProfileName.slice(0, 2).toUpperCase() || 'TG';

  async function handleTelegramPrimaryAction() {
    if (telegramUserConnected) {
      setShowTelegramMenu((prev) => !prev);
      return;
    }

    setShowTelegramMenu(false);
    await refreshTelegramStatus?.();
    await startTelegramDeepLinkLogin?.();
  }

  function handleTelegramDisconnect() {
    disconnectTelegram?.();
    setShowTelegramMenu(false);
  }

  return (
    <div className="landing-shell bm-shell">
      <div className="bm-aura bm-aura-left" />
      <div className="bm-aura bm-aura-right" />

      <PlatformTopNav
        activeItem="home"
        sectionItems={landingNavItems}
        onGoHome={() => {}}
        onSelect={(key) => {
          if (key !== 'home') onOpenNav(key);
        }}
        secondaryActionLabel="Quick Sweep"
        onSecondaryAction={onRunQuickSweep}
        primaryActionLabel={telegramUserConnected ? '' : 'Connect Telegram'}
        onPrimaryAction={handleTelegramPrimaryAction}
        primaryConnected={telegramUserConnected}
        primaryAvatarUrl={telegramConnectionProfilePhotoUrl}
        primaryAvatarFallback={telegramAvatarFallback}
        primaryAvatarTitle={telegramProfileName}
        primaryMenuOpen={showTelegramMenu}
        onPrimaryToggleMenu={handleTelegramPrimaryAction}
        onPrimaryDisconnect={handleTelegramDisconnect}
      />

      <main className="bm-main">
        <section className="bm-search-hero">
          <form className="bm-search-form" onSubmit={handleHomeAnalyze}>
            <div className="bm-search-wrap bm-search-wrap-live">
              <span className="bm-search-icon" aria-hidden="true">
                Q
              </span>
              <input
                value={token}
                onChange={(e) => setToken(e.target.value)}
                placeholder={tokenSearchMode === 'address' ? 'Paste contract address' : 'Search by token symbol'}
                aria-label="search tokens"
              />
              <button className="bm-search-btn" type="submit" disabled={homeAnalyzing}>
                {homeAnalyzing ? 'Analyzing...' : tokenSearchMode === 'address' ? 'Analyze Address' : 'Analyze Token'}
              </button>
            </div>

            <div className="bm-search-controls">
              <div className="bm-mode-switch">
                <button
                  type="button"
                  className={`bm-mode-btn ${tokenSearchMode === 'symbol' ? 'active' : ''}`}
                  onClick={() => setTokenSearchMode('symbol')}
                >
                  Symbol
                </button>
                <button
                  type="button"
                  className={`bm-mode-btn ${tokenSearchMode === 'address' ? 'active' : ''}`}
                  onClick={() => setTokenSearchMode('address')}
                >
                  Contract Address
                </button>
              </div>

              <label className="bm-chain-select">
                Chain
                <select value={chain} onChange={(e) => setChain(e.target.value)}>
                  {CHAINS.map((c) => (
                    <option key={`home-chain-${c}`} value={c}>
                      {c}
                    </option>
                  ))}
                </select>
              </label>
            </div>
          </form>

          {analysisError ? <div className="error-banner bm-search-error">{analysisError}</div> : null}

          <div className="bm-hero-meta">
            <span>Engine {String(status || 'Idle')}</span>
            <span>Tracked {metrics.tracked}</span>
            <span>Alerts {metrics.enabledAlerts}</span>
            <span>Coverage {metrics.chains} chains</span>
            <button className="bm-chain-pill" onClick={() => onOpenNav('Dashboard')}>
              All Chains
            </button>
          </div>
        </section>

        <section className="bm-explore bm-recent">
          <div className="bm-explore-head bm-recent-head">
            <h2>Recent Transactions</h2>
            <div className="bm-feed-meta">
              <span className={`bm-feed-status ${feedState}`}>{feedState === 'live' ? 'LIVE' : feedState.toUpperCase()}</span>
              <button className="bm-dashboard-btn" onClick={onEnterDashboard}>
                Open Dashboard
              </button>
            </div>
          </div>

          <div className="bm-recent-filters">
            <button className={`bm-filter-chip ${txFilter === 'all' ? 'active' : ''}`} onClick={() => setTxFilter('all')}>
              All
            </button>
            <button className={`bm-filter-chip ${txFilter === 'usd1' ? 'active' : ''}`} onClick={() => setTxFilter('usd1')}>
              USD &gt; 1
            </button>
            <button className={`bm-filter-chip ${txFilter === 'usd10' ? 'active' : ''}`} onClick={() => setTxFilter('usd10')}>
              USD &gt; 10
            </button>
            <button className={`bm-filter-chip ${txFilter === 'buy' ? 'active' : ''}`} onClick={() => setTxFilter('buy')}>
              BUY only
            </button>
            <button className={`bm-filter-chip ${txFilter === 'sell' ? 'active' : ''}`} onClick={() => setTxFilter('sell')}>
              SELL only
            </button>

            <label className="bm-chain-select bm-recent-chain-filter">
              Chain
              <select value={txChainFilter} onChange={(e) => setTxChainFilter(e.target.value)}>
                {availableChains.map((chainOption) => (
                  <option key={`home-live-chain-${chainOption}`} value={chainOption}>
                    {chainOption}
                  </option>
                ))}
              </select>
            </label>
          </div>

          {feedError ? <div className="error-banner bm-search-error">{feedError}</div> : null}

          <article className="bm-card bm-recent-card">
            <table className="bm-recent-table mobile-card-table">
              <thead>
                <tr>
                  <th>Time</th>
                  <th>Wallet</th>
                  <th>Side</th>
                  <th>Token</th>
                  <th>Swap</th>
                  <th>USD</th>
                  <th>Chain</th>
                  <th>AMM</th>
                </tr>
              </thead>
              <tbody>
                {pagedRows.length ? (
                  pagedRows.map((row) => {
                    const timeRaw = Number(row.time || 0);
                    const ts = timeRaw > 10_000_000_000 ? Math.floor(timeRaw / 1000) : Math.floor(timeRaw);
                    return (
                      <tr key={String(row.id || `${row.txHash}:${row.tokenAddress}`)}>
                        <td data-label="Time" title={ts > 0 ? new Date(ts * 1000).toLocaleString() : '-'}>{formatRelativeTime(ts)}</td>
                        <td data-label="Wallet" className="bm-wallet">
                          {getTxExplorerUrl(row.chain, row.txHash) ? (
                            <a 
                              href={getTxExplorerUrl(row.chain, row.txHash)} 
                              target="_blank" 
                              rel="noopener noreferrer" 
                              style={{ textDecoration: 'underline', color: 'inherit' }}
                              title="View Transaction"
                            >
                              {shortWallet(row.wallet)}
                            </a>
                          ) : (
                            shortWallet(row.wallet)
                          )}
                        </td>
                        <td data-label="Side">
                          <span className={`bm-side-badge ${String(row.side || '').toUpperCase() === 'BUY' ? 'buy' : 'sell'}`}>
                            {String(row.side || '').toUpperCase() || '-'}
                          </span>
                        </td>
                        <td data-label="Token" className="bm-token-symbol">{String(row.symbol || '-').toUpperCase()}</td>
                        <td data-label="Swap">{String(row.swapLabel || '-')}</td>
                        <td data-label="USD">{formatUsd(row.usd)}</td>
                        <td data-label="Chain">
                          <span className="bm-chain-badge">{String(row.chain || '-')}</span>
                        </td>
                        <td data-label="AMM">{String(row.amm || '-')}</td>
                      </tr>
                    );
                  })
                ) : (
                  <tr>
                    <td data-label="" colSpan={8} className="bm-empty-row">
                      {feedState === 'live' ? 'Waiting for new swap transactions...' : 'Connecting to live transaction feed...'}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </article>

          <div className="bm-pagination-row">
            <button
              className="bm-page-btn"
              onClick={() => setCurrentPage((prev) => Math.max(1, prev - 1))}
              disabled={safePage <= 1}
            >
              Prev
            </button>

            <div className="bm-page-list">
              {pageNumbers.map((page) => (
                <button
                  key={`tx-page-${page}`}
                  className={`bm-page-btn ${page === safePage ? 'active' : ''}`}
                  onClick={() => setCurrentPage(page)}
                >
                  {page}
                </button>
              ))}
            </div>

            <button
              className="bm-page-btn"
              onClick={() => setCurrentPage((prev) => Math.min(totalPages, prev + 1))}
              disabled={safePage >= totalPages}
            >
              Next
            </button>
          </div>

          <div className="bm-jump-row">
            <button className="bm-jump-chip" onClick={() => onOpenNav('Signal Engine')}>
              Signal Engine
            </button>
            <button className="bm-jump-chip" onClick={() => onOpenNav('Whale Feed')}>
              Whale Feed
            </button>
            <button className="bm-jump-chip" onClick={() => onOpenNav('Risk Matrix')}>
              Risk Matrix
            </button>
          </div>
        </section>
      </main>

      {showAnalyzeModal && report ? (
        <div className="modal-backdrop" onClick={() => setShowAnalyzeModal(false)}>
          <div className="modal-card bm-analyze-modal" onClick={(e) => e.stopPropagation()}>
            <div className="bm-analyze-head">
              <h2>Single Token Probe Result</h2>
              <button className="close-btn" onClick={() => setShowAnalyzeModal(false)}>
                Close
              </button>
            </div>

            <div className="bm-analyze-grid">
              <article className="glass card">
                <h3 className="bm-analyze-subtitle">Token Snapshot</h3>
                {report.scam_warning ? (
                  <div style={{
                    background: report.scam_warning.severity === 'high' ? 'rgba(239,68,68,0.12)' : 'rgba(245,158,11,0.10)',
                    border: `1.5px solid ${report.scam_warning.severity === 'high' ? '#ef4444' : '#f59e0b'}`,
                    borderRadius: '10px',
                    padding: '14px 16px',
                    marginBottom: '12px',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '8px',
                  }}>
                    <strong style={{ color: report.scam_warning.severity === 'high' ? '#f87171' : '#fbbf24', fontSize: '0.9rem' }}>
                      {report.scam_warning.severity === 'high' ? '🚫 This token is likely INCORRECT / FAKE!' : '⚠️ Caution — Verify this token'}
                    </strong>
                    <p style={{ margin: 0, fontSize: '0.8rem', color: '#aaa', lineHeight: 1.5 }}>
                      {report.scam_warning.reasons.map((r, i) => (
                        <span key={i} style={{ display: 'block' }}>• {r}</span>
                      ))}
                    </p>
                    {report.scam_warning.severity === 'high' && (
                      <>
                        <p style={{ margin: 0, fontSize: '0.82rem', color: '#ccc' }}>
                          This is likely NOT the token you were looking for. Use the official <strong>Contract Address (CA)</strong> for accurate results.
                        </p>
                        <button
                          className="btn-primary"
                          style={{ alignSelf: 'flex-start', padding: '6px 14px', fontSize: '0.8rem' }}
                          onClick={() => {
                            setTokenSearchMode?.('address');
                            setShowAnalyzeModal(false);
                          }}
                        >
                          🔍 Search with Contract Address
                        </button>
                      </>
                    )}
                  </div>
                ) : null}
                <div className="report-grid">
                  <div className="metric-box">
                    <span>Token Name</span>
                    <strong>{String(report.name || report.token || '-')}</strong>
                  </div>
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
                  <div className="metric-box">
                    <span>Chain</span>
                    <strong>{String(chain || '-')}</strong>
                  </div>
                </div>

                <div className="trade-actions">
                  <button
                    className="btn-trade"
                    style={{ width: '100%', padding: '8px 12px' }}
                    onClick={() => {
                      const ca = report.address || report.ca || token;
                      const url = getAveProUrl(ca, chain);
                      if (url) window.open(url, '_blank');
                    }}
                  >
                    Trade on Ave
                  </button>
                  <button
                    className="btn-trade"
                    style={{ width: '100%', padding: '8px 12px' }}
                    onClick={() => {
                      const ca = report.address || report.ca || '';
                      if (!isLikelyAddress(ca)) {
                        setStatus?.('Bubble Map requires a valid contract address.');
                        return;
                      }
                      window.open(getBubbleMapUrl(ca, chain), '_blank');
                    }}
                  >
                    Bubble Map
                  </button>
                </div>
              </article>

              <article className="glass card score-card bm-score-panel">
                <h3 className="bm-analyze-subtitle">Risk-Adjusted Score</h3>
                <div className={`score-orb ${scoreTone(report.score?.risk_adjusted || 0)}`}>
                  {report.score?.risk_adjusted || 0}
                </div>
                <p className="phase-line">Market phase: {String(report.score?.market_phase || '-').toUpperCase()}</p>
                <div className="signal-list">
                  <div><span>Volume Divergence</span><b>{report.signals?.volume_divergence ?? '-'}</b></div>
                  <div><span>Volume Momentum</span><b>{report.signals?.volume_momentum ?? '-'}</b></div>
                  <div><span>TVL Stability</span><b>{report.signals?.tvl_stability ?? '-'}</b></div>
                  <div><span>Holder Distribution</span><b>{report.signals?.holder_distribution ?? '-'}</b></div>
                  <div><span>Whale Score</span><b>{report.signals?.whale_score ?? '-'}</b></div>
                </div>
              </article>
            </div>

            <div className="bm-analyze-actions">
              <button className="btn-primary" onClick={onEnterDashboard}>
                Open In Dashboard
              </button>
            </div>
          </div>
        </div>
      ) : null}

    </div>
  );
}

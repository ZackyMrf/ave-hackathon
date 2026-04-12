import { Fragment, useState } from 'react';
import { LightChartViewer } from '../../TradingViewChart';
import Sparkline from '../Sparkline';
import { CHAINS } from '../../constants/monitoring';
import {
  buildTrendCacheKey,
  formatMoney,
  getBubbleMapUrl,
  getIntervalMinutes,
  isLikelyAddress,
  scoreTone,
} from '../../utils/monitoring';

export default function DashboardSection({
  token,
  setToken,
  tokenSearchMode,
  setTokenSearchMode,
  chain,
  setChain,
  analyzeToken,
  report,
  setStatus,
  category,
  setCategory,
  sweepChain,
  setSweepChain,
  top,
  setTop,
  sweepLoading,
  runSweep,
  signalKpis,
  sweep,
  trendCache,
  openTokenChart,
  selectedRowKey,
  timeframe,
  reloadChartForTimeframe,
  showMA,
  setShowMA,
  showEMA,
  setShowEMA,
  chartLoading,
  chartError,
  chartData,
  selectedToken,
  selectedChartChain,
  selectedPairAddress,
  selectedTokenAddress,
  setSelectedPairAddress,
  cachePairAddress,
  createAlert,
  addToWatchlist,
  toggleWatchlist,
  isTokenInWatchlist,
}) {
  const [showQuickAlert, setShowQuickAlert] = useState(false);
  const [quickAlertSaving, setQuickAlertSaving] = useState(false);
  const [quickAlert, setQuickAlert] = useState({
    alert_type: 'price',
    condition: 'above',
    threshold: '',
  });
  const [rowQuickAlertTarget, setRowQuickAlertTarget] = useState(null);
  const [rowQuickAlertSaving, setRowQuickAlertSaving] = useState(false);
  const [rowQuickAlert, setRowQuickAlert] = useState({
    alert_type: 'price',
    condition: 'above',
    threshold: '',
  });
  const [rowActionMenuKey, setRowActionMenuKey] = useState('');

  function openQuickAlert() {
    const fallbackThreshold = Number(report?.price || 0);
    const defaultThreshold = fallbackThreshold > 0 ? fallbackThreshold.toFixed(6) : '1';
    setQuickAlert({
      alert_type: 'price',
      condition: 'above',
      threshold: defaultThreshold,
    });
    setShowQuickAlert(true);
  }

  async function handleQuickAlertCreate() {
    if (!report?.token || !chain || !createAlert) return;

    const thresholdNum = Number.parseFloat(String(quickAlert.threshold || '').trim());
    if (!Number.isFinite(thresholdNum)) {
      setStatus('Threshold alert tidak valid.');
      return;
    }

    setQuickAlertSaving(true);
    try {
      const ok = await createAlert({
        token: String(report.token || token).toUpperCase(),
        chain: String(chain),
        alert_type: quickAlert.alert_type,
        condition: quickAlert.condition,
        threshold: thresholdNum,
      });

      if (ok) {
        setShowQuickAlert(false);
      }
    } finally {
      setQuickAlertSaving(false);
    }
  }

  function openSweepRowAlert(e, item, currentPrice, rowKey) {
    e.stopPropagation();

    const tokenSymbol = String(item?.token || '').trim();
    if (!tokenSymbol) {
      setStatus('Token tidak valid untuk membuat alert.');
      return;
    }

    const basePrice = Number(currentPrice || item?.price || 0);
    const threshold = basePrice > 0 ? Number((basePrice * 1.03).toFixed(8)) : 1;
    setRowQuickAlertTarget({
      rowKey,
      token: tokenSymbol.toUpperCase(),
      chain: String(sweepChain || chain || 'solana'),
    });
    setRowQuickAlert({
      alert_type: 'price',
      condition: 'above',
      threshold: String(threshold),
    });
  }

  async function handleSweepRowAlertCreate() {
    if (!createAlert || !rowQuickAlertTarget?.token || !rowQuickAlertTarget?.chain) return;

    const thresholdNum = Number.parseFloat(String(rowQuickAlert.threshold || '').trim());
    if (!Number.isFinite(thresholdNum)) {
      setStatus('Threshold alert tidak valid.');
      return;
    }

    setRowQuickAlertSaving(true);
    try {
      const ok = await createAlert({
        token: rowQuickAlertTarget.token,
        chain: rowQuickAlertTarget.chain,
        alert_type: rowQuickAlert.alert_type,
        condition: rowQuickAlert.condition,
        threshold: thresholdNum,
      });

      if (ok) {
        setRowQuickAlertTarget(null);
      }
    } finally {
      setRowQuickAlertSaving(false);
    }
  }

  function toggleRowActionMenu(e, rowKey) {
    e.stopPropagation();
    setRowActionMenuKey((prev) => (prev === rowKey ? '' : rowKey));
  }

  function onRowMenuAddAlert(e, item, currentPrice, rowKey) {
    openSweepRowAlert(e, item, currentPrice, rowKey);
    setRowActionMenuKey('');
  }

  function onRowMenuToggleWatchlist(e, item) {
    e.stopPropagation();
    if (!toggleWatchlist && !addToWatchlist) return;

    const payload = {
      token: String(item?.token || '').toUpperCase(),
      chain: String(sweepChain || chain || 'solana'),
      address: String(item?.address || item?.ca || ''),
    };

    if (toggleWatchlist) {
      toggleWatchlist(payload);
    } else {
      addToWatchlist(payload);
    }

    setRowActionMenuKey('');
  }

  return (
    <>
      <section className="hero-grid">
        <article className="glass card analyze-card">
          <h2>Single Token Probe</h2>
          <div className="control-grid">
            <label>
              Token / Contract Address
              <input
                value={token}
                onChange={(e) => setToken(e.target.value)}
                placeholder={tokenSearchMode === 'address' ? 'paste contract address' : 'jup'}
              />
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
          <div className="engine-actions">
            <button
              className={`tv-chip ${tokenSearchMode === 'symbol' ? 'active' : ''}`}
              onClick={() => setTokenSearchMode('symbol')}
            >
              Symbol
            </button>
            <button
              className={`tv-chip ${tokenSearchMode === 'address' ? 'active' : ''}`}
              onClick={() => setTokenSearchMode('address')}
            >
              Contract Address
            </button>
            <button onClick={analyzeToken} className="btn-primary">
              {tokenSearchMode === 'address' ? 'Analyze by Address' : 'Analyze by Symbol'}
            </button>
          </div>
          <p className="helper">
            Mode {tokenSearchMode === 'address' ? 'Contract Address' : 'Symbol'} aktif.
            {tokenSearchMode === 'address'
              ? ' Gunakan CA asli agar tidak ketukar token palsu.'
              : ' Gunakan Symbol untuk pencarian cepat.'}
          </p>

          {report ? (
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
              <div style={{ gridColumn: '1 / -1', marginTop: '8px' }}>
                <div className="trade-actions">
                  <button
                    className="btn-trade"
                    style={{ padding: '8px 12px' }}
                    onClick={() => {
                      const ca = report.address || report.ca || token;
                      window.open(`https://pro.ave.ai/token/${ca}-${chain}`, '_blank');
                    }}
                  >
                    🚀 Trade on Ave
                  </button>
                  <button
                    className="btn-trade"
                    style={{ padding: '8px 12px' }}
                    onClick={() => {
                      const ca = report.address || report.ca || '';
                      if (!isLikelyAddress(ca)) {
                        setStatus('Bubble Map butuh contract address yang valid.');
                        return;
                      }
                      window.open(getBubbleMapUrl(ca, chain), '_blank');
                    }}
                  >
                    🫧 Bubble Map
                  </button>
                  <button
                    className="btn-trade"
                    style={{ padding: '8px 12px' }}
                    onClick={openQuickAlert}
                  >
                    🔔 Add Alert
                  </button>
                </div>

                {showQuickAlert ? (
                  <div className="quick-alert-box">
                    <div className="quick-alert-grid">
                      <label>
                        Alert Type
                        <select
                          value={quickAlert.alert_type}
                          onChange={(e) => setQuickAlert((prev) => ({ ...prev, alert_type: e.target.value }))}
                          disabled={quickAlertSaving}
                        >
                          <option value="price">price</option>
                          <option value="risk">risk</option>
                          <option value="volume">volume</option>
                          <option value="whale">whale</option>
                          <option value="trend">trend</option>
                        </select>
                      </label>

                      <label>
                        Condition
                        <select
                          value={quickAlert.condition}
                          onChange={(e) => setQuickAlert((prev) => ({ ...prev, condition: e.target.value }))}
                          disabled={quickAlertSaving}
                        >
                          <option value="above">above</option>
                          <option value="below">below</option>
                          <option value="change">change</option>
                        </select>
                      </label>

                      <label>
                        Threshold
                        <input
                          type="number"
                          step="0.000001"
                          value={quickAlert.threshold}
                          onChange={(e) => setQuickAlert((prev) => ({ ...prev, threshold: e.target.value }))}
                          disabled={quickAlertSaving}
                        />
                      </label>
                    </div>

                    <div className="quick-alert-actions">
                      <button
                        className="btn-ghost"
                        onClick={() => setShowQuickAlert(false)}
                        disabled={quickAlertSaving}
                      >
                        Cancel
                      </button>
                      <button
                        className="btn-primary"
                        onClick={handleQuickAlertCreate}
                        disabled={quickAlertSaving}
                      >
                        {quickAlertSaving ? 'Saving...' : 'Create Alert'}
                      </button>
                    </div>
                  </div>
                ) : null}
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
              <p className="phase-line">Market phase: {String(report.score?.market_phase || '-').toUpperCase()}</p>
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
              <select value={category} onChange={(e) => setCategory(e.target.value)} disabled={sweepLoading}>
                <option value="trending">trending</option>
                <option value="meme">meme</option>
                <option value="defi">defi</option>
                <option value="gaming">gaming</option>
                <option value="ai">ai</option>
              </select>
            </label>
            <label>
              Sweep Network
              <select value={sweepChain} onChange={(e) => setSweepChain(e.target.value)} disabled={sweepLoading}>
                {CHAINS.map((c) => (
                  <option key={`sweep-${c}`} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Top
              <input
                value={top}
                onChange={(e) => {
                  const next = Math.min(20, Math.max(1, Number.parseInt(e.target.value || '1', 10) || 1));
                  setTop(next);
                }}
                min={1}
                max={20}
                type="number"
                disabled={sweepLoading}
              />
            </label>
          </div>
          <button onClick={runSweep} className="btn-ghost" disabled={sweepLoading}>{sweepLoading ? 'Scanning...' : 'Run Sweep'}</button>
          <p className="helper">Sweep menggunakan network sendiri + kategori wajib, terpisah dari Single Token Probe.</p>
        </article>
      </section>

      <section className="glass table-section">
        <div className="table-header">
          <h2>Top Signal Candidates</h2>
          <span>{sweep.length} assets</span>
        </div>
        <p className="helper">
          Signal Engine: 1) Analyze token, 2) Sweep category/network, 3) rank by Risk-Adjusted score,
          4) validasi tren dari chart + whale context sebelum eksekusi.
        </p>
        <div className="engine-kpis">
          <div className="kpi-box">
            <span>Analyzed</span>
            <strong>{signalKpis.total}</strong>
          </div>
          <div className="kpi-box">
            <span>High Conviction</span>
            <strong>{signalKpis.highConviction}</strong>
          </div>
          <div className="kpi-box">
            <span>Trend Synced</span>
            <strong>{signalKpis.withTrend}</strong>
          </div>
          <div className="kpi-box">
            <span>Last Risk</span>
            <strong>{signalKpis.latestRisk}</strong>
          </div>
        </div>
        <div className="engine-actions">
          <button className="tv-chip" onClick={analyzeToken}>Run Analyze</button>
          <button className="tv-chip" onClick={runSweep}>Run Sweep</button>
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
                  const trendKey = buildTrendCacheKey(item, sweepChain);
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
                  const rowChain = String(sweepChain || chain || 'solana');
                  const rowToken = String(item?.token || '').toUpperCase();
                  const rowWatchlisted = Boolean(
                    isTokenInWatchlist?.({ token: rowToken, chain: rowChain })
                  );
                  return (
                    <Fragment key={rowKey}>
                      <tr
                        className="clickable-row"
                        onClick={() => {
                          setRowActionMenuKey('');
                          openTokenChart(item, rowKey);
                        }}
                      >
                        <td>{idx + 1}</td>
                        <td>
                          <span className="token-link">{String(item.token || '-').toUpperCase()}</span>
                        </td>
                        <td>{formatMoney(displayPrice)}</td>
                        <td className={displayChange24h >= 0 ? 'up' : 'down'}>
                          {displayChange24h.toFixed(2)}%
                        </td>
                        <td>{item.score?.risk_adjusted ?? '-'}</td>
                        <td>
                          <span className={`alert-dot ${scoreTone(item.score?.risk_adjusted || 0)}`} />
                          {String(item.score?.alert_level || '-').toUpperCase()}
                        </td>
                        <td><Sparkline points={trendPoints} /></td>
                        <td>
                          <div className="trade-actions">
                            <button
                              className="btn-trade"
                              onClick={(e) => {
                                e.stopPropagation();
                                const ca = item.address || item.ca || item.token;
                                const url = `https://pro.ave.ai/token/${ca}-${sweepChain}`;
                                window.open(url, '_blank');
                              }}
                            >
                              🚀 Trade
                            </button>
                            <button
                              className="btn-trade"
                              onClick={(e) => {
                                e.stopPropagation();
                                const ca = item.address || item.ca || '';
                                if (!isLikelyAddress(ca)) {
                                  setStatus(`Bubble Map tidak tersedia untuk ${String(item.token || '').toUpperCase()} karena address tidak valid.`);
                                  return;
                                }
                                window.open(getBubbleMapUrl(ca, sweepChain), '_blank');
                              }}
                            >
                              🫧 Bubble
                            </button>

                            <div className="row-action-wrap">
                              <button
                                className="row-action-trigger"
                                onClick={(e) => toggleRowActionMenu(e, rowKey)}
                                title="More actions"
                              >
                                ⋯
                              </button>

                              {rowActionMenuKey === rowKey ? (
                                <div className="row-action-menu" onClick={(e) => e.stopPropagation()}>
                                  <button
                                    className="row-action-item"
                                    onClick={(e) => onRowMenuAddAlert(e, item, displayPrice, rowKey)}
                                  >
                                    🔔 Add Alert
                                  </button>
                                  <button
                                    className="row-action-item"
                                    onClick={(e) => onRowMenuToggleWatchlist(e, item)}
                                  >
                                    {rowWatchlisted ? '✖ Unwatchlist' : '⭐ Add Watchlist'}
                                  </button>
                                </div>
                              ) : null}
                            </div>
                          </div>
                        </td>
                      </tr>

                      {rowQuickAlertTarget?.rowKey === rowKey ? (
                        <tr className="chart-inline-row">
                          <td colSpan={8} className="chart-inline-cell">
                            <div className="quick-alert-box">
                              <div className="quick-alert-grid">
                                <label>
                                  Alert Type
                                  <select
                                    value={rowQuickAlert.alert_type}
                                    onChange={(e) => setRowQuickAlert((prev) => ({ ...prev, alert_type: e.target.value }))}
                                    disabled={rowQuickAlertSaving}
                                  >
                                    <option value="price">price</option>
                                    <option value="risk">risk</option>
                                    <option value="volume">volume</option>
                                    <option value="whale">whale</option>
                                    <option value="trend">trend</option>
                                  </select>
                                </label>

                                <label>
                                  Condition
                                  <select
                                    value={rowQuickAlert.condition}
                                    onChange={(e) => setRowQuickAlert((prev) => ({ ...prev, condition: e.target.value }))}
                                    disabled={rowQuickAlertSaving}
                                  >
                                    <option value="above">above</option>
                                    <option value="below">below</option>
                                    <option value="change">change</option>
                                  </select>
                                </label>

                                <label>
                                  Threshold
                                  <input
                                    type="number"
                                    step="0.000001"
                                    value={rowQuickAlert.threshold}
                                    onChange={(e) => setRowQuickAlert((prev) => ({ ...prev, threshold: e.target.value }))}
                                    disabled={rowQuickAlertSaving}
                                  />
                                </label>
                              </div>

                              <div className="quick-alert-actions">
                                <button
                                  className="btn-ghost"
                                  onClick={() => setRowQuickAlertTarget(null)}
                                  disabled={rowQuickAlertSaving}
                                >
                                  Cancel
                                </button>
                                <button
                                  className="btn-primary"
                                  onClick={handleSweepRowAlertCreate}
                                  disabled={rowQuickAlertSaving}
                                >
                                  {rowQuickAlertSaving ? 'Saving...' : 'Create Alert'}
                                </button>
                              </div>
                            </div>
                          </td>
                        </tr>
                      ) : null}

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
                                  chain={selectedChartChain}
                                  pairAddress={selectedPairAddress}
                                  tokenAddress={selectedTokenAddress}
                                  intervalMinutes={getIntervalMinutes(timeframe)}
                                  chartType="candlestick"
                                  showMA={showMA}
                                  showEMA={showEMA}
                                  onPairDiscovered={(pair) => {
                                    if (!pair) return;
                                    setSelectedPairAddress((prev) => (prev === pair ? prev : pair));
                                    cachePairAddress(selectedTokenAddress, selectedChartChain, pair);
                                  }}
                                />
                              ) : null}
                            </div>

                            {chartData.length ? (
                              <div className="chart-stats">
                                <span>{String(selectedToken || '-').toUpperCase()} · {selectedChartChain}</span>
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
    </>
  );
}

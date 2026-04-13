import { CHAINS } from '../../constants/monitoring';
import { formatSnapshotTime, getAddressExplorerUrl, getArkhamAddressUrl, shortAddress } from '../../utils/monitoring';

export default function WhaleFeedSection({
  whaleFeedRows,
  whaleToken,
  setWhaleToken,
  whaleChain,
  setWhaleChain,
  runWhaleFeedAnalysis,
  whaleLoading,
  whaleError,
  selectedWhaleWallet,
  setSelectedWhaleWallet,
  whaleReport,
  selectedWhaleTimeline,
}) {
  return (
    <section className="glass mini-section">
      <div className="table-header">
        <h2>Whale Feed</h2>
        <span>{whaleFeedRows.length} rows</span>
      </div>
      <p className="helper">
        Enter token and chain, then the system will fetch whale movements for that token.
      </p>

      <div className="engine-rule-grid">
        <label>
          Token
          <input
            value={whaleToken}
            onChange={(e) => setWhaleToken(e.target.value)}
            placeholder="contoh: jup"
          />
        </label>
        <label>
          Chain
          <select value={whaleChain} onChange={(e) => setWhaleChain(e.target.value)}>
            {CHAINS.map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
        </label>
        <div className="engine-actions">
          <button className="tv-chip" onClick={runWhaleFeedAnalysis} disabled={whaleLoading}>
            {whaleLoading ? 'Analyzing...' : 'Analyze Whale Movement'}
          </button>
        </div>
      </div>

      {whaleError ? <div className="error-banner">{whaleError}</div> : null}

      {whaleFeedRows.length ? (
        <>
          <div className="table-wrap">
            <table className="mobile-card-table">
              <thead>
                <tr>
                  <th>Token</th>
                  <th>Wallet</th>
                  <th>Share</th>
                  <th>24h</th>
                  <th>Status</th>
                  <th>Track</th>
                </tr>
              </thead>
              <tbody>
                {whaleFeedRows.map((row) => {
                  const active =
                    String(row.address || '').toLowerCase() === String(selectedWhaleWallet || '').toLowerCase();
                  return (
                    <tr key={row.id} className={active ? 'selected-row' : ''}>
                      <td data-label="Token">{String(whaleReport?.token || whaleToken).toUpperCase()}</td>
                      <td data-label="Wallet">{shortAddress(row.address)}</td>
                      <td data-label="Share">{row.ratio.toFixed(2)}%</td>
                      <td data-label="24h" className={row.delta >= 0 ? 'up' : 'down'}>{row.delta.toFixed(2)}%</td>
                      <td data-label="Status">{row.isNew ? 'new whale' : 'tracked'}</td>
                      <td data-label="Track">
                        <div className="wallet-track-actions">
                          <button
                            className={`tv-chip ${active ? 'active' : ''}`}
                            onClick={() => setSelectedWhaleWallet(String(row.address || '').trim())}
                            disabled={!row.address}
                          >
                            Track
                          </button>
                          <button
                            className="tv-chip"
                            onClick={() => window.open(getArkhamAddressUrl(row.address), '_blank')}
                            disabled={!row.address}
                          >
                            Arkham
                          </button>
                          <button
                            className="tv-chip"
                            onClick={() => window.open(getAddressExplorerUrl(whaleChain, row.address), '_blank')}
                            disabled={!row.address}
                          >
                            Explorer
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {selectedWhaleWallet ? (
            <div className="wallet-tracker-panel">
              <div className="table-header">
                <h2>Address Tracker</h2>
                <span>{shortAddress(selectedWhaleWallet)} · {selectedWhaleTimeline.length} snapshots</span>
              </div>
              <p className="helper">
                This timeline stores the trace of wallet movements from every time you click Analyze Whale Movement.
              </p>
              <div className="engine-actions">
                <button
                  className="tv-chip"
                  onClick={() => window.open(getArkhamAddressUrl(selectedWhaleWallet), '_blank')}
                >
                  Open Arkham Profile
                </button>
                <button
                  className="tv-chip"
                  onClick={() => window.open(getAddressExplorerUrl(whaleChain, selectedWhaleWallet), '_blank')}
                >
                  Open Chain Explorer
                </button>
                <button className="tv-chip" onClick={() => setSelectedWhaleWallet('')}>Clear Tracker</button>
              </div>

              {selectedWhaleTimeline.length ? (
                <div className="table-wrap">
                  <table className="mobile-card-table">
                    <thead>
                      <tr>
                        <th>Time</th>
                        <th>Token</th>
                        <th>Chain</th>
                        <th>Share</th>
                        <th>24h</th>
                        <th>Move</th>
                      </tr>
                    </thead>
                    <tbody>
                      {selectedWhaleTimeline.map((row, idx) => {
                        const prev = selectedWhaleTimeline[idx + 1];
                        const move = prev ? Number(row.ratio || 0) - Number(prev.ratio || 0) : 0;
                        return (
                          <tr key={`track-${idx}`}>
                            <td data-label="Time">{formatSnapshotTime(row.capturedAt)}</td>
                            <td data-label="Token">{String(row.token || '-').toUpperCase()}</td>
                            <td data-label="Chain">{String(row.chain || '-')}</td>
                            <td data-label="Share">{Number(row.ratio || 0).toFixed(2)}%</td>
                            <td data-label="24h" className={Number(row.delta || 0) >= 0 ? 'up' : 'down'}>{Number(row.delta || 0).toFixed(2)}%</td>
                            <td data-label="Move" className={move >= 0 ? 'up' : 'down'}>{move >= 0 ? '+' : ''}{move.toFixed(2)}%</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="empty-note">No history for this wallet yet. Run Analyze again to add a snapshot.</p>
              )}
            </div>
          ) : null}
        </>
      ) : (
        <>
          <p className="empty-note">No whale data yet. Enter token + chain then click Analyze Whale Movement.</p>
        </>
      )}
    </section>
  );
}

import { SIGNAL_PRESETS } from '../../constants/monitoring';

export default function SignalEngineSection({
  signalEngineRows,
  enginePreset,
  applySignalPreset,
  engineMinRisk,
  setEngineMinRisk,
  engineMinWhale,
  setEngineMinWhale,
  engineRequireUptrend,
  setEngineRequireUptrend,
  setEnginePreset,
  runSweep,
  handleNavigate,
}) {
  return (
    <section className="glass table-section">
      <div className="table-header">
        <h2>Signal Engine Lab</h2>
        <span>{signalEngineRows.length} matched</span>
      </div>
      <p className="helper">
        Di menu ini kita fokus ke rule-based screening, bukan list top signal mentah. Atur rule lalu lihat token yang lolos.
      </p>

      <div className="engine-actions">
        {Object.keys(SIGNAL_PRESETS).map((name) => (
          <button
            key={name}
            className={`tv-chip ${enginePreset === name ? 'active' : ''}`}
            onClick={() => applySignalPreset(name)}
          >
            {name}
          </button>
        ))}
      </div>

      <div className="engine-rule-grid">
        <label>
          Min Risk-Adjusted
          <input
            type="number"
            min={0}
            max={100}
            value={engineMinRisk}
            onChange={(e) => {
              setEnginePreset('Custom');
              setEngineMinRisk(Number(e.target.value || 0));
            }}
          />
        </label>
        <label>
          Min Whale Score
          <input
            type="number"
            min={0}
            max={40}
            value={engineMinWhale}
            onChange={(e) => {
              setEnginePreset('Custom');
              setEngineMinWhale(Number(e.target.value || 0));
            }}
          />
        </label>
        <label className="toggle-line">
          <input
            type="checkbox"
            checked={engineRequireUptrend}
            onChange={(e) => {
              setEnginePreset('Custom');
              setEngineRequireUptrend(e.target.checked);
            }}
          />
          Uptrend only (24h &gt; 0)
        </label>
      </div>

      <div className="engine-actions">
        <button className="tv-chip" onClick={runSweep}>Refresh Source Data</button>
        <button className="tv-chip" onClick={() => handleNavigate('Dashboard')}>Back to Dashboard</button>
      </div>

      {signalEngineRows.length ? (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>#</th>
                <th>Token</th>
                <th>Risk Adj</th>
                <th>Whale</th>
                <th>Trend 24h</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {signalEngineRows.map((row, idx) => (
                <tr key={row.id}>
                  <td>{idx + 1}</td>
                  <td>{row.token}</td>
                  <td>{row.riskAdj.toFixed(0)}</td>
                  <td>{row.whaleScore.toFixed(0)}</td>
                  <td className={row.trend >= 0 ? 'up' : 'down'}>{row.trend.toFixed(2)}%</td>
                  <td>{row.action}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="empty-note">Belum ada token yang lolos rule saat ini. Coba turunkan threshold atau jalankan Sweep dulu.</p>
      )}
    </section>
  );
}

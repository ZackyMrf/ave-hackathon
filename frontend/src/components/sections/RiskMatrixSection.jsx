export default function RiskMatrixSection({ riskRows, riskSummary }) {
  return (
    <section className="glass mini-section">
      <div className="table-header">
        <h2>Risk Matrix</h2>
        <span>{riskRows.length} assets</span>
      </div>
      <div className="risk-summary-grid">
        <div className="kpi-box">
          <span>High</span>
          <strong>{riskSummary.high}</strong>
        </div>
        <div className="kpi-box">
          <span>Elevated</span>
          <strong>{riskSummary.elevated}</strong>
        </div>
        <div className="kpi-box">
          <span>Watch</span>
          <strong>{riskSummary.watch}</strong>
        </div>
        <div className="kpi-box">
          <span>Low</span>
          <strong>{riskSummary.low}</strong>
        </div>
      </div>

      {riskRows.length ? (
        <div className="table-wrap">
          <table className="mobile-card-table">
            <thead>
              <tr>
                <th>Token</th>
                <th>Risk Adj</th>
                <th>Tier</th>
                <th>Whale</th>
                <th>Vol Div</th>
              </tr>
            </thead>
            <tbody>
              {riskRows.map((row) => (
                <tr key={row.id}>
                  <td data-label="Token">{row.token}</td>
                  <td data-label="Risk Adj">{row.riskAdj}</td>
                  <td data-label="Tier">{row.tier.toUpperCase()}</td>
                  <td data-label="Whale">{row.whaleScore.toFixed(0)}</td>
                  <td data-label="Vol Div">{row.volDiv.toFixed(0)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="empty-note">No risk matrix data yet. Run Analyze or Sweep.</p>
      )}
    </section>
  );
}

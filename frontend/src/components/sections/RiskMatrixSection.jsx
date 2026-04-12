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
          <table>
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
                  <td>{row.token}</td>
                  <td>{row.riskAdj}</td>
                  <td>{row.tier.toUpperCase()}</td>
                  <td>{row.whaleScore.toFixed(0)}</td>
                  <td>{row.volDiv.toFixed(0)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="empty-note">Belum ada data risk matrix. Jalankan Analyze atau Sweep.</p>
      )}
    </section>
  );
}

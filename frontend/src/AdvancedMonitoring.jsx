// Advanced Monitoring Features Component
// Handles alerts, watchlist sync, and real-time monitoring

export function AlertsPanel({ activeTab, setActiveTab, alerts, onCreateAlert, onDeleteAlert, onToggleAlert, token, chain }) {
  const [formData, setFormData] = useState({
    alert_type: 'price',
    condition: 'above',
    threshold: 100,
  });

  function handleCreateAlert() {
    if (!token || !chain || !formData.threshold) {
      alert('Please fill all fields');
      return;
    }

    onCreateAlert({
      token,
      chain,
      alert_type: formData.alert_type,
      condition: formData.condition,
      threshold: parseFloat(formData.threshold),
    });

    setFormData({ alert_type: 'price', condition: 'above', threshold: 100 });
  }

  return (
    <div className="alerts-panel">
      <div className="alerts-header">
        <h2>⚠️ Advanced Alerts</h2>
        <div className="alerts-tabs">
          <button
            className={`tab-btn ${activeTab === 'create' ? 'active' : ''}`}
            onClick={() => setActiveTab('create')}
          >
            Create
          </button>
          <button
            className={`tab-btn ${activeTab === 'list' ? 'active' : ''}`}
            onClick={() => setActiveTab('list')}
          >
            Active ({alerts.length})
          </button>
        </div>
      </div>

      {activeTab === 'create' ? (
        <div className="alert-form">
          <div className="form-group">
            <label>Token</label>
            <input type="text" disabled value={token || 'Select a token first'} />
          </div>

          <div className="form-group">
            <label>Alert Type</label>
            <select value={formData.alert_type} onChange={(e) => setFormData({ ...formData, alert_type: e.target.value })}>
              <option value="price">💰 Price Alert</option>
              <option value="risk">⚠️ Risk Score</option>
              <option value="volume">📊 Volume Spike</option>
              <option value="whale">🐋 Whale Movement</option>
              <option value="trend">📈 Trend Change</option>
            </select>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label>Condition</label>
              <select value={formData.condition} onChange={(e) => setFormData({ ...formData, condition: e.target.value })}>
                <option value="above">Above</option>
                <option value="below">Below</option>
                <option value="change">Change %</option>
              </select>
            </div>

            <div className="form-group">
              <label>Threshold</label>
              <input
                type="number"
                step="0.01"
                value={formData.threshold}
                onChange={(e) => setFormData({ ...formData, threshold: e.target.value })}
              />
            </div>
          </div>

          <button className="action-btn primary" onClick={handleCreateAlert}>
            Create Alert
          </button>
        </div>
      ) : (
        <div className="alerts-list">
          {alerts.length === 0 ? (
            <p className="empty-note">No alerts for this token</p>
          ) : (
            alerts.map((alert) => (
              <div key={alert.id} className={`alert-item ${alert.enabled ? 'enabled' : 'disabled'}`}>
                <div className="alert-info">
                  <strong>{alert.alert_type.toUpperCase()}</strong>
                  <span className="alert-condition">
                    {alert.condition} {alert.threshold}
                  </span>
                  <span className="alert-time">{new Date(alert.created_at).toLocaleDateString()}</span>
                </div>

                <div className="alert-actions">
                  <button className="icon-btn" onClick={() => onToggleAlert(alert.id, !alert.enabled)} title="Toggle">
                    {alert.enabled ? '✓' : 'ⅹ'}
                  </button>
                  <button className="icon-btn delete" onClick={() => onDeleteAlert(alert.id)} title="Delete">
                    🗑️
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}

export function MonitoringStats({ stats }) {
  return (
    <div className="monitoring-stats">
      <div className="stat-card">
        <span className="stat-label">Total Alerts</span>
        <span className="stat-value">{stats.total || 0}</span>
      </div>
      <div className="stat-card">
        <span className="stat-label">Active</span>
        <span className="stat-value highlight">{stats.enabled || 0}</span>
      </div>
      <div className="stat-card">
        <span className="stat-label">Monitored Tokens</span>
        <span className="stat-value">{stats.monitored_tokens || 0}</span>
      </div>
      <div className="stat-card">
        <span className="stat-label">Price | Risk | Volume</span>
        <span className="stat-value mini">
          {stats.by_type?.price || 0} | {stats.by_type?.risk || 0} | {stats.by_type?.volume || 0}
        </span>
      </div>
    </div>
  );
}

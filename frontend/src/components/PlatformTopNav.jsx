export default function PlatformTopNav({
  activeItem,
  sectionItems = [],
  onSelect,
  onGoHome,
  rightMeta = [],
  secondaryActionLabel,
  onSecondaryAction,
  primaryActionLabel,
  onPrimaryAction,
  primaryConnected = false,
  primaryAvatarUrl = '',
  primaryAvatarFallback = 'TG',
  primaryAvatarTitle = 'Connected Telegram',
  primaryMenuOpen = false,
  onPrimaryToggleMenu,
  onPrimaryDisconnect,
  primaryAlerts = [],
  primaryAlertsLoading = false,
  primaryWatchlist = [],
  onPrimaryDeleteAlert,
  onPrimaryDeleteWatchlist,
}) {
  return (
    <header className="platform-nav-wrap">
      <nav className="platform-nav">
        <button className="platform-logo" onClick={onGoHome}>
          AVETRACE
        </button>

        <div className="platform-links" role="tablist" aria-label="primary navigation">
          {sectionItems.map((item) => (
            <button
              key={item.key}
              className={`platform-link ${activeItem === item.key ? 'active' : ''}`}
              onClick={() => onSelect?.(item.key)}
              role="tab"
              aria-selected={activeItem === item.key}
            >
              {item.label}
            </button>
          ))}
        </div>

        <div className="platform-nav-right">
          {rightMeta.map((text) => (
            <button key={text} className="platform-meta-btn">
              {text}
            </button>
          ))}

          {secondaryActionLabel ? (
            <button className="platform-cta secondary" onClick={onSecondaryAction}>
              {secondaryActionLabel}
            </button>
          ) : null}

          {primaryConnected ? (
            <div className="platform-primary-profile-wrap">
              <button
                className="platform-primary-avatar-btn"
                onClick={onPrimaryToggleMenu}
                title={primaryAvatarTitle}
              >
                {primaryAvatarUrl ? (
                  <img src={primaryAvatarUrl} alt="Telegram profile" className="platform-primary-avatar-img" />
                ) : (
                  <span className="platform-primary-avatar-fallback">{String(primaryAvatarFallback || 'TG').slice(0, 2).toUpperCase()}</span>
                )}
              </button>

              {primaryMenuOpen ? (
                <div className="platform-primary-menu">
                  <div className="platform-primary-menu-head">Web Alerts</div>

                  {primaryAlertsLoading ? (
                    <div className="platform-primary-menu-empty">Loading alerts...</div>
                  ) : primaryAlerts.length ? (
                    <div className="platform-primary-alert-list">
                      {primaryAlerts.map((alert) => (
                        <div key={alert.id} className="platform-primary-alert-item">
                          <div className="platform-primary-alert-main">
                            <strong>{String(alert.token || '-').toUpperCase()} · {String(alert.chain || '-')}</strong>
                            <span>
                              {String(alert.alert_type || '-')} {String(alert.condition || '-')} {String(alert.threshold ?? '-')}
                            </span>
                          </div>
                          <button
                            className="platform-primary-alert-delete"
                            onClick={() => onPrimaryDeleteAlert?.(alert.id)}
                            title="Delete Alert"
                          >
                            Delete
                          </button>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="platform-primary-menu-empty">No alerts yet</div>
                  )}

                  <div className="platform-primary-menu-subhead">Watchlist</div>
                  {primaryWatchlist.length ? (
                    <div className="platform-primary-watchlist">
                      {primaryWatchlist.map((item) => (
                        <div
                          key={`${String(item.token || '').toLowerCase()}::${String(item.chain || '').toLowerCase()}`}
                          className="platform-primary-watchlist-item"
                        >
                          <div className="platform-primary-watchlist-main">
                            <strong>{String(item.token || '-').toUpperCase()}</strong>
                            <span>{String(item.chain || '-')} · {String(item.category || 'general')}</span>
                          </div>
                          <button
                            className="platform-primary-watchlist-delete"
                            onClick={() => onPrimaryDeleteWatchlist?.(item)}
                            title="Remove from watchlist"
                          >
                            Delete
                          </button>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="platform-primary-menu-empty">Watchlist empty</div>
                  )}

                  <div className="platform-primary-menu-divider" />
                  <button className="platform-primary-menu-item" onClick={onPrimaryDisconnect}>
                    Disconnect Telegram
                  </button>
                </div>
              ) : null}
            </div>
          ) : primaryActionLabel ? (
            <button className="platform-cta primary" onClick={onPrimaryAction}>
              {primaryActionLabel}
            </button>
          ) : null}
        </div>
      </nav>
    </header>
  );
}

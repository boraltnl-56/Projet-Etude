/**
 * Layout — Sidebar + Header
 * Navigation complète au clavier (WCAG 2.1.1)
 * Rôles ARIA (navigation, banner)
 */
const NAV_ITEMS = [
  { id: 'dashboard',    icon: '🗺️',  label: 'Tableau de bord' },
  { id: 'environment',  icon: '🌿',  label: 'Environnement' },
  { id: 'crowdsourcing',icon: '📍',  label: 'Signalements' },
]

export default function Layout({ children, currentPage, onNavigate, apiStatus }) {
  const statusColor = apiStatus === 'online' ? 'var(--traffic-free)' : 'var(--traffic-jam)'
  const statusLabel = apiStatus === 'online' ? 'API en ligne' : 'API hors ligne'

  return (
    <div className="app-layout">
      {/* ── Header ── */}
      <header className="header" role="banner">
        <div className="header__logo" aria-label="UrbanFlow — Mobilité Urbaine">
          <span aria-hidden="true">🌆</span> UrbanFlow
        </div>
        <div className="header__status" role="status" aria-live="polite">
          <div className="status-badge">
            <span
              className="status-dot"
              style={{ background: statusColor, boxShadow: `0 0 6px ${statusColor}` }}
              aria-hidden="true"
            />
            <span>{statusLabel}</span>
          </div>
          <div className="status-badge">
            <span aria-hidden="true">🕐</span>
            <span suppressHydrationWarning>
              {new Date().toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })}
            </span>
          </div>
        </div>
      </header>

      {/* ── Sidebar ── */}
      <nav className="sidebar" role="navigation" aria-label="Navigation principale">
        <div style={{ padding: '0 1rem 1rem', fontSize: '0.7rem', fontWeight: 700,
          color: 'var(--color-text-muted)', textTransform: 'uppercase', letterSpacing: '0.1em' }}>
          Navigation
        </div>
        {NAV_ITEMS.map(item => (
          <button
            key={item.id}
            className={`nav-item ${currentPage === item.id ? 'active' : ''}`}
            onClick={() => onNavigate(item.id)}
            aria-current={currentPage === item.id ? 'page' : undefined}
            aria-label={item.label}
          >
            <span className="nav-item__icon" aria-hidden="true">{item.icon}</span>
            {item.label}
          </button>
        ))}

        {/* Infos stack */}
        <div style={{ marginTop: 'auto', padding: '1rem', borderTop: '1px solid var(--color-border)' }}>
          <div style={{ fontSize: '0.7rem', color: 'var(--color-text-muted)', lineHeight: 1.8 }}>
            <div>📊 PostgreSQL + PostGIS</div>
            <div>⚡ Redis Cache</div>
            <div>🤖 ARIMA + LSTM</div>
            <div>🌿 CodeCarbon actif</div>
          </div>
        </div>
      </nav>

      {/* ── Contenu ── */}
      {children}
    </div>
  )
}

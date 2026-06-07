/**
 * AlertsPanel — Panneau d'alertes trafic temps réel
 * aria-live="polite" pour les lecteurs d'écran (WCAG 4.1.3)
 */
const CONGESTION_LABELS = ['Fluide', 'Dense', 'Saturé', 'Bloqué', 'Paralysé']
const CONGESTION_ICONS  = ['🟢', '🟡', '🟠', '🔴', '🟣']

export default function AlertsPanel({ alerts = [], loading }) {
  if (loading) return (
    <div className="card" style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
      <div className="spinner" aria-hidden="true" />
      <span style={{ color: 'var(--color-text-secondary)', fontSize: '0.875rem' }}>
        Chargement des alertes…
      </span>
    </div>
  )

  return (
    <section
      className="card"
      aria-label={`${alerts.length} alerte(s) de trafic active(s)`}
    >
      <div className="card__header">
        <h2 className="card__title">🚨 Alertes trafic</h2>
        <span
          style={{
            background: alerts.length > 0 ? 'rgba(239,68,68,0.15)' : 'rgba(34,197,94,0.15)',
            color: alerts.length > 0 ? 'var(--traffic-jam)' : 'var(--traffic-free)',
            padding: '2px 10px',
            borderRadius: 'var(--radius-full)',
            fontSize: '0.75rem',
            fontWeight: 700,
          }}
          aria-label={`${alerts.length} alertes`}
        >
          {alerts.length}
        </span>
      </div>

      {/* aria-live pour annoncer les nouvelles alertes aux lecteurs d'écran */}
      <div
        role="log"
        aria-live="polite"
        aria-label="Flux des alertes de trafic"
        style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', maxHeight: '340px', overflowY: 'auto' }}
      >
        {alerts.length === 0 ? (
          <p style={{ color: 'var(--color-text-secondary)', fontSize: '0.875rem', textAlign: 'center', padding: '1rem' }}>
            ✅ Aucune alerte majeure en ce moment
          </p>
        ) : alerts.map((alert, i) => (
          <div
            key={alert.sensor_id + i}
            className={`alert-item ${alert.congestion_level >= 3 ? 'alert-item--critical' : 'alert-item--warning'}`}
            role="alert"
            aria-label={`Alerte ${CONGESTION_LABELS[alert.congestion_level]} sur ${alert.road_name}`}
          >
            <span className="alert-item__icon" aria-hidden="true">
              {CONGESTION_ICONS[alert.congestion_level] || '⚠️'}
            </span>
            <div style={{ flex: 1 }}>
              <div className="alert-item__title">
                {alert.road_name || alert.sensor_id}
              </div>
              <div className="alert-item__meta">
                <span className={`congestion-badge congestion-${alert.congestion_level}`}>
                  {CONGESTION_LABELS[alert.congestion_level]}
                </span>
                {' · '}
                {alert.average_speed_kmh?.toFixed(0)} km/h
                {' · '}
                {alert.vehicle_count} véh/h
              </div>
            </div>
          </div>
        ))}
      </div>
    </section>
  )
}

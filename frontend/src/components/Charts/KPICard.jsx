/**
 * KPICard — Carte indicateur clé
 * Accessible : role="article", aria-label complet
 */
export default function KPICard({ icon, label, value, unit, trend, color, description }) {
  const trendIcon  = trend > 0 ? '↑' : trend < 0 ? '↓' : '→'
  const trendColor = trend > 0 ? 'var(--traffic-jam)' : trend < 0 ? 'var(--traffic-free)' : 'var(--color-text-secondary)'

  return (
    <article
      className="card fade-in"
      role="article"
      aria-label={`${label} : ${value} ${unit || ''}`}
    >
      <div className="card__header">
        <span className="card__title">{label}</span>
        <span style={{ fontSize: '1.4rem' }} aria-hidden="true">{icon}</span>
      </div>
      <div className="card__value" style={{ color: color || 'var(--color-text-primary)' }}>
        {value}
        {unit && (
          <span style={{ fontSize: '0.9rem', fontWeight: 500, color: 'var(--color-text-secondary)', marginLeft: '4px' }}>
            {unit}
          </span>
        )}
      </div>
      {trend !== undefined && (
        <div style={{ marginTop: '6px', fontSize: '0.75rem', color: trendColor, fontWeight: 600 }}>
          <span aria-hidden="true">{trendIcon}</span>
          <span className="sr-only">{trend > 0 ? 'En hausse' : trend < 0 ? 'En baisse' : 'Stable'}</span>
          {' '}{description || ''}
        </div>
      )}
    </article>
  )
}

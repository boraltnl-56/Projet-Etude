/**
 * Environment — Page données environnementales
 * AQI, météo, historique 7 jours (Recharts)
 */
import { useState, useEffect } from 'react'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, AreaChart, Area } from 'recharts'
import { environmentAPI } from '../services/api'

const AQI_LABELS = ['', 'Bon', 'Modéré', 'Dégradé', 'Mauvais', 'Très mauvais']
const AQI_COLORS = ['', 'var(--aqi-good)', 'var(--aqi-moderate)', 'var(--aqi-unhealthy)', 'var(--aqi-bad)', 'var(--aqi-hazardous)']

export default function Environment({ envData, loading }) {
  const [history, setHistory] = useState([])
  const [histLoading, setHistLoading] = useState(true)

  useEffect(() => {
    environmentAPI.getAQIHistory()
      .then(data => setHistory(data.history || []))
      .catch(() => {})
      .finally(() => setHistLoading(false))
  }, [])

  const aqi = envData?.aqi || 0

  return (
    <div className="page fade-in">
      <div className="page-header">
        <h1 className="page-title">🌿 Données Environnementales</h1>
        <p className="page-subtitle">Qualité de l'air · Météo · Historique 7 jours — Source : OpenWeatherMap</p>
      </div>

      {/* ── KPIs environnement ── */}
      <div className="kpi-grid" role="region" aria-label="Indicateurs environnementaux">
        {/* AQI */}
        <article className="card" aria-label={`Indice qualité de l'air : ${AQI_LABELS[aqi]}`}>
          <div className="card__header">
            <span className="card__title">AQI Paris</span>
            <div className={`aqi-badge aqi-${aqi}`} aria-hidden="true">{aqi}</div>
          </div>
          <div className="card__value" style={{ color: AQI_COLORS[aqi] }}>
            {loading ? '…' : AQI_LABELS[aqi] || '--'}
          </div>
          <div style={{ marginTop:'6px', fontSize:'0.75rem', color:'var(--color-text-secondary)' }}>
            Indice européen 1–5
          </div>
        </article>

        <article className="card" aria-label={`PM2.5 : ${envData?.pm25} µg/m³`}>
          <div className="card__header"><span className="card__title">PM2.5</span><span aria-hidden="true">🫁</span></div>
          <div className="card__value">{loading ? '…' : envData?.pm25?.toFixed(1) ?? '--'}</div>
          <div style={{ fontSize:'0.75rem', color:'var(--color-text-secondary)' }}>µg/m³ · Seuil OMS : 15</div>
        </article>

        <article className="card" aria-label={`NO2 : ${envData?.no2} µg/m³`}>
          <div className="card__header"><span className="card__title">NO₂</span><span aria-hidden="true">🏭</span></div>
          <div className="card__value" style={{ color: (envData?.no2 || 0) > 100 ? 'var(--aqi-bad)' : 'inherit' }}>
            {loading ? '…' : envData?.no2?.toFixed(0) ?? '--'}
          </div>
          <div style={{ fontSize:'0.75rem', color:'var(--color-text-secondary)' }}>µg/m³ · Seuil : 40</div>
        </article>

        <article className="card" aria-label={`Température : ${envData?.temperature_celsius}°C`}>
          <div className="card__header"><span className="card__title">Température</span><span aria-hidden="true">🌡️</span></div>
          <div className="card__value">{loading ? '…' : envData?.temperature_celsius?.toFixed(1) ?? '--'}</div>
          <div style={{ fontSize:'0.75rem', color:'var(--color-text-secondary)' }}>
            °C · {envData?.weather_condition || '--'} · Vent {envData?.wind_speed_ms?.toFixed(1)} m/s
          </div>
        </article>

        <article className="card" aria-label={`Humidité : ${envData?.humidity_pct}%`}>
          <div className="card__header"><span className="card__title">Humidité</span><span aria-hidden="true">💧</span></div>
          <div className="card__value">{loading ? '…' : (envData?.humidity_pct ?? '--')}</div>
          <div style={{ fontSize:'0.75rem', color:'var(--color-text-secondary)' }}>%</div>
        </article>

        <article className="card" aria-label={`Précipitations : ${envData?.precipitation_mm} mm`}>
          <div className="card__header"><span className="card__title">Précipitations</span><span aria-hidden="true">🌧️</span></div>
          <div className="card__value">{loading ? '…' : envData?.precipitation_mm?.toFixed(1) ?? '0'}</div>
          <div style={{ fontSize:'0.75rem', color:'var(--color-text-secondary)' }}>mm/h</div>
        </article>
      </div>

      {/* ── Graphiques historique ── */}
      <div className="grid-2">
        {/* Historique AQI */}
        <section className="card" aria-label="Historique AQI sur 7 jours">
          <h2 className="card__title" style={{ marginBottom:'1rem' }}>📈 Historique AQI — 7 jours</h2>
          {histLoading ? (
            <div style={{ display:'flex', justifyContent:'center', padding:'2rem' }}>
              <div className="spinner" aria-label="Chargement de l'historique" />
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={200}>
              <AreaChart data={history} aria-label="Graphique AQI sur 7 jours">
                <defs>
                  <linearGradient id="aqiGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%"  stopColor="var(--color-accent)" stopOpacity={0.3}/>
                    <stop offset="95%" stopColor="var(--color-accent)" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                <XAxis dataKey="date" tick={{ fill:'var(--color-text-muted)', fontSize:11 }} />
                <YAxis domain={[0,5]} tick={{ fill:'var(--color-text-muted)', fontSize:11 }} />
                <Tooltip
                  contentStyle={{ background:'var(--color-bg-card)', border:'1px solid var(--color-border)', borderRadius:8 }}
                  labelStyle={{ color:'var(--color-text-primary)' }}
                  itemStyle={{ color:'var(--color-accent)' }}
                />
                <Area type="monotone" dataKey="aqi_mean" stroke="var(--color-accent)"
                  fill="url(#aqiGrad)" strokeWidth={2} name="AQI moyen" />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </section>

        {/* PM2.5 + NO2 */}
        <section className="card" aria-label="Historique PM2.5 et NO2 sur 7 jours">
          <h2 className="card__title" style={{ marginBottom:'1rem' }}>🏭 PM2.5 & NO₂ — 7 jours</h2>
          {histLoading ? (
            <div style={{ display:'flex', justifyContent:'center', padding:'2rem' }}>
              <div className="spinner" aria-label="Chargement" />
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={200}>
              <LineChart data={history} aria-label="Évolution PM2.5 et NO2">
                <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                <XAxis dataKey="date" tick={{ fill:'var(--color-text-muted)', fontSize:11 }} />
                <YAxis tick={{ fill:'var(--color-text-muted)', fontSize:11 }} />
                <Tooltip
                  contentStyle={{ background:'var(--color-bg-card)', border:'1px solid var(--color-border)', borderRadius:8 }}
                  labelStyle={{ color:'var(--color-text-primary)' }}
                />
                <Line type="monotone" dataKey="pm25_mean" stroke="var(--traffic-sat)"
                  strokeWidth={2} dot={false} name="PM2.5 µg/m³" />
                <Line type="monotone" dataKey="no2_mean" stroke="var(--traffic-block)"
                  strokeWidth={2} dot={false} name="NO₂ µg/m³" />
              </LineChart>
            </ResponsiveContainer>
          )}
        </section>
      </div>

      {/* ── Info Green IT ── */}
      <div className="card" style={{ marginTop:'1rem', background:'rgba(34,197,94,0.05)',
        borderColor:'rgba(34,197,94,0.2)' }}>
        <div style={{ display:'flex', alignItems:'flex-start', gap:'1rem' }}>
          <span style={{ fontSize:'1.5rem' }} aria-hidden="true">🌱</span>
          <div>
            <div style={{ fontWeight:700, marginBottom:'4px' }}>Green IT — CodeCarbon intégré</div>
            <div style={{ fontSize:'0.8rem', color:'var(--color-text-secondary)' }}>
              Les entraînements du modèle ARIMA+LSTM sont planifiés pendant les heures creuses (22h-6h),
              période où le mix électrique français est à &gt;95% bas-carbone (nucléaire + renouvelables).
              Émissions mesurées et loguées dans <code>logs/carbon/emissions.csv</code>.
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

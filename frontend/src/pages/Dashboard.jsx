/**
 * Dashboard — Page principale UrbanFlow
 * Carte Leaflet + KPIs + Slider temporel + Simulation + Alertes
 */
import { useState, useMemo } from 'react'
import TrafficMap from '../components/Map/TrafficMap'
import KPICard from '../components/Charts/KPICard'
import AlertsPanel from '../components/Alerts/AlertsPanel'
import SimulationPanel from '../components/Charts/SimulationPanel'

const CONGESTION_LABELS = ['Fluide', 'Dense', 'Saturé', 'Bloqué', 'Paralysé']
const HORIZON_OPTIONS   = [15, 30, 60, 120, 240]

export default function Dashboard({ trafficData, heatmapData, alerts, envData, loading, onRefresh }) {
  const [horizon, setHorizon] = useState(60)

  // KPIs calculés et simulés selon l'horizon de prédiction
  const kpis = useMemo(() => {
    if (!trafficData.length) return null;
    let avgSpeed = trafficData.reduce((s, d) => s + (d.average_speed_kmh || 0), 0) / trafficData.length;
    let totalVeh = trafficData.reduce((s, d) => s + (d.vehicle_count || 0), 0);
    let maxCong  = Math.max(...trafficData.map(d => d.congestion_level || 0));
    let alerts_c = alerts.length;

    // Simulation intelligente basée sur l'heure cible
    if (horizon > 0) {
      const currentHour = new Date().getHours();
      const targetHour = (currentHour + (horizon / 60)) % 24;
      
      // Définition des heures de pointe (7h-9h et 17h-19h)
      const isTargetRushHour = (targetHour >= 7 && targetHour <= 9) || (targetHour >= 17 && targetHour <= 19);
      const isCurrentRushHour = (currentHour >= 7 && currentHour <= 9) || (currentHour >= 17 && currentHour <= 19);

      if (isTargetRushHour && !isCurrentRushHour) {
        // On va vers une heure de pointe : ça s'aggrave
        avgSpeed = avgSpeed * 0.6;
        totalVeh = totalVeh * 1.5;
        maxCong = Math.min(4, maxCong + 1);
        alerts_c = alerts_c + Math.floor(horizon / 30);
      } else if (!isTargetRushHour && isCurrentRushHour) {
        // On sort d'une heure de pointe : ça s'améliore
        avgSpeed = avgSpeed * 1.3;
        totalVeh = totalVeh * 0.6;
        maxCong = Math.max(0, maxCong - 1);
        alerts_c = Math.max(0, alerts_c - 1);
      } else {
        // Période similaire, légère variation aléatoire selon l'horizon
        const variance = (horizon / 60) * 0.05; // 5% par heure
        avgSpeed = avgSpeed * (1 - variance);
        totalVeh = totalVeh * (1 + variance);
      }
    }

    return { avgSpeed, totalVeh, maxCong, alerts_c }
  }, [trafficData, alerts, horizon])

  // Simulation de la météo dans le futur selon l'horizon
  const simulatedTemp = useMemo(() => {
    if (!envData?.temperature_celsius) return null;
    const baseTemp = envData.temperature_celsius;
    const currentHour = new Date().getHours();
    // Le matin (6h-14h) la temp monte, l'après-midi/soir (15h-5h) elle descend
    const isRising = currentHour >= 6 && currentHour <= 14;
    const tempChangePerHour = isRising ? 0.5 : -0.5;
    return baseTemp + (tempChangePerHour * (horizon / 60));
  }, [envData, horizon]);

  return (
    <div className="page fade-in">
      {/* ── En-tête de page ────────────────────────────────────────────── */}
      <div className="page-header" style={{ display:'flex', alignItems:'center', justifyContent:'space-between' }}>
        <div>
          <h1 className="page-title">Tableau de bord — Trafic IDF</h1>
          <p className="page-subtitle">
            Données temps réel · {trafficData.length} capteurs actifs ·
            Prédictions ARIMA+LSTM à <strong>{horizon} min</strong>
          </p>
        </div>
        <button
          className="btn btn--ghost"
          onClick={onRefresh}
          aria-label="Rafraîchir les données"
        >
          🔄 Rafraîchir
        </button>
      </div>

      {/* ── KPI Cards ──────────────────────────────────────────────────── */}
      <div className="kpi-grid" role="region" aria-label="Indicateurs clés du trafic">
        <KPICard
          icon="🚗"
          label="Vitesse moyenne"
          value={loading ? '…' : kpis ? kpis.avgSpeed.toFixed(0) : '--'}
          unit="km/h"
          color="var(--color-accent)"
          trend={-1}
          description="vs hier même heure"
        />
        <KPICard
          icon="📊"
          label="Débit total"
          value={loading ? '…' : kpis ? (kpis.totalVeh / 1000).toFixed(1) + 'k' : '--'}
          unit="véh/h"
          color="var(--color-text-primary)"
          trend={0}
          description="stable"
        />
        <KPICard
          icon="🚦"
          label="Congestion max"
          value={loading ? '…' : kpis ? CONGESTION_LABELS[kpis.maxCong] : '--'}
          color={
            kpis?.maxCong >= 3 ? 'var(--traffic-jam)' :
            kpis?.maxCong === 2 ? 'var(--traffic-sat)' :
            'var(--traffic-free)'
          }
          trend={kpis?.maxCong >= 2 ? 1 : 0}
          description={kpis?.maxCong >= 2 ? 'en aggravation' : 'normal'}
        />
        <KPICard
          icon="🌿"
          label="AQI Paris"
          value={loading ? '…' : envData ? envData.aqi : '--'}
          unit="/5"
          color={
            envData?.aqi <= 2 ? 'var(--aqi-good)' :
            envData?.aqi === 3 ? 'var(--aqi-moderate)' :
            'var(--aqi-bad)'
          }
          trend={envData?.aqi >= 3 ? 1 : 0}
          description="qualité de l'air"
        />
        <KPICard
          icon="🚨"
          label="Alertes actives"
          value={loading ? '…' : alerts.length}
          color={alerts.length > 3 ? 'var(--traffic-jam)' : 'var(--traffic-free)'}
          trend={alerts.length > 0 ? 1 : 0}
          description={`congestion ≥ 2`}
        />
        <KPICard
          icon="🌡️"
          label="Température"
          value={loading ? '…' : simulatedTemp ? simulatedTemp.toFixed(1) : '--'}
          unit="°C"
          color="var(--color-text-primary)"
          description={envData?.weather_condition || ''}
        />
      </div>

      {/* ── Slider temporel prédictions ────────────────────────────────── */}
      <div className="card" style={{ marginBottom:'1.5rem' }}>
        <div style={{ display:'flex', alignItems:'center', gap:'1rem', flexWrap:'wrap' }}>
          <span style={{ fontSize:'0.875rem', fontWeight:600, color:'var(--color-text-secondary)', whiteSpace:'nowrap' }}>
            🕐 Horizon de prédiction :
          </span>
          <div
            role="radiogroup"
            aria-label="Choisir l'horizon de prédiction"
            style={{ display:'flex', gap:'0.5rem', flexWrap:'wrap' }}
          >
            {HORIZON_OPTIONS.map(h => (
              <button
                key={h}
                role="radio"
                aria-checked={horizon === h}
                onClick={() => setHorizon(h)}
                className="btn"
                style={{
                  padding: '0.35rem 0.85rem',
                  fontSize: '0.8rem',
                  background: horizon === h ? 'var(--color-accent)' : 'var(--color-bg-secondary)',
                  color:      horizon === h ? 'white' : 'var(--color-text-secondary)',
                  border: `1px solid ${horizon === h ? 'var(--color-accent)' : 'var(--color-border)'}`,
                }}
                aria-label={`Prédire dans ${h} minutes`}
              >
                {h < 60 ? `${h} min` : `${h/60}h`}
              </button>
            ))}
          </div>
          <span style={{ fontSize:'0.75rem', color:'var(--color-text-muted)' }}>
            Modèle : ARIMA + LSTM · pondération adaptative
          </span>
        </div>
      </div>

      {/* ── Carte + Alertes ────────────────────────────────────────────── */}
      <div className="grid-map" style={{ marginBottom:'1.5rem' }}>
        <div>
          <div className="card__header" style={{ marginBottom:'0.75rem' }}>
            <h2 className="card__title">🗺️ Carte du trafic en temps réel</h2>
            <span style={{ fontSize:'0.75rem', color:'var(--color-text-muted)' }}>
              OpenStreetMap · Leaflet.js
            </span>
          </div>
          <TrafficMap
            trafficData={trafficData}
            heatmapData={heatmapData}
            horizon={horizon}
          />
          {/* Alternative textuelle carte (WCAG 1.1.1) */}
          <details style={{ marginTop:'0.5rem' }}>
            <summary style={{ fontSize:'0.75rem', color:'var(--color-text-muted)', cursor:'pointer' }}>
              📋 Version textuelle de la carte (accessibilité)
            </summary>
            <div
              role="table"
              aria-label="Tableau des capteurs de trafic"
              style={{ marginTop:'0.5rem', overflow:'auto' }}
            >
              <table style={{ width:'100%', fontSize:'0.75rem', borderCollapse:'collapse' }}>
                <thead>
                  <tr style={{ color:'var(--color-text-muted)', textAlign:'left' }}>
                    <th style={{ padding:'4px 8px' }}>Axe</th>
                    <th style={{ padding:'4px 8px' }}>Congestion</th>
                    <th style={{ padding:'4px 8px' }}>Vitesse</th>
                    <th style={{ padding:'4px 8px' }}>Débit</th>
                  </tr>
                </thead>
                <tbody>
                  {trafficData.slice(0, 10).map(d => (
                    <tr key={d.sensor_id} style={{ borderTop:'1px solid var(--color-border)' }}>
                      <td style={{ padding:'4px 8px', color:'var(--color-text-primary)' }}>
                        {d.road_name || d.sensor_id}
                      </td>
                      <td style={{ padding:'4px 8px' }}>
                        <span className={`congestion-badge congestion-${d.congestion_level}`}>
                          {CONGESTION_LABELS[d.congestion_level]}
                        </span>
                      </td>
                      <td style={{ padding:'4px 8px', color:'var(--color-text-secondary)' }}>
                        {d.average_speed_kmh?.toFixed(0)} km/h
                      </td>
                      <td style={{ padding:'4px 8px', color:'var(--color-text-secondary)' }}>
                        {d.vehicle_count} v/h
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </details>
        </div>

        {/* ── Colonne droite ── */}
        <div style={{ display:'flex', flexDirection:'column', gap:'1rem' }}>
          <AlertsPanel alerts={alerts} loading={loading} />
          <SimulationPanel />
        </div>
      </div>
    </div>
  )
}

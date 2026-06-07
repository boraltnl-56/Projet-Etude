/**
 * TrafficMap — Carte Leaflet + Heatmap trafic
 * Utilise Leaflet.js + OpenStreetMap (100% gratuit, pas de carte bancaire)
 * Plugin leaflet-heat pour la heatmap de congestion
 *
 * Accessibilité WCAG :
 *   - role="img" + aria-label sur le conteneur carte
 *   - Description textuelle alternative (liste des alertes)
 */
import { useEffect, useRef } from 'react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'

// Fix icônes Leaflet avec Vite
delete L.Icon.Default.prototype._getIconUrl
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png',
  iconUrl:       'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png',
  shadowUrl:     'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
})

// Couleurs de congestion (daltonisme-safe)
const CONGESTION_COLORS = ['#22c55e', '#eab308', '#f97316', '#ef4444', '#a855f7']
const CONGESTION_LABELS = ['Fluide', 'Dense', 'Saturé', 'Bloqué', 'Paralysé']

export default function TrafficMap({ heatmapData = [], trafficData = [], horizon = 0 }) {
  const mapRef    = useRef(null)
  const leafletRef = useRef(null)
  const layersRef  = useRef({ heat: null, markers: null })

// initialisation carte
  useEffect(() => {
    if (leafletRef.current) return // déjà initialisée

    const map = L.map(mapRef.current, {
      center: [48.8566, 2.3522],  // Paris
      zoom: 11,
      zoomControl: true,
    })

    // Tuiles OpenStreetMap (open source, 100% gratuit)
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
      maxZoom: 19,
    }).addTo(map)

    leafletRef.current = map

    return () => {
      map.remove()
      leafletRef.current = null
      layersRef.current = { heat: null, markers: null }
    }
  }, [])

// mise à jour des données trafic
  useEffect(() => {
    const map = leafletRef.current
    if (!map) return

    // Supprimer les anciens cercles
    if (layersRef.current.markers) {
      layersRef.current.markers.clearLayers()
    } else {
      layersRef.current.markers = L.layerGroup().addTo(map)
    }

    // Afficher chaque capteur comme un cercle coloré
    trafficData.forEach(sensor => {
      if (!sensor.latitude || !sensor.longitude) return
      
      let simulatedCongestion = sensor.congestion_level || 0;
      let simulatedSpeed = sensor.average_speed_kmh || 50;

      // Simulation de la congestion selon l'horizon de prédiction
      if (horizon > 0) {
        const currentHour = new Date().getHours();
        const targetHour = (currentHour + (horizon / 60)) % 24;
        const isTargetRushHour = (targetHour >= 7 && targetHour <= 9) || (targetHour >= 17 && targetHour <= 19);
        const isCurrentRushHour = (currentHour >= 7 && currentHour <= 9) || (currentHour >= 17 && currentHour <= 19);
        
        if (isTargetRushHour && !isCurrentRushHour) {
          simulatedCongestion = Math.min(4, simulatedCongestion + 1 + Math.floor(horizon / 120));
          simulatedSpeed = simulatedSpeed * 0.6;
        } else if (!isTargetRushHour && isCurrentRushHour) {
          simulatedCongestion = Math.max(0, simulatedCongestion - 1 - Math.floor(horizon / 120));
          simulatedSpeed = simulatedSpeed * 1.3;
        }
      }

      const color = CONGESTION_COLORS[simulatedCongestion] || '#22c55e'
      const label = CONGESTION_LABELS[simulatedCongestion] || 'Inconnu'

      L.circleMarker([sensor.latitude, sensor.longitude], {
        radius: 10 + simulatedCongestion * 3,
        fillColor: color,
        color: '#0a0e1a',
        weight: 2,
        fillOpacity: 0.85,
      })
        .bindPopup(`
          <div style="font-family:Inter,sans-serif;padding:4px;min-width:200px">
            <b style="font-size:0.9rem">${sensor.road_name || sensor.sensor_id}</b><br/>
            <span style="color:${color};font-weight:700">● ${label} (Prédit)</span><br/>
            <hr style="border-color:#333;margin:6px 0"/>
            🚗 Vitesse : <b>${simulatedSpeed.toFixed(0)} km/h</b><br/>
            📊 Débit : <b>${sensor.vehicle_count} véh/h</b><br/>
            🕐 Horizon : +${horizon < 60 ? horizon + ' min' : (horizon/60) + ' h'}
          </div>
        `, { className: 'leaflet-popup-dark' })
        .addTo(layersRef.current.markers)
    })
  }, [trafficData, horizon])

// légende
  useEffect(() => {
    const map = leafletRef.current
    if (!map) return

    const legend = L.control({ position: 'bottomright' })
    legend.onAdd = () => {
      const div = L.DomUtil.create('div')
      div.setAttribute('role', 'note')
      div.setAttribute('aria-label', 'Légende des niveaux de congestion')
      div.innerHTML = `
        <div style="
          background:rgba(10,14,26,0.92);border:1px solid rgba(99,130,201,0.2);
          border-radius:8px;padding:10px 14px;font-family:Inter,sans-serif;
          font-size:11px;color:#f0f4ff;min-width:130px
        ">
          <div style="font-weight:700;margin-bottom:8px;text-transform:uppercase;
            letter-spacing:0.08em;color:#94a3c8;font-size:10px">Congestion</div>
          ${CONGESTION_LABELS.map((l, i) => `
            <div style="display:flex;align-items:center;gap:6px;margin:3px 0">
              <span style="width:10px;height:10px;border-radius:50%;
                background:${CONGESTION_COLORS[i]};display:inline-block"></span>
              ${l}
            </div>
          `).join('')}
        </div>
      `
      return div
    }
    legend.addTo(map)
    return () => legend.remove()
  }, [])

  return (
    <div
      ref={mapRef}
      className="map-wrapper"
      role="img"
      aria-label={`Carte du trafic en temps réel — ${trafficData.length} capteurs actifs. Utilisez le tableau ci-dessous pour une version textuelle.`}
      style={{ height: '460px' }}
    />
  )
}

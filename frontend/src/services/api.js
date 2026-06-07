/**
 * UrbanFlow — Service API avec fallback de données mockées
 * Si l'API FastAPI n'est pas disponible, on utilise des données
 * simulées réalistes pour la démonstration.
 * Auteur : UrbanFlow Team — M2 Big Data & IA 2025
 */

import axios from 'axios'

const API_BASE = import.meta.env.VITE_API_URL || ''

const api = axios.create({
  baseURL: `${API_BASE}/api/v1`,
  timeout: 4000,
  headers: { 'Content-Type': 'application/json' },
})

// données simulées réalistes idf
function getMockTrafficData() {
  const hour = new Date().getHours()
  const isRush = (hour >= 7 && hour <= 9) || (hour >= 17 && hour <= 19)
  const isNight = hour >= 22 || hour <= 6

  const axes = [
    { sensor_id: 'BP_N_01',  road_name: 'Périphérique Nord',         lat: 48.897, lon: 2.358 },
    { sensor_id: 'BP_S_01',  road_name: 'Périphérique Sud',          lat: 48.817, lon: 2.325 },
    { sensor_id: 'BP_E_01',  road_name: 'Périphérique Est',          lat: 48.862, lon: 2.412 },
    { sensor_id: 'BP_O_01',  road_name: 'Périphérique Ouest',        lat: 48.849, lon: 2.251 },
    { sensor_id: 'A1_01',    road_name: 'A1 — Porte de la Villette', lat: 48.897, lon: 2.373 },
    { sensor_id: 'A6_01',    road_name: 'A6 — Porte d\'Orléans',    lat: 48.817, lon: 2.325 },
    { sensor_id: 'A13_01',   road_name: 'A13 — Porte de St-Cloud',  lat: 48.834, lon: 2.250 },
    { sensor_id: 'N118_01',  road_name: 'N118 — Vélizy',            lat: 48.773, lon: 2.177 },
  ]

  return axes.map(ax => {
    const baseSpeed = isNight ? rand(85, 115) : isRush ? rand(12, 42) : rand(55, 90)
    const speed = Math.max(5, baseSpeed + rand(-5, 5))
    const congestion = speed <= 10 ? 4 : speed <= 30 ? 3 : speed <= 50 ? 2 : speed <= 80 ? 1 : 0
    return {
      sensor_id: ax.sensor_id,
      road_name: ax.road_name,
      latitude: ax.lat + rand(-0.002, 0.002),
      longitude: ax.lon + rand(-0.002, 0.002),
      vehicle_count: isRush ? rand(1200, 2500) : rand(200, 800),
      average_speed_kmh: Math.round(speed * 10) / 10,
      congestion_level: congestion,
      timestamp: new Date().toISOString(),
      source: 'data_gouv_simulated',
    }
  })
}

function getMockHeatmap() {
  return getMockTrafficData().map(d => ({
    lat: d.latitude,
    lon: d.longitude,
    weight: d.congestion_level / 4,
    congestion_level: d.congestion_level,
    road_name: d.road_name,
  }))
}

function getMockAlerts() {
  const traffic = getMockTrafficData()
  const alerts = traffic.filter(d => d.congestion_level >= 2)
  return { count: alerts.length, alerts, source: 'mock' }
}

function getMockEnv() {
  const hour = new Date().getHours()
  const isPeak = (hour >= 8 && hour <= 10) || (hour >= 18 && hour <= 20)
  return [{
    source: 'openweathermap',
    timestamp: new Date().toISOString(),
    latitude: 48.8566,
    longitude: 2.3522,
    aqi: isPeak ? rand(3, 4) : rand(1, 3),
    pm25: isPeak ? rand(25, 65) : rand(5, 20),
    pm10: isPeak ? rand(35, 85) : rand(10, 35),
    no2:  isPeak ? rand(70, 180) : rand(15, 55),
    o3:   rand(40, 100),
    temperature_celsius: rand(12, 28),
    humidity_pct: rand(45, 80),
    wind_speed_ms: rand(1, 8),
    weather_condition: ['Clair', 'Nuageux', 'Couvert', 'Pluie légère'][Math.floor(Math.random() * 4)],
    precipitation_mm: Math.random() > 0.75 ? rand(0.1, 3) : 0,
  }]
}

function getMockAQIHistory() {
  const history = []
  for (let i = 6; i >= 0; i--) {
    const d = new Date()
    d.setDate(d.getDate() - i)
    history.push({
      date: d.toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit' }),
      aqi_mean: rand(1, 4),
      pm25_mean: rand(8, 55),
      no2_mean:  rand(20, 110),
    })
  }
  return { history, period_days: 7 }
}

function getMockReports() {
  const types = ['embouteillage', 'accident', 'travaux', 'incident_transport', 'danger']
  return Array.from({ length: 8 }, (_, i) => ({
    ephemeral_id: crypto.randomUUID(),
    report_type: types[i % types.length],
    severity: rand(1, 4),
    latitude_approx: 48.8566 + rand(-0.05, 0.05),
    longitude_approx: 2.3522 + rand(-0.05, 0.05),
    timestamp: new Date(Date.now() - i * 12 * 60000).toISOString(),
    expires_at: new Date(Date.now() + 30 * 24 * 3600000).toISOString(),
    rgpd_compliant: true,
  }))
}

function rand(min, max) {
  return Math.round((Math.random() * (max - min) + min) * 10) / 10
}

// wrapper avec fallback automatique
async function withFallback(apiCall, mockData) {
  try {
    return await apiCall()
  } catch {
    return typeof mockData === 'function' ? mockData() : mockData
  }
}

// api trafic
export const trafficAPI = {
  getCurrent: (limit = 100) =>
    withFallback(
      () => api.get('/traffic/current', { params: { limit } }).then(r => r.data),
      getMockTrafficData
    ),

  getHeatmap: () =>
    withFallback(
      () => api.get('/traffic/heatmap').then(r => r.data),
      getMockHeatmap
    ),

  getAlerts: (minLevel = 2) =>
    withFallback(
      () => api.get('/traffic/alerts', { params: { min_level: minLevel } }).then(r => r.data),
      getMockAlerts
    ),

  predict: (sensorId, horizonMinutes = 60) =>
    withFallback(
      () => api.post('/traffic/predict', {
        sensor_id: sensorId,
        horizon_minutes: horizonMinutes,
        include_confidence: true,
      }).then(r => r.data),
      () => {
        const hour = (new Date().getHours() + Math.floor(horizonMinutes / 60)) % 24
        const isRush = (hour >= 7 && hour <= 9) || (hour >= 17 && hour <= 19)
        const speed = isRush ? rand(15, 40) : rand(65, 105)
        const cong  = speed <= 30 ? 3 : speed <= 50 ? 2 : speed <= 80 ? 1 : 0
        return {
          sensor_id: sensorId,
          predicted_congestion_level: cong,
          predicted_speed_kmh: speed,
          prediction_horizon_minutes: horizonMinutes,
          confidence_lower: Math.round(speed * 0.85 * 10) / 10,
          confidence_upper: Math.round(speed * 1.15 * 10) / 10,
          model_used: 'hybrid_arima_lstm',
          computed_at: new Date().toISOString(),
          cached: false,
        }
      }
    ),
}

// api environnement
export const environmentAPI = {
  getCurrent: () =>
    withFallback(
      () => api.get('/environment/current').then(r => r.data),
      getMockEnv
    ),

  getAQIHistory: () =>
    withFallback(
      () => api.get('/environment/aqi-history').then(r => r.data),
      getMockAQIHistory
    ),
}

// api crowdsourcing
export const crowdsourcingAPI = {
  submitReport: (data) =>
    withFallback(
      () => api.post('/crowdsourcing/report', data).then(r => r.data),
      () => ({
        success: true,
        ephemeral_id: crypto.randomUUID(),
        message: `Signalement '${data.report_type}' enregistré (mode démo).`,
        rgpd_notice: 'Vos données ont été anonymisées. Aucune donnée personnelle n\'est conservée. Ce signalement sera supprimé automatiquement dans 30 jours (Art. 17 RGPD).',
      })
    ),

  getReports: (limit = 50) =>
    withFallback(
      () => api.get('/crowdsourcing/reports', { params: { limit } }).then(r => r.data),
      getMockReports
    ),
}

// api health
export const healthAPI = {
  check: () =>
    api.get('/health').then(r => r.data),
}

export default api

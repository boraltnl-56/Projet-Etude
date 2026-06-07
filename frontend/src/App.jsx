import { useState, useEffect, useCallback } from 'react'
import { trafficAPI, environmentAPI, healthAPI } from './services/api'
import Layout from './components/Layout/Layout'
import Dashboard from './pages/Dashboard'
import Environment from './pages/Environment'
import Crowdsourcing from './pages/Crowdsourcing'
import './index.css'

export default function App() {
  const [currentPage, setCurrentPage] = useState('dashboard')
  const [apiStatus, setApiStatus] = useState('checking')
  const [trafficData, setTrafficData] = useState([])
  const [heatmapData, setHeatmapData] = useState([])
  const [alerts, setAlerts] = useState([])
  const [envData, setEnvData] = useState(null)
  const [loading, setLoading] = useState(true)

  const refreshData = useCallback(async () => {
    try {
      const [traffic, heatmap, alertsRes, env] = await Promise.allSettled([
        trafficAPI.getCurrent(),
        trafficAPI.getHeatmap(),
        trafficAPI.getAlerts(2),
        environmentAPI.getCurrent(),
      ])
      if (traffic.status === 'fulfilled')  setTrafficData(traffic.value)
      if (heatmap.status === 'fulfilled')  setHeatmapData(heatmap.value)
      if (alertsRes.status === 'fulfilled') setAlerts(alertsRes.value.alerts || [])
      if (env.status === 'fulfilled')      setEnvData(env.value[0] || null)
      setApiStatus('online')
    } catch {
      setApiStatus('offline')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    // Vérif santé API
    healthAPI.check()
      .then(() => setApiStatus('online'))
      .catch(() => setApiStatus('offline'))

    refreshData()
    // Rafraîchissement auto toutes les 30s
    const interval = setInterval(refreshData, 30000)
    return () => clearInterval(interval)
  }, [refreshData])

  const pages = { dashboard: Dashboard, environment: Environment, crowdsourcing: Crowdsourcing }
  const PageComponent = pages[currentPage] || Dashboard

  return (
    <>
      {/* Skip link WCAG 2.4.1 */}
      <a href="#main-content" className="skip-link">
        Aller au contenu principal
      </a>
      <Layout
        currentPage={currentPage}
        onNavigate={setCurrentPage}
        apiStatus={apiStatus}
      >
        <main id="main-content" role="main" className="main-content">
          <PageComponent
            trafficData={trafficData}
            heatmapData={heatmapData}
            alerts={alerts}
            envData={envData}
            loading={loading}
            onRefresh={refreshData}
          />
        </main>
      </Layout>
    </>
  )
}

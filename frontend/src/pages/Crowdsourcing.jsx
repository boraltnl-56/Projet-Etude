/**
 * Crowdsourcing — Page signalements citoyens
 * Formulaire de signalement + carte des incidents + notice RGPD
 * Conformité RGPD Art. 13 — information des personnes
 */
import { useState, useEffect } from 'react'
import { crowdsourcingAPI } from '../services/api'

const REPORT_TYPES = [
  { value:'embouteillage',     label:'🚗 Embouteillage',       color:'var(--traffic-jam)' },
  { value:'accident',          label:'🚨 Accident',             color:'var(--traffic-block)' },
  { value:'travaux',           label:'🚧 Travaux / Chantier',   color:'var(--traffic-sat)' },
  { value:'incident_transport',label:'🚇 Incident transport',   color:'var(--color-accent)' },
  { value:'danger',            label:'⚠️ Danger sur chaussée', color:'var(--traffic-slow)' },
]

export default function Crowdsourcing() {
  const [reports, setReports]     = useState([])
  const [loading, setLoading]     = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [success, setSuccess]     = useState(null)
  const [error, setError]         = useState(null)

  const [form, setForm] = useState({
    latitude: 48.8566,
    longitude: 2.3522,
    report_type: 'embouteillage',
    severity: 2,
    description: '',
  })

  // Charger les signalements récents
  useEffect(() => {
    crowdsourcingAPI.getReports(20)
      .then(setReports)
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  const handleSubmit = async (e) => {
    e.preventDefault()
    setSubmitting(true)
    setError(null)
    setSuccess(null)
    try {
      const result = await crowdsourcingAPI.submitReport(form)
      setSuccess(result)
      setForm({ ...form, description: '' })
      // Recharger les signalements
      crowdsourcingAPI.getReports(20).then(setReports)
    } catch (err) {
      setError('Erreur lors de la soumission. Réessayez dans quelques instants.')
    } finally {
      setSubmitting(false)
    }
  }

  const SEVERITY_LABELS = ['', '⚪ Mineur', '🟡 Modéré', '🟠 Important', '🔴 Grave', '🚨 Critique']

  return (
    <div className="page fade-in">
      <div className="page-header">
        <h1 className="page-title">📍 Signalements Citoyens</h1>
        <p className="page-subtitle">
          Signalez un incident de mobilité — Anonymisation RGPD immédiate
        </p>
      </div>

      {/* ── Notice RGPD (Art. 13) ── */}
      <div className="card" style={{ marginBottom:'1.5rem', background:'rgba(59,130,246,0.05)',
        borderColor:'rgba(59,130,246,0.2)' }}
        role="note"
        aria-label="Information RGPD concernant la collecte de données"
      >
        <div style={{ display:'flex', gap:'1rem', alignItems:'flex-start' }}>
          <span style={{ fontSize:'1.4rem' }} aria-hidden="true">🔐</span>
          <div>
            <div style={{ fontWeight:700, marginBottom:'4px', fontSize:'0.9rem' }}>
              Protection de vos données (RGPD Art. 13)
            </div>
            <div style={{ fontSize:'0.78rem', color:'var(--color-text-secondary)', lineHeight:1.7 }}>
              <strong>Données anonymisées immédiatement :</strong> votre adresse IP est hashée (SHA-256+sel)
              et vos coordonnées GPS sont floutées à ±150m avant tout stockage.
              <strong> Aucune donnée personnelle n'est conservée.</strong>
              Ce signalement sera <strong>automatiquement supprimé dans 30 jours</strong> (Art. 17 RGPD — Droit à l'effacement).
              Responsable de traitement : UrbanFlow — Finalité : amélioration de la mobilité urbaine.
            </div>
          </div>
        </div>
      </div>

      <div className="grid-2">
        {/* ── Formulaire ── */}
        <section className="card" aria-label="Formulaire de signalement">
          <h2 className="card__title" style={{ marginBottom:'1.25rem' }}>
            Nouveau signalement
          </h2>

          <form onSubmit={handleSubmit} noValidate>
            {/* Type d'incident */}
            <div className="form-group" style={{ marginBottom:'1rem' }}>
              <label className="form-label" htmlFor="report-type">Type d'incident *</label>
              <select
                id="report-type"
                className="form-select"
                value={form.report_type}
                onChange={e => setForm({ ...form, report_type: e.target.value })}
                required
                aria-required="true"
              >
                {REPORT_TYPES.map(t => (
                  <option key={t.value} value={t.value}>{t.label}</option>
                ))}
              </select>
            </div>

            {/* Sévérité */}
            <div className="form-group" style={{ marginBottom:'1rem' }}>
              <label className="form-label" htmlFor="severity">
                Sévérité : {SEVERITY_LABELS[form.severity]}
              </label>
              <input
                id="severity"
                type="range"
                min={1} max={5}
                value={form.severity}
                onChange={e => setForm({ ...form, severity: parseInt(e.target.value) })}
                aria-valuemin={1}
                aria-valuemax={5}
                aria-valuenow={form.severity}
                aria-valuetext={SEVERITY_LABELS[form.severity]}
                style={{ width:'100%', accentColor:'var(--color-accent)' }}
              />
              <div style={{ display:'flex', justifyContent:'space-between',
                fontSize:'0.7rem', color:'var(--color-text-muted)' }}>
                <span>Mineur</span><span>Critique</span>
              </div>
            </div>

            {/* Localisation */}
            <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:'0.75rem', marginBottom:'1rem' }}>
              <div className="form-group">
                <label className="form-label" htmlFor="latitude">Latitude *</label>
                <input
                  id="latitude"
                  type="number"
                  className="form-input"
                  value={form.latitude}
                  step="0.0001"
                  min={48.12} max={49.24}
                  onChange={e => setForm({ ...form, latitude: parseFloat(e.target.value) })}
                  aria-describedby="lat-hint"
                  required
                />
                <span id="lat-hint" style={{ fontSize:'0.7rem', color:'var(--color-text-muted)' }}>
                  IDF : 48.12 – 49.24
                </span>
              </div>
              <div className="form-group">
                <label className="form-label" htmlFor="longitude">Longitude *</label>
                <input
                  id="longitude"
                  type="number"
                  className="form-input"
                  value={form.longitude}
                  step="0.0001"
                  min={1.45} max={3.56}
                  onChange={e => setForm({ ...form, longitude: parseFloat(e.target.value) })}
                  aria-describedby="lon-hint"
                  required
                />
                <span id="lon-hint" style={{ fontSize:'0.7rem', color:'var(--color-text-muted)' }}>
                  IDF : 1.45 – 3.56
                </span>
              </div>
            </div>

            {/* Description */}
            <div className="form-group" style={{ marginBottom:'1.25rem' }}>
              <label className="form-label" htmlFor="description">
                Description (optionnel — max 500 caractères)
              </label>
              <textarea
                id="description"
                className="form-textarea"
                value={form.description}
                onChange={e => setForm({ ...form, description: e.target.value })}
                maxLength={500}
                placeholder="Ex : Accident impliquant 2 véhicules, voie de droite bloquée…"
                aria-describedby="desc-hint"
              />
              <span id="desc-hint" style={{ fontSize:'0.7rem', color:'var(--color-text-muted)' }}>
                {form.description.length}/500 — les informations personnelles seront automatiquement supprimées
              </span>
            </div>

            <button
              type="submit"
              className="btn btn--primary"
              disabled={submitting}
              aria-busy={submitting}
              style={{ width:'100%', justifyContent:'center' }}
            >
              {submitting ? (
                <><span className="spinner" aria-hidden="true" /> Anonymisation en cours…</>
              ) : (
                '📍 Soumettre le signalement'
              )}
            </button>
          </form>

          {/* Succès */}
          {success && (
            <div
              role="alert"
              className="fade-in"
              style={{ marginTop:'1rem', padding:'0.75rem 1rem', background:'rgba(34,197,94,0.1)',
                border:'1px solid rgba(34,197,94,0.3)', borderRadius:'var(--radius-md)',
                fontSize:'0.8rem' }}
            >
              <div style={{ fontWeight:700, color:'var(--color-traffic-free)', marginBottom:'4px' }}>
                ✅ Signalement enregistré
              </div>
              <div style={{ color:'var(--color-text-secondary)' }}>
                ID éphémère : <code style={{ fontSize:'0.7rem' }}>{success.ephemeral_id?.substring(0,8)}…</code>
              </div>
              <div style={{ color:'var(--color-text-muted)', fontSize:'0.72rem', marginTop:'4px' }}>
                {success.rgpd_notice}
              </div>
            </div>
          )}

          {/* Erreur */}
          {error && (
            <div role="alert" className="fade-in"
              style={{ marginTop:'1rem', padding:'0.75rem 1rem', background:'rgba(239,68,68,0.1)',
                border:'1px solid rgba(239,68,68,0.3)', borderRadius:'var(--radius-md)',
                fontSize:'0.8rem', color:'var(--traffic-jam)' }}>
              ❌ {error}
            </div>
          )}
        </section>

        {/* ── Signalements récents ── */}
        <section className="card" aria-label="Liste des signalements citoyens récents">
          <h2 className="card__title" style={{ marginBottom:'1rem' }}>
            Signalements récents ({reports.length})
          </h2>
          <div
            role="feed"
            aria-label="Flux des signalements anonymisés"
            style={{ display:'flex', flexDirection:'column', gap:'0.5rem',
              maxHeight:'500px', overflowY:'auto' }}
          >
            {loading ? (
              <div style={{ display:'flex', justifyContent:'center', padding:'2rem' }}>
                <div className="spinner" aria-label="Chargement des signalements" />
              </div>
            ) : reports.length === 0 ? (
              <p style={{ color:'var(--color-text-secondary)', textAlign:'center', padding:'1rem',
                fontSize:'0.875rem' }}>
                Aucun signalement récent
              </p>
            ) : reports.map((r, i) => {
              const typeInfo = REPORT_TYPES.find(t => t.value === r.report_type) || REPORT_TYPES[0]
              return (
                <article
                  key={r.ephemeral_id || i}
                  className="alert-item alert-item--warning"
                  aria-label={`Signalement ${typeInfo.label} — sévérité ${r.severity}/5`}
                >
                  <span style={{ fontSize:'1.1rem' }} aria-hidden="true">
                    {typeInfo.label.split(' ')[0]}
                  </span>
                  <div style={{ flex:1 }}>
                    <div style={{ fontWeight:600, fontSize:'0.85rem' }}>
                      {typeInfo.label.substring(2)}
                    </div>
                    <div style={{ fontSize:'0.75rem', color:'var(--color-text-secondary)', display:'flex', gap:'8px', flexWrap:'wrap' }}>
                      <span>Sévérité {r.severity}/5</span>
                      <span>·</span>
                      <span>📍 {r.latitude_approx?.toFixed(3)}, {r.longitude_approx?.toFixed(3)}</span>
                      <span>·</span>
                      <span style={{ color:'var(--color-text-muted)' }}>
                        🔐 ID: {r.ephemeral_id?.substring(0,6)}…
                      </span>
                    </div>
                  </div>
                </article>
              )
            })}
          </div>

          <div style={{ marginTop:'1rem', padding:'0.6rem 0.75rem',
            background:'rgba(34,197,94,0.05)', borderRadius:'var(--radius-sm)',
            fontSize:'0.72rem', color:'var(--color-text-muted)', textAlign:'center' }}>
            🔐 Toutes les données affichées sont anonymisées · Aucune PII stockée · RGPD Art. 5 & 25
          </div>
        </section>
      </div>
    </div>
  )
}

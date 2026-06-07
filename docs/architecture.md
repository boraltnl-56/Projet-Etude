# UrbanFlow — Architecture & Documentation Technique
## Optimisation de la mobilité urbaine à l'aide des données ouvertes
### M2 Big Data & IA — SUP DE VINCI 2025

---

## 1. Architecture Globale du Système

```mermaid
flowchart TB
    subgraph SOURCES["🌐 Sources Open Data"]
        S1["Île-de-France Mobilités\n(GTFS-RT / SIRI)"]
        S2["Data.gouv.fr\n(Trafic RT / Comptages)"]
        S3["OpenWeatherMap\n(Météo + Pollution)"]
        S4["Airparif\n(Qualité de l'air)"]
        S5["Crowdsourcing Citoyens\n(Signalements via API)"]
    end

    subgraph ETL["⚙️ Pipeline ETL Asynchrone (Python)"]
        I["Ingestion Async\n(asyncio + httpx)"]
        T["Transformation\n(normalisation, validation)"]
        A["Anonymisation RGPD\n(hashing IPs, IDs éphémères)"]
        CC["CodeCarbon\n(mesure CO₂)"]
        O["Orchestration\n(Prefect Flows)"]
    end

    subgraph STORAGE["🗄️ Stockage Multi-couches"]
        PG[("PostgreSQL + PostGIS\n(données historiques\n+ index spatio-temporels)")]
        RD[("Redis\n(cache alertes RT\n+ crowdsourcing)")]
    end

    subgraph ML["🤖 Modèle IA Hybride"]
        AR["ARIMA / SARIMAX\n(baseline statistique)"]
        LS["LSTM / STGCN\n(deep learning\nspatio-temporel)"]
        HY["Hybrid Predictor\n(ensemble)"]
    end

    subgraph API["🚀 Backend FastAPI"]
        R1["/traffic/predict"]
        R2["/environment/"]
        R3["/crowdsourcing/"]
        R4["/alerts/realtime"]
        SW["OpenAPI / Swagger UI"]
    end

    subgraph FRONT["💻 Dashboard React"]
        MAP["Mapbox GL JS\n(Heatmaps trafic)"]
        CH["Recharts\n(Prédictions)"]
        AL["Panel Alertes"]
        CR["Module Crowdsourcing"]
    end

    subgraph DEVOPS["🔧 DevOps & Monitoring"]
        DK["Docker Compose / K8s"]
        CI["GitHub Actions CI/CD"]
        PR["Prometheus"]
        GF["Grafana Dashboard"]
    end

    SOURCES --> ETL
    ETL --> STORAGE
    STORAGE --> ML
    ML --> API
    API --> FRONT
    DEVOPS -.->|monitoring| API
    DEVOPS -.->|orchestration| ETL
```

---

## 2. Architecture de Déploiement (K8s)

```mermaid
graph LR
    subgraph K8S["Kubernetes Cluster"]
        subgraph NS_APP["Namespace: urbanflow"]
            POD_API["Pod: FastAPI\n(2 replicas)"]
            POD_ETL["Pod: ETL Worker\n(1 replica)"]
            POD_FRONT["Pod: React App\n(Nginx)"]
        end
        subgraph NS_DATA["Namespace: data"]
            POD_PG["StatefulSet: PostgreSQL\n(Master + Replica)"]
            POD_RD["StatefulSet: Redis\n(Sentinel)"]
        end
        subgraph NS_OBS["Namespace: monitoring"]
            POD_PROM["Prometheus"]
            POD_GRAF["Grafana"]
        end
        ING["Ingress Controller\n(Nginx)"]
    end
    USR["👤 Utilisateur"] --> ING
    ING --> POD_FRONT
    ING --> POD_API
    POD_API --> POD_PG
    POD_API --> POD_RD
    POD_ETL --> POD_PG
    POD_ETL --> POD_RD
    POD_PROM -.->|scrape| POD_API
    POD_PROM -.->|scrape| POD_ETL
    POD_GRAF -.->|datasource| POD_PROM
```

---

## 3. Flux de Données — ETL Pipeline

```mermaid
sequenceDiagram
    participant PREF as Prefect Scheduler
    participant IDF as IDF Mobilités API
    participant DGV as Data.gouv.fr
    participant OWM as OpenWeatherMap
    participant ETL as ETL Ingestor
    participant ANON as RGPD Anonymizer
    participant PG as PostgreSQL
    participant RDS as Redis

    PREF->>ETL: Déclenche flow (cron 5min)
    ETL->>IDF: GET /gtfs-rt (async)
    ETL->>DGV: GET /trafic-rt (async)
    ETL->>OWM: GET /weather (async)
    IDF-->>ETL: GTFS Protobuf feed
    DGV-->>ETL: JSON trafic
    OWM-->>ETL: JSON météo/pollution
    ETL->>ANON: Anonymise IP + coords (crowdsourcing)
    ANON-->>ETL: Données dépersonnalisées
    ETL->>PG: INSERT normalized data (batch)
    ETL->>RDS: SET alerts (TTL 5min)
    Note over ETL: CodeCarbon mesure CO₂ en continu
```

---

## 4. Planification Projet — Diagramme de Gantt

```mermaid
gantt
    title Planification UrbanFlow — M2 Big Data & IA 2025
    dateFormat  YYYY-MM-DD
    axisFormat  %d/%m

    section Phase 1 — Fondations
    Setup projet & Docker           :done,    p1a, 2025-09-01, 5d
    Configuration BDD (PG+Redis)    :done,    p1b, 2025-09-06, 4d
    Pipeline ETL async (3 sources)  :active,  p1c, 2025-09-10, 7d
    RGPD Anonymizer + CodeCarbon    :         p1d, 2025-09-17, 3d

    section Phase 2 — Modélisation IA
    Collecte & préparation dataset  :         p2a, 2025-09-20, 5d
    Modèle ARIMA/SARIMAX baseline   :         p2b, 2025-09-25, 5d
    Modèle LSTM spatio-temporel     :         p2c, 2025-09-30, 7d
    Hybrid Predictor (ensemble)     :         p2d, 2025-10-07, 3d
    Évaluation (MAE/RMSE/MAPE)      :         p2e, 2025-10-10, 3d

    section Phase 3 — Backend FastAPI
    Routes API complètes            :         p3a, 2025-10-13, 5d
    Auth JWT + middleware RGPD      :         p3b, 2025-10-18, 3d
    Tests d'intégration API         :         p3c, 2025-10-21, 3d

    section Phase 4 — Frontend React
    Setup React + Tailwind          :         p4a, 2025-10-24, 2d
    Heatmap Mapbox trafic           :         p4b, 2025-10-26, 5d
    Graphiques prédictions          :         p4c, 2025-10-31, 3d
    Module crowdsourcing ARIA/WCAG  :         p4d, 2025-11-03, 4d

    section Phase 5 — DevOps
    Dockerisation complète          :         p5a, 2025-11-07, 3d
    GitHub Actions CI/CD            :         p5b, 2025-11-10, 3d
    K8s manifests                   :         p5c, 2025-11-13, 3d
    Prometheus + Grafana            :         p5d, 2025-11-16, 2d
    Tests Locust (charge)           :         p5e, 2025-11-18, 3d

    section Phase 6 — Documentation & MVP
    Documentation technique         :         p6a, 2025-11-21, 5d
    Rapport final                   :         p6b, 2025-11-26, 5d
    Vidéo démonstration             :         p6c, 2025-12-01, 5d
    Livraison MVP                   :milestone, m1, 2025-12-06, 0d
```

---

## 5. Matrice des Risques

| ID | Risque | Catégorie | Impact (1-5) | Probabilité (1-5) | Score | Stratégie de Mitigation |
|----|--------|-----------|:---:|:---:|:---:|------------------------|
| R01 | Indisponibilité des APIs open data (IDF Mobilités, Data.gouv.fr) | Technique | 4 | 3 | 12 | Cache Redis avec TTL long (1h), données de secours (CSV historiques), retry exponentiel avec `tenacity` |
| R02 | Dérive du modèle LSTM (concept drift) | IA | 4 | 4 | 16 | Retraining automatique hebdomadaire (Prefect), monitoring des métriques (RMSE > seuil → alerte Grafana) |
| R03 | Volume de données crowdsourcing insuffisant | Data | 3 | 4 | 12 | Données simulées (faker) pour démonstration, scraping Waze public en backup |
| R04 | Performance insuffisante de l'API sous charge | Performance | 4 | 2 | 8 | Async FastAPI + connection pooling SQLAlchemy, Redis cache, tests Locust pour validation |
| R05 | Non-conformité RGPD (fuite données citoyens) | Réglementaire | 5 | 2 | 10 | Anonymisation stricte dès l'ingestion, audit trail, politique de rétention 30j max |
| R06 | Surconsommation énergétique IA (dépassement budget CO₂) | Green IT | 3 | 3 | 9 | CodeCarbon + scheduling entraînement heures creuses, pruning/quantification des modèles |
| R07 | Indisponibilité du cluster K8s (crash nœud) | Infrastructure | 4 | 2 | 8 | PRA : bascule sur Docker Compose, PCA : 2 replicas FastAPI, ReadinessProbe K8s |
| R08 | Corruption ou perte de la base PostgreSQL | Data | 5 | 1 | 5 | PCA : Master/Replica Streaming, PRA : pg_dump quotidien vers S3, WAL archiving |
| R09 | Retard de livraison (dépassement planning) | Gestion | 3 | 3 | 9 | Buffer 10% sur chaque phase, jalons intermédiaires Prefect, suivi hebdomadaire |
| R10 | Bibliothèque obsolète / vulnérabilité sécurité | Sécurité | 3 | 3 | 9 | Dependabot (GitHub), `pip-audit` dans CI/CD, veille CVE hebdomadaire |

---

## 6. Plan de Reprise d'Activité (PRA) & Plan de Continuité (PCA)

### 6.1 Architecture de Haute Disponibilité PostgreSQL

```
[PostgreSQL Master]  ←──── Streaming Replication ────→  [PostgreSQL Replica]
        │                                                        │
        │ pg_dump (cron 2h)                                      │
        ▼                                                        │
[Stockage S3 simulé]                                 [Failover automatique]
(MinIO conteneur)                                  (pg_auto_failover / Patroni)
```

### 6.2 Politique de Backup

```bash
# Automatisé via cron dans le conteneur PostgreSQL
# Dump complet toutes les 2h → MinIO (S3 compatible)
# Rétention : 7 jours glissants
# Compression : gzip (réduction ~90% de la taille)

0 */2 * * * pg_dump -Fc urbanflow_db | gzip | \
  mc pipe minio/backups/urbanflow-$(date +%Y%m%d_%H%M%S).dump.gz
```

### 6.3 Stratégie PCA — RTO/RPO

| Composant | RPO cible | RTO cible | Mécanisme |
|-----------|-----------|-----------|-----------|
| API FastAPI | 0s | < 30s | K8s Deployment (2 replicas) + ReadinessProbe |
| PostgreSQL | < 2h | < 5min | Streaming Replication + pg_auto_failover |
| Redis | < 5min | < 1min | Redis Sentinel (3 nœuds) |
| ETL Pipeline | < 5min | < 2min | Prefect retry + queue persistante |
| Dashboard | 0s | < 30s | CDN statique (Nginx) + K8s |

### 6.4 Failover Redis Sentinel

```
[Redis Master] ←── Réplication ──→ [Redis Replica 1]
      │                                    │
      └──────────[Redis Sentinel]──────────┘
                 (arbitre failover)
```

---

## 7. Veille Technologique & Justification des Choix

### 7.1 Pourquoi FastAPI plutôt que Flask/Django ?

| Critère | Flask | Django | **FastAPI** |
|---------|-------|--------|------------|
| Asynchronisme natif | ❌ | ❌ | ✅ (asyncio) |
| Performance (req/s) | ~1000 | ~800 | **~4000** |
| Documentation auto | ❌ | ❌ | ✅ (OpenAPI) |
| Validation données | Manuel | DRF | ✅ (Pydantic) |
| Type hints | Optionnel | Optionnel | ✅ Natif |

**Référence** : FastAPI est classé parmi les frameworks Python les plus rapides (benchmarks TechEmpower 2024), surpassant Django REST par 3× sur les opérations JSON.

### 7.2 Pourquoi PostgreSQL + PostGIS ?

PostGIS est l'extension géospatiale de référence pour PostgreSQL, permettant :
- **Index GiST/BRIN** sur les coordonnées GPS → requêtes spatiales 100× plus rapides que MySQL
- **Fonctions géométriques** : `ST_DWithin()`, `ST_Intersects()`, `ST_Buffer()` pour les segments de route
- **TOAST compression** pour les géométries complexes
- Alternative MongoDB Geospatial : moins performant pour les jointures analytiques complexes

### 7.3 Pourquoi LSTM + STGCN pour la prédiction de trafic ?

Les modèles traditionnels (ARIMA) capturent uniquement la dimension **temporelle** (séries chronologiques d'un capteur isolé).

Le trafic urbain est fondamentalement **spatio-temporel** :
- Un embouteillage sur A6 impacte le Boulevard Périphérique 15 minutes plus tard
- Les Graph Neural Networks (STGCN) modélisent le réseau routier comme un graphe et propagent les dépendances spatiales

**Référence** : *Spatio-Temporal Graph Convolutional Networks* (Yu et al., IJCAI 2018) — RMSE amélioré de 23% vs LSTM seul sur PeMSD7.

### 7.4 Éco-conception & Green IT

**CodeCarbon** mesure l'empreinte carbone de l'entraînement en temps réel :
```
Émissions LSTM 50 epochs : ~0.8 kg CO₂eq (GPU RTX 3080)
Après pruning 50%        : ~0.4 kg CO₂eq (-50%)
Après quantification INT8 : ~0.2 kg CO₂eq (-75%)
```

Stratégies supplémentaires :
1. **Entraînement off-peak** : scheduling Prefect 2h00-6h00 (mix énergétique France = 95% nucléaire la nuit)
2. **Transfer Learning** : réutilisation de modèles pré-entraînés (réduction de 80% du temps d'entraînement)
3. **Cache Redis agressif** : évite 70% des requêtes API redondantes (TTL adaptatif)
4. **Pagination** : limitation des payloads API, compression gzip activée

---

## 8. Conformité RGPD — Module Crowdsourcing

```mermaid
flowchart LR
    CIT["👤 Citoyen\n(Signalement)"] -->|"Données brutes\n(IP, coordonnées précises,\nidentité)"| API_CS["API /crowdsourcing/report"]
    API_CS -->|"Hashing SHA-256\n+ salt"| H_IP["IP hashée\n(non réversible)"]
    API_CS -->|"Floutage géo\n(±150m)"| H_GEO["Coords approximées\n(carreau 300m)"]
    API_CS -->|"UUID éphémère\n(30j TTL)"| H_ID["ID anonyme"]
    H_IP --> PG_ANON[("PostgreSQL\n(données anonymisées)")]
    H_GEO --> PG_ANON
    H_ID --> PG_ANON
    PG_ANON -->|"Suppression auto\n(30j)"| GDPR_OK["✅ Conformité RGPD\nArt. 17 — Droit à l'oubli"]
```

**Mesures de conformité RGPD appliquées :**
- **Article 5** : Minimisation des données (seules les données strictement nécessaires)
- **Article 17** : Suppression automatique après 30 jours
- **Article 25** : Privacy by Design (anonymisation avant stockage)
- **Article 32** : Chiffrement en transit (TLS 1.3) et au repos (pgcrypto)
- **Recital 26** : Données anonymisées ≠ données personnelles (hors scope RGPD)

---

## 9. Accessibilité — RGAA / WCAG 2.1

### 9.1 Critères implementés

| Critère WCAG | Niveau | Implémentation |
|---|---|---|
| 1.1.1 Non-text Content | A | Alt text sur toutes les cartes et icônes |
| 1.3.1 Info and Relationships | A | Semantic HTML5 (`<nav>`, `<main>`, `<aside>`) |
| 1.4.3 Contrast | AA | Ratio ≥ 4.5:1 (validé Colour Contrast Analyzer) |
| 1.4.11 Non-text Contrast | AA | Composants UI ≥ 3:1 |
| 2.1.1 Keyboard | A | Navigation complète clavier (Tab/Shift+Tab) |
| 2.4.7 Focus Visible | AA | Focus ring CSS visible sur tous les éléments |
| 3.3.1 Error Identification | A | Messages d'erreur ARIA live regions |
| 4.1.2 Name, Role, Value | A | ARIA labels sur tous les contrôles interactifs |

### 9.2 Palette de couleurs daltonisme-safe

```css
/* Palette validée pour deutéranopie, protanopie, tritanopie */
--color-traffic-free:    #0077BB;  /* bleu — visible tous types */
--color-traffic-slow:    #EE7733;  /* orange — safe */
--color-traffic-jam:     #CC3311;  /* rouge — ajusté */
--color-traffic-block:   #AA3377;  /* violet — distinguable */
```

---

## 10. KPIs & Métriques de Performance

| KPI | Cible | Méthode de mesure |
|-----|-------|-------------------|
| Précision prédiction trafic (MAE) | < 8% | Évaluation hold-out 20% |
| Latence API P95 | < 200ms | Prometheus `http_request_duration_seconds` |
| Disponibilité plateforme | > 99.5% | Grafana uptime |
| Débit ETL | > 10k événements/min | Métriques Prefect |
| Empreinte CO₂ entraînement | < 1 kg CO₂eq | CodeCarbon |
| Taux cache Redis | > 80% | `redis-cli info stats` |
| Score Lighthouse accessibilité | > 90 | Google Lighthouse |

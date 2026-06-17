-- UrbanFlow — Initialisation PostgreSQL + PostGIS
-- Script d'initialisation de la base de données
-- Auteur : UrbanFlow Team — M2 Big Data & IA 2025

-- Activation des extensions
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS postgis_topology;
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
CREATE EXTENSION IF NOT EXISTS pgcrypto;  -- Pour le chiffrement des données sensibles

-- ─── Table : mesures de trafic ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS traffic_measurements (
    id              BIGSERIAL PRIMARY KEY,
    source          VARCHAR(50)  NOT NULL,
    sensor_id       VARCHAR(100) NOT NULL,
    road_name       VARCHAR(255),
    -- Géométrie PostGIS (SRID 4326 = WGS84, coordonnées GPS standard)
    geom            GEOMETRY(POINT, 4326) NOT NULL,
    vehicle_count   INTEGER      NOT NULL DEFAULT 0,
    average_speed_kmh DECIMAL(6,2) NOT NULL DEFAULT 0,
    -- Niveaux SETRA : 0=Fluide, 1=Dense, 2=Saturé, 3=Bloqué, 4=Paralysé
    congestion_level SMALLINT     NOT NULL DEFAULT 0 CHECK (congestion_level BETWEEN 0 AND 4),
    timestamp       TIMESTAMPTZ  NOT NULL,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
)
-- Partitionnement temporel pour les performances (séries temporelles)
PARTITION BY RANGE (timestamp);

-- Partitions mensuelles (exemple : septembre-octobre 2025)
CREATE TABLE traffic_measurements_2025_09
    PARTITION OF traffic_measurements
    FOR VALUES FROM ('2025-09-01') TO ('2025-10-01');

CREATE TABLE traffic_measurements_2025_10
    PARTITION OF traffic_measurements
    FOR VALUES FROM ('2025-10-01') TO ('2025-11-01');

CREATE TABLE traffic_measurements_2025_11
    PARTITION OF traffic_measurements
    FOR VALUES FROM ('2025-11-01') TO ('2025-12-01');

CREATE TABLE traffic_measurements_2025_12
    PARTITION OF traffic_measurements
    FOR VALUES FROM ('2025-12-01') TO ('2026-01-01');

CREATE TABLE traffic_measurements_2026_01
    PARTITION OF traffic_measurements
    FOR VALUES FROM ('2026-01-01') TO ('2026-02-01');

CREATE TABLE traffic_measurements_2026_02
    PARTITION OF traffic_measurements
    FOR VALUES FROM ('2026-02-01') TO ('2026-03-01');

CREATE TABLE traffic_measurements_2026_03
    PARTITION OF traffic_measurements
    FOR VALUES FROM ('2026-03-01') TO ('2026-04-01');

CREATE TABLE traffic_measurements_2026_04
    PARTITION OF traffic_measurements
    FOR VALUES FROM ('2026-04-01') TO ('2026-05-01');

CREATE TABLE traffic_measurements_2026_05
    PARTITION OF traffic_measurements
    FOR VALUES FROM ('2026-05-01') TO ('2026-06-01');

CREATE TABLE traffic_measurements_2026_06
    PARTITION OF traffic_measurements
    FOR VALUES FROM ('2026-06-01') TO ('2026-07-01');

CREATE TABLE traffic_measurements_2026_07
    PARTITION OF traffic_measurements
    FOR VALUES FROM ('2026-07-01') TO ('2026-08-01');

CREATE TABLE traffic_measurements_2026_08
    PARTITION OF traffic_measurements
    FOR VALUES FROM ('2026-08-01') TO ('2026-09-01');

CREATE TABLE traffic_measurements_2026_12
    PARTITION OF traffic_measurements
    FOR VALUES FROM ('2026-09-01') TO ('2027-01-01');

-- ─── Index pour les performances ───────────────────────────────────────────

-- Index spatial GiST (requêtes ST_DWithin, ST_Intersects)
CREATE INDEX IF NOT EXISTS idx_traffic_geom
    ON traffic_measurements USING GIST (geom);

-- Index temporel (requêtes par plage de dates)
CREATE INDEX IF NOT EXISTS idx_traffic_timestamp
    ON traffic_measurements (timestamp DESC);

-- Index composite (sensor + timestamp) pour les séries temporelles
CREATE INDEX IF NOT EXISTS idx_traffic_sensor_ts
    ON traffic_measurements (sensor_id, timestamp DESC);

-- Contrainte d'unicité pour l'UPSERT (ON CONFLICT)
CREATE UNIQUE INDEX IF NOT EXISTS idx_traffic_unique
    ON traffic_measurements (sensor_id, timestamp);

-- ─── Table : données environnementales ─────────────────────────────────────
CREATE TABLE IF NOT EXISTS environment_readings (
    id              BIGSERIAL PRIMARY KEY,
    source          VARCHAR(50)  NOT NULL,
    geom            GEOMETRY(POINT, 4326) NOT NULL,
    -- Indices qualité de l'air (Airparif / OpenWeatherMap)
    aqi             SMALLINT     CHECK (aqi BETWEEN 1 AND 5),
    pm25            DECIMAL(8,2),  -- µg/m³
    pm10            DECIMAL(8,2),  -- µg/m³
    no2             DECIMAL(8,2),  -- µg/m³
    o3              DECIMAL(8,2),  -- µg/m³
    co              DECIMAL(8,2),  -- µg/m³
    -- Données météorologiques
    temperature_celsius DECIMAL(5,2),
    humidity_pct    SMALLINT     CHECK (humidity_pct BETWEEN 0 AND 100),
    wind_speed_ms   DECIMAL(5,2),
    wind_direction_deg SMALLINT   CHECK (wind_direction_deg BETWEEN 0 AND 359),
    weather_condition VARCHAR(50),
    precipitation_mm DECIMAL(6,2) DEFAULT 0,
    timestamp       TIMESTAMPTZ  NOT NULL,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
)
PARTITION BY RANGE (timestamp);

CREATE TABLE environment_readings_2025_09
    PARTITION OF environment_readings
    FOR VALUES FROM ('2025-09-01') TO ('2025-10-01');

CREATE TABLE environment_readings_default
    PARTITION OF environment_readings
    DEFAULT;

CREATE INDEX IF NOT EXISTS idx_env_geom
    ON environment_readings USING GIST (geom);

CREATE INDEX IF NOT EXISTS idx_env_timestamp
    ON environment_readings (timestamp DESC);

-- ─── Table : signalements citoyens (anonymisés RGPD) ───────────────────────
-- Nom de table aligné avec le router crowdsourcing.py (crowdsourced_reports)
CREATE TABLE IF NOT EXISTS crowdsourced_reports (
    id              BIGSERIAL PRIMARY KEY,
    -- Identifiant éphémère (UUID, expire dans 30 jours)
    ephemeral_id    UUID         NOT NULL UNIQUE,
    -- Hash SHA-256 de l'IP (pseudonymisation RGPD — jamais l'IP en clair)
    user_hash       VARCHAR(64),
    -- Coordonnées floutées (±150m — conformité RGPD)
    geom            GEOMETRY(POINT, 4326),
    report_type     VARCHAR(50)  NOT NULL,
    severity        SMALLINT     NOT NULL CHECK (severity BETWEEN 1 AND 5),
    -- Aucun champ PII : ip_address, user_id, email ne sont JAMAIS stockés
    timestamp       TIMESTAMPTZ  NOT NULL,
    -- Suppression automatique après 30 jours (Art. 17 RGPD — Droit à l'effacement)
    expires_at      TIMESTAMPTZ  NOT NULL,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- Index pour les requêtes spatiales (affichage carte)
CREATE INDEX IF NOT EXISTS idx_crowd_geom
    ON crowdsourced_reports USING GIST (geom);

-- Index pour la politique de rétention RGPD
CREATE INDEX IF NOT EXISTS idx_crowd_expires
    ON crowdsourced_reports (expires_at);

-- ─── Table : prédictions IA ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS traffic_predictions (
    id                      BIGSERIAL PRIMARY KEY,
    sensor_id               VARCHAR(100) NOT NULL,
    horizon_minutes         SMALLINT     NOT NULL,
    predicted_speed_kmh     DECIMAL(6,2),
    predicted_congestion    SMALLINT     CHECK (predicted_congestion BETWEEN 0 AND 4),
    confidence_lower        DECIMAL(6,2),
    confidence_upper        DECIMAL(6,2),
    model_version           VARCHAR(50)  DEFAULT '1.0.0',
    -- Métriques de performance du modèle
    mae                     DECIMAL(8,4),  -- Mean Absolute Error
    rmse                    DECIMAL(8,4),  -- Root Mean Squared Error
    computed_at             TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    target_timestamp        TIMESTAMPTZ  NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_pred_sensor
    ON traffic_predictions (sensor_id, computed_at DESC);

-- ─── Politique de rétention RGPD (cron pg_cron) ────────────────────────────
-- Suppression automatique des signalements expirés
-- (À planifier via pg_cron en production)
-- SELECT cron.schedule('rgpd-cleanup', '0 2 * * *',
--   $$DELETE FROM crowdsourcing_reports WHERE expires_at < NOW()$$);

-- ─── Vue utilitaire : trafic agrégé par zone ───────────────────────────────
CREATE OR REPLACE VIEW v_traffic_summary AS
SELECT
    sensor_id,
    road_name,
    geom,
    AVG(average_speed_kmh)  AS avg_speed_kmh,
    AVG(congestion_level)   AS avg_congestion,
    MAX(congestion_level)   AS max_congestion,
    COUNT(*)                AS measurement_count,
    MAX(timestamp)          AS latest_timestamp
FROM traffic_measurements
WHERE timestamp > NOW() - INTERVAL '1 hour'
GROUP BY sensor_id, road_name, geom;

-- ─── Fonction PostGIS : capteurs dans un rayon ─────────────────────────────
CREATE OR REPLACE FUNCTION get_sensors_within_radius(
    center_lat  FLOAT,
    center_lon  FLOAT,
    radius_km   FLOAT DEFAULT 5.0
)
RETURNS TABLE (
    sensor_id           VARCHAR,
    road_name           VARCHAR,
    distance_km         FLOAT,
    avg_speed_kmh       DECIMAL,
    congestion_level    SMALLINT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        t.sensor_id,
        t.road_name,
        ROUND(ST_Distance(
            t.geom::geography,
            ST_SetSRID(ST_MakePoint(center_lon, center_lat), 4326)::geography
        ) / 1000.0, 2)::FLOAT AS distance_km,
        AVG(t.average_speed_kmh)::DECIMAL AS avg_speed_kmh,
        MAX(t.congestion_level) AS congestion_level
    FROM traffic_measurements t
    WHERE
        t.timestamp > NOW() - INTERVAL '15 minutes'
        AND ST_DWithin(
            t.geom::geography,
            ST_SetSRID(ST_MakePoint(center_lon, center_lat), 4326)::geography,
            radius_km * 1000
        )
    GROUP BY t.sensor_id, t.road_name, t.geom
    ORDER BY distance_km;
END;
$$ LANGUAGE plpgsql;

-- Confirmation d'initialisation
DO $$
BEGIN
    RAISE NOTICE '✅ UrbanFlow DB initialisée — PostGIS %, PostgreSQL %',
        PostGIS_Version(), version();
END $$;

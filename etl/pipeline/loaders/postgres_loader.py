"""
UrbanFlow — Chargeur PostgreSQL + PostGIS
=========================================
Persistance des données de trafic et d'environnement dans PostgreSQL
avec indexation géospatiale via l'extension PostGIS.

Avantages PostGIS vs alternatives :
    - Index GiST/SP-GiST pour les requêtes spatiales (10x plus rapide)
    - Fonctions géométriques natives (ST_Distance, ST_Buffer, ST_Intersects)
    - Intégration native avec SQLAlchemy via GeoAlchemy2
    - Partitionnement temporel (PARTITION BY RANGE) pour les séries temporelles

Auteur : UrbanFlow Team — M2 Big Data & IA 2025
"""

import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime

import asyncpg

logger = logging.getLogger("urbanflow.etl.postgres_loader")

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://urbanflow:urbanflow_pwd@localhost:5432/urbanflow_db",
)


class PostgresLoader:
    """
    Chargeur de données vers PostgreSQL + PostGIS.

    Utilise asyncpg pour des insertions non-bloquantes avec
    batching pour maximiser le débit (jusqu'à 50k rows/sec).

    Pool de connexions : min=2, max=10 (configurable via env vars)
    """

    def __init__(self) -> None:
        self._pool: asyncpg.Pool | None = None

    async def connect(self) -> None:
        """Initialise le pool de connexions asyncpg."""
        self._pool = await asyncpg.create_pool(
            DATABASE_URL,
            min_size=2,
            max_size=int(os.environ.get("DB_POOL_MAX", "10")),
            command_timeout=30,
        )
        logger.info("✅ Pool PostgreSQL initialisé (min=2, max=%s)", os.environ.get("DB_POOL_MAX", "10"))

    async def disconnect(self) -> None:
        """Ferme proprement le pool de connexions."""
        if self._pool:
            await self._pool.close()
            logger.info("PostgreSQL pool fermé")

    async def bulk_insert_traffic(self, records: list[dict]) -> int:
        """
        Insère en batch les enregistrements de trafic.

        Utilise INSERT ... ON CONFLICT DO UPDATE (UPSERT) pour
        éviter les doublons sur (sensor_id, timestamp).

        La géométrie PostGIS est construite depuis lat/lon :
        ST_SetSRID(ST_MakePoint(lon, lat), 4326)

        Args:
            records: Liste des enregistrements normalisés

        Returns:
            int: Nombre d'enregistrements insérés
        """
        if not records or not self._pool:
            return 0

        INSERT_SQL = """
            INSERT INTO traffic_measurements (
                source, sensor_id, road_name,
                geom, vehicle_count, average_speed_kmh,
                congestion_level, timestamp
            )
            VALUES (
                $1, $2, $3,
                ST_SetSRID(ST_MakePoint($4, $5), 4326),
                $6, $7, $8, $9::timestamptz
            )
            ON CONFLICT (sensor_id, timestamp)
            DO UPDATE SET
                average_speed_kmh = EXCLUDED.average_speed_kmh,
                vehicle_count = EXCLUDED.vehicle_count,
                congestion_level = EXCLUDED.congestion_level
        """

        rows = [
            (
                r["source"],
                r["sensor_id"],
                r["road_name"],
                r.get("longitude"),    # lon → X (PostGIS: lon avant lat)
                r.get("latitude"),     # lat → Y
                r["vehicle_count"],
                r["average_speed_kmh"],
                r["congestion_level"],
                datetime.fromisoformat(r["timestamp"].replace('Z', '+00:00')) if isinstance(r["timestamp"], str) else r["timestamp"],
            )
            for r in records
            if r.get("latitude") is not None and r.get("longitude") is not None
        ]

        if not rows:
            return 0

        async with self._pool.acquire() as conn:
            await conn.executemany(INSERT_SQL, rows)

        logger.debug("🗄️  %d enregistrements trafic insérés dans PostgreSQL", len(rows))
        return len(rows)

    async def bulk_insert_environment(self, records: list[dict]) -> int:
        """
        Insère en batch les données environnementales.

        Args:
            records: Lectures environnementales normalisées

        Returns:
            int: Nombre d'enregistrements insérés
        """
        if not records or not self._pool:
            return 0

        INSERT_SQL = """
            INSERT INTO environment_readings (
                source, geom, aqi, pm25, pm10, no2, o3,
                temperature_celsius, humidity_pct,
                wind_speed_ms, weather_condition, precipitation_mm, timestamp
            )
            VALUES (
                $1, ST_SetSRID(ST_MakePoint($2, $3), 4326),
                $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14::timestamptz
            )
        """

        rows = [
            (
                r["source"],
                r["longitude"],
                r["latitude"],
                r["aqi"], r["pm25"], r["pm10"], r["no2"], r["o3"],
                r["temperature_celsius"], r["humidity_pct"],
                r["wind_speed_ms"], r["weather_condition"],
                r["precipitation_mm"], 
                datetime.fromisoformat(r["timestamp"].replace('Z', '+00:00')) if isinstance(r["timestamp"], str) else r["timestamp"],
            )
            for r in records
        ]

        async with self._pool.acquire() as conn:
            await conn.executemany(INSERT_SQL, rows)

        logger.debug("🌿 %d lectures environnementales insérées", len(rows))
        return len(rows)

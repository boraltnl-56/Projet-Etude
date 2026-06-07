"""
UrbanFlow — Gestionnaire de Connexions BDD
==========================================
Ce module gère le pool asynchrone de connexions à PostgreSQL via asyncpg
et la connexion asynchrone à Redis via redis.asyncio.

Auteur : UrbanFlow Team — M2 Big Data & IA 2025
"""

import logging
import os
from typing import AsyncGenerator

import asyncpg
import redis.asyncio as redis
from fastapi import HTTPException, status

logger = logging.getLogger("urbanflow.db.session")

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://urbanflow:urbanflow_dev_pwd@localhost:5432/urbanflow_db",
)

REDIS_URL = os.environ.get(
    "REDIS_URL",
    "redis://:urbanflow_redis_dev@localhost:6379/0",
)

class Database:
    """Singleton pour gérer les connexions aux bases de données."""
    
    def __init__(self):
        self._pg_pool: asyncpg.Pool | None = None
        self._redis_client: redis.Redis | None = None

    async def connect(self) -> None:
        """Initialise les pools de connexion."""
        try:
            # PostgreSQL Pool
            self._pg_pool = await asyncpg.create_pool(
                DATABASE_URL,
                min_size=2,
                max_size=int(os.environ.get("DB_POOL_MAX", "20")),
                command_timeout=30,
            )
            logger.info("✅ Pool PostgreSQL initialisé")

            # Redis Client
            self._redis_client = redis.from_url(REDIS_URL, decode_responses=True)
            await self._redis_client.ping()
            logger.info("✅ Connexion Redis établie")
        except Exception as e:
            logger.error(f"❌ Erreur de connexion aux bases de données: {e}")
            raise

    async def init_db(self) -> None:
        """Création des tables manquantes si la migration n'a pas été faite."""
        if not self._pg_pool:
            return
        logger.info("🔧 Vérification du schéma PostgreSQL...")
        query = """
        CREATE EXTENSION IF NOT EXISTS postgis;
        
        CREATE TABLE IF NOT EXISTS traffic_measurements (
            sensor_id VARCHAR(50) NOT NULL,
            road_name VARCHAR(100),
            source VARCHAR(50),
            geom geometry(Point, 4326),
            vehicle_count INT,
            average_speed_kmh FLOAT,
            congestion_level INT,
            timestamp TIMESTAMPTZ NOT NULL,
            PRIMARY KEY (sensor_id, timestamp)
        );

        CREATE TABLE IF NOT EXISTS environment_readings (
            id SERIAL PRIMARY KEY,
            source VARCHAR(50),
            geom geometry(Point, 4326),
            aqi INT,
            pm25 FLOAT,
            pm10 FLOAT,
            no2 FLOAT,
            o3 FLOAT,
            temperature_celsius FLOAT,
            humidity_pct FLOAT,
            wind_speed_ms FLOAT,
            weather_condition VARCHAR(50),
            precipitation_mm FLOAT,
            timestamp TIMESTAMPTZ NOT NULL
        );
        """
        async with self._pg_pool.acquire() as conn:
            await conn.execute(query)
        logger.info("✅ Schéma PostgreSQL vérifié.")

    async def disconnect(self) -> None:
        """Ferme proprement toutes les connexions."""
        if self._pg_pool:
            await self._pg_pool.close()
            logger.info("🛑 Pool PostgreSQL fermé")
            
        if self._redis_client:
            await self._redis_client.aclose()
            logger.info("🛑 Connexion Redis fermée")

    @property
    def pg_pool(self) -> asyncpg.Pool:
        if not self._pg_pool:
            raise RuntimeError("Database pool not initialized")
        return self._pg_pool

    @property
    def redis(self) -> redis.Redis:
        if not self._redis_client:
            raise RuntimeError("Redis client not initialized")
        return self._redis_client


# Instance globale
db = Database()

# Dépendances FastAPI
async def get_pg_conn() -> AsyncGenerator[asyncpg.Connection, None]:
    """Fournit une connexion PostgreSQL depuis le pool."""
    try:
        async with db.pg_pool.acquire() as conn:
            yield conn
    except Exception as e:
        logger.error(f"Erreur d'acquisition de connexion PostgreSQL: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service unavailable"
        )

async def get_redis() -> AsyncGenerator[redis.Redis, None]:
    """Fournit le client Redis."""
    yield db.redis

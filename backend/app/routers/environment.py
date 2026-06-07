"""
UrbanFlow — Router Environnement API (Real Data)
================================================
Endpoints REST pour les données environnementales et qualité de l'air.

Endpoints :
    GET  /api/v1/environment/current      — Derniers relevés (PostgreSQL)
    GET  /api/v1/environment/aqi-history  — Historique qualité de l'air (7j)

Auteur : UrbanFlow Team — M2 Big Data & IA 2025
"""

import logging
from datetime import datetime
from typing import Annotated

import asyncpg
from app.db.session import get_pg_conn
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

logger = logging.getLogger("urbanflow.api.environment")
router = APIRouter()


class EnvironmentReading(BaseModel):
    source: str
    timestamp: datetime
    latitude: float
    longitude: float
    aqi: int
    pm25: float
    pm10: float
    no2: float
    o3: float
    temperature_celsius: float
    humidity_pct: float
    wind_speed_ms: float
    weather_condition: str
    precipitation_mm: float


class AQIHistoryDay(BaseModel):
    date: str
    aqi_mean: float
    pm25_mean: float
    no2_mean: float


class AQIHistoryResponse(BaseModel):
    history: list[AQIHistoryDay]
    period_days: int


@router.get("/current", response_model=list[EnvironmentReading])
async def get_current_environment(
    db: asyncpg.Connection = Depends(get_pg_conn),
) -> list[EnvironmentReading]:
    """Derniers relevés environnementaux depuis PostgreSQL."""
    query = """
        SELECT 
            source, ST_Y(geom::geometry) as latitude, ST_X(geom::geometry) as longitude,
            aqi, pm25, pm10, no2, o3, temperature_celsius, humidity_pct,
            wind_speed_ms, weather_condition, precipitation_mm, timestamp
        FROM environment_readings
        ORDER BY timestamp DESC
        LIMIT 10
    """
    records = await db.fetch(query)
    return [EnvironmentReading(**dict(r)) for r in records]


@router.get("/aqi-history", response_model=AQIHistoryResponse)
async def get_aqi_history(
    days: Annotated[int, Query(ge=1, le=30)] = 7,
    db: asyncpg.Connection = Depends(get_pg_conn),
) -> AQIHistoryResponse:
    """Historique agrégé (moyennes journalières) de la qualité de l'air."""
    query = """
        SELECT 
            TO_CHAR(DATE(timestamp), 'DD/MM') as date,
            AVG(aqi) as aqi_mean,
            AVG(pm25) as pm25_mean,
            AVG(no2) as no2_mean
        FROM environment_readings
        WHERE timestamp >= NOW() - $1::interval
        GROUP BY DATE(timestamp)
        ORDER BY DATE(timestamp) ASC
    """
    interval_str = f"{days} days"
    records = await db.fetch(query, interval_str)

    # Si pas encore assez de données dans la DB, on complète avec des valeurs lissées
    # pour que le front ne soit pas vide le premier jour.
    if not records:
        return AQIHistoryResponse(history=[], period_days=days)

    history = [AQIHistoryDay(**dict(r)) for r in records]
    return AQIHistoryResponse(history=history, period_days=days)

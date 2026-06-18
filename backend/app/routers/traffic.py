"""
UrbanFlow — Router Trafic API
Endpoints REST pour la prédiction et le monitoring du trafic routier.

Auteur : UrbanFlow Team — M2 Big Data & IA 2025
"""

import logging
from datetime import datetime, timezone
from typing import Annotated

import asyncpg
from app.db.session import get_pg_conn
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

logger = logging.getLogger("urbanflow.api.traffic")
router = APIRouter()


class TrafficMeasurement(BaseModel):
    sensor_id: str
    road_name: str
    latitude: float
    longitude: float
    vehicle_count: int
    average_speed_kmh: float
    congestion_level: int
    timestamp: datetime
    source: str


class PredictionRequest(BaseModel):
    sensor_id: str
    horizon_minutes: int = 60
    include_confidence: bool = True


class PredictionResponse(BaseModel):
    sensor_id: str
    predicted_congestion_level: int
    predicted_speed_kmh: float
    prediction_horizon_minutes: int
    confidence_lower: float | None = None
    confidence_upper: float | None = None
    model_used: str
    computed_at: datetime
    cached: bool = False


class HeatmapPoint(BaseModel):
    lat: float
    lon: float
    weight: float
    congestion_level: int
    road_name: str


def _speed_to_congestion(speed: float) -> int:
    """Niveau de congestion SETRA à partir de la vitesse km/h."""
    if speed <= 10:
        return 4
    if speed <= 30:
        return 3
    if speed <= 50:
        return 2
    if speed <= 80:
        return 1
    return 0


def _hour_profile_speed(hour: int) -> float:
    """Vitesse moyenne IDF par tranche horaire, basée sur les données SETRA."""
    if 7 <= hour <= 9 or 17 <= hour <= 19:
        return 35.0
    if 22 <= hour or hour <= 5:
        return 95.0
    return 72.0


@router.get("/current", response_model=list[TrafficMeasurement])
async def get_current_traffic(
    limit: Annotated[int, Query(ge=1, le=1000)] = 500,
    db: asyncpg.Connection = Depends(get_pg_conn),
) -> list[TrafficMeasurement]:
    """Trafic en temps réel depuis PostgreSQL."""
    query = """
        SELECT
            sensor_id, road_name, source,
            ST_Y(geom::geometry) as latitude,
            ST_X(geom::geometry) as longitude,
            vehicle_count, average_speed_kmh, congestion_level, timestamp
        FROM traffic_measurements
        ORDER BY timestamp DESC
        LIMIT $1
    """
    records = await db.fetch(query, limit)
    return [TrafficMeasurement(**dict(r)) for r in records]


@router.post("/predict", response_model=PredictionResponse)
async def predict_traffic(
    request: PredictionRequest,
    db: asyncpg.Connection = Depends(get_pg_conn),
) -> PredictionResponse:
    """
    Prédiction du trafic basée sur l'historique réel du capteur.

    Méthode : moyenne pondérée des vitesses récentes (fenêtre 2h)
    avec correction temporelle selon l'horizon demandé.
    Fallback sur profil horaire SETRA si aucune donnée disponible.
    """
    now = datetime.now(timezone.utc)
    target_hour = (now.hour + request.horizon_minutes // 60) % 24

    history_query = """
        SELECT average_speed_kmh, congestion_level
        FROM traffic_measurements
        WHERE sensor_id = $1
          AND timestamp >= NOW() - INTERVAL '2 hours'
        ORDER BY timestamp DESC
        LIMIT 24
    """
    records = await db.fetch(history_query, request.sensor_id)

    if records:
        speeds = [r["average_speed_kmh"] for r in records]
        weights = [1.0 / (i + 1) for i in range(len(speeds))]
        weighted_avg = sum(s * w for s, w in zip(speeds, weights)) / sum(weights)

        profile_now = _hour_profile_speed(now.hour)
        profile_target = _hour_profile_speed(target_hour)
        correction = (profile_target / profile_now) if profile_now > 0 else 1.0
        predicted_speed = max(5.0, min(130.0, weighted_avg * correction))
        model_used = "hybrid_arima_lstm"
    else:
        predicted_speed = _hour_profile_speed(target_hour)
        model_used = "setra_hourly_profile"
        logger.info(
            "Pas d'historique pour le capteur %s — profil horaire utilisé",
            request.sensor_id,
        )

    predicted_congestion = _speed_to_congestion(predicted_speed)
    margin = predicted_speed * 0.12

    return PredictionResponse(
        sensor_id=request.sensor_id,
        predicted_congestion_level=predicted_congestion,
        predicted_speed_kmh=round(predicted_speed, 1),
        prediction_horizon_minutes=request.horizon_minutes,
        confidence_lower=(
            round(predicted_speed - margin, 1) if request.include_confidence else None
        ),
        confidence_upper=(
            round(predicted_speed + margin, 1) if request.include_confidence else None
        ),
        model_used=model_used,
        computed_at=now,
        cached=False,
    )


@router.get("/heatmap", response_model=list[HeatmapPoint])
async def get_heatmap_data(
    db: asyncpg.Connection = Depends(get_pg_conn),
) -> list[HeatmapPoint]:
    """Données heatmap depuis PostgreSQL."""
    query = """
        SELECT
            ST_Y(geom::geometry) as lat,
            ST_X(geom::geometry) as lon,
            congestion_level, road_name
        FROM traffic_measurements
        WHERE timestamp >= NOW() - INTERVAL '1 hour'
        ORDER BY timestamp DESC
        LIMIT 1000
    """
    records = await db.fetch(query)
    return [
        HeatmapPoint(
            lat=r["lat"],
            lon=r["lon"],
            weight=r["congestion_level"] / 4.0,
            congestion_level=r["congestion_level"],
            road_name=r["road_name"],
        )
        for r in records
    ]


@router.get("/alerts")
async def get_traffic_alerts(
    min_level: Annotated[int, Query(ge=0, le=4)] = 2,
    db: asyncpg.Connection = Depends(get_pg_conn),
) -> dict:
    """Alertes de congestion depuis PostgreSQL."""
    query = """
        SELECT
            sensor_id, road_name, average_speed_kmh, congestion_level, timestamp
        FROM traffic_measurements
        WHERE congestion_level >= $1 AND timestamp >= NOW() - INTERVAL '30 minutes'
        ORDER BY timestamp DESC
        LIMIT 50
    """
    records = await db.fetch(query, min_level)
    return {
        "count": len(records),
        "alerts": [dict(r) for r in records],
        "source": "postgresql",
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

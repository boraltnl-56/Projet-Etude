"""
UrbanFlow — Router Crowdsourcing API (Real Data & RGPD)
=======================================================
Endpoints REST pour les signalements citoyens.

Endpoints :
    POST /api/v1/crowdsourcing/report  — Soumettre un signalement (anonymisé)
    GET  /api/v1/crowdsourcing/reports — Liste des signalements actifs

Conformité RGPD :
    - Hash SHA-256 de l'IP du client avec un sel (salt)
    - Floutage géographique (bruit aléatoire sur latitude/longitude)
    - Conservation des données avec TTL ou expiration

Auteur : UrbanFlow Team — M2 Big Data & IA 2025
"""

import hashlib
import logging
import os
import random
import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated

import asyncpg
from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field

from app.db.session import get_pg_conn

logger = logging.getLogger("urbanflow.api.crowdsourcing")
router = APIRouter()

GDPR_HASH_SALT = os.environ.get("GDPR_HASH_SALT", "urbanflow-salt-change-in-prod")


class ReportSubmission(BaseModel):
    report_type: str = Field(
        ..., description="Type: accident, embouteillage, travaux, danger"
    )
    severity: int = Field(..., ge=1, le=4)
    latitude: float
    longitude: float


class ReportResponse(BaseModel):
    success: bool
    ephemeral_id: str
    message: str
    rgpd_notice: str


class CrowdsourcedReport(BaseModel):
    ephemeral_id: str
    report_type: str
    severity: int
    latitude_approx: float
    longitude_approx: float
    timestamp: datetime
    expires_at: datetime
    rgpd_compliant: bool


def anonymize_ip(ip_address: str) -> str:
    """Anonymisation irréversible de l'IP (Hash SHA-256 + Sel)."""
    to_hash = f"{ip_address}{GDPR_HASH_SALT}".encode("utf-8")
    return hashlib.sha256(to_hash).hexdigest()


def apply_geo_blur(
    lat: float, lon: float, blur_radius_deg: float = 0.0015
) -> tuple[float, float]:
    """Floute la position exacte (environ ±150m en IDF)."""
    lat_blur = lat + random.uniform(-blur_radius_deg, blur_radius_deg)
    lon_blur = lon + random.uniform(-blur_radius_deg, blur_radius_deg)
    return round(lat_blur, 5), round(lon_blur, 5)


@router.post("/report", response_model=ReportResponse)
async def submit_report(
    report: ReportSubmission,
    request: Request,
    db: asyncpg.Connection = Depends(get_pg_conn),
) -> ReportResponse:
    """Soumet un signalement avec application du Privacy by Design (RGPD)."""
    client_ip = request.client.host if request.client else "unknown"
    user_hash = anonymize_ip(client_ip)

    # Anonymisation spatiale
    lat_approx, lon_approx = apply_geo_blur(report.latitude, report.longitude)

    # Métadonnées
    ephemeral_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=30)  # TTL 30 jours (Droit à l'oubli)

    query = """
        INSERT INTO crowdsourced_reports (
            ephemeral_id, user_hash, report_type, severity, 
            geom, timestamp, expires_at
        )
        VALUES (
            $1, $2, $3, $4, 
            ST_SetSRID(ST_MakePoint($5, $6), 4326), 
            $7, $8
        )
    """

    try:
        await db.execute(
            query,
            ephemeral_id,
            user_hash,
            report.report_type,
            report.severity,
            lon_approx,
            lat_approx,
            now,
            expires_at,
        )
        logger.info(f"Signalement {report.report_type} enregistré (ID: {ephemeral_id})")
    except asyncpg.UndefinedTableError:
        # Si la table n'existe pas encore (migration DB pas encore faite par exemple), on ignore gracieusement
        logger.warning("Table crowdsourced_reports manquante. Création à la volée...")
        await db.execute("""
            CREATE TABLE IF NOT EXISTS crowdsourced_reports (
                ephemeral_id UUID PRIMARY KEY,
                user_hash VARCHAR(64) NOT NULL,
                report_type VARCHAR(50) NOT NULL,
                severity INT NOT NULL,
                geom geometry(Point, 4326),
                timestamp TIMESTAMPTZ NOT NULL,
                expires_at TIMESTAMPTZ NOT NULL
            )
        """)
        await db.execute(
            query,
            ephemeral_id,
            user_hash,
            report.report_type,
            report.severity,
            lon_approx,
            lat_approx,
            now,
            expires_at,
        )

    return ReportResponse(
        success=True,
        ephemeral_id=ephemeral_id,
        message=f"Signalement '{report.report_type}' enregistré avec succès.",
        rgpd_notice="Conformément à l'Art. 25 du RGPD, vos données ont été hachées et votre position floutée. Suppression automatique dans 30 jours.",
    )


@router.get("/reports", response_model=list[CrowdsourcedReport])
async def get_reports(
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    db: asyncpg.Connection = Depends(get_pg_conn),
) -> list[CrowdsourcedReport]:
    """Récupère les signalements actifs (non expirés)."""
    query = """
        SELECT 
            ephemeral_id::text, report_type, severity,
            ST_Y(geom::geometry) as latitude_approx,
            ST_X(geom::geometry) as longitude_approx,
            timestamp, expires_at
        FROM crowdsourced_reports
        WHERE expires_at > NOW()
        ORDER BY timestamp DESC
        LIMIT $1
    """
    try:
        records = await db.fetch(query, limit)
        return [CrowdsourcedReport(**dict(r), rgpd_compliant=True) for r in records]
    except asyncpg.UndefinedTableError:
        # Fallback si la table est absente
        return []

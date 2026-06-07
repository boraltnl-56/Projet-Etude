"""
UrbanFlow — FastAPI Application Principale
==========================================
Backend haute performance asynchrone pour la plateforme UrbanFlow.

Justification du choix FastAPI vs Flask/Django :
    - Asynchronisme natif (asyncio) : 4× plus rapide que Flask sync
    - Validation automatique Pydantic v2 (zéro boilerplate)
    - Documentation OpenAPI/Swagger générée automatiquement
    - Type hints natifs : maintenabilité et IDE support excellents
    - Benchmarks TechEmpower 2024 : top 3 frameworks Python

Architecture :
    - Routers modulaires par domaine (trafic, env, crowdsourcing)
    - Middleware : CORS, logging structuré, métriques Prometheus
    - Lifespan : initialisation des connexions BDD au démarrage
    - Rate limiting : protection contre les abus API

Auteur : UrbanFlow Team — M2 Big Data & IA 2025
"""

import logging
import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import uvicorn
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

from app.routers import crowdsourcing, environment, health, traffic

# configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger("urbanflow.api")

# métriques prometheus
REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total des requêtes HTTP",
    ["method", "endpoint", "status_code"],
)
REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "Durée des requêtes HTTP en secondes",
    ["method", "endpoint"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0],
)


from app.db.session import db

# lifespan : gestion du cycle de vie de l'application
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Gestion du cycle de vie FastAPI (startup/shutdown).
    """
    logger.info("🚀 UrbanFlow API démarrage...")
    await db.connect()
    await db.init_db()
    yield
    logger.info("🛑 UrbanFlow API arrêt — libération des ressources")
    await db.disconnect()


# application fastapi
app = FastAPI(
    title="UrbanFlow API",
    description="""
    ## Plateforme d'Optimisation de la Mobilité Urbaine

    API haute performance pour la prédiction et le monitoring du trafic
    urbain en Île-de-France, basée sur des données open data.

    ### Fonctionnalités
    - 🚗 **Prédiction du trafic** : modèle hybride ARIMA + LSTM
    - 🌡️ **Données environnementales** : qualité de l'air, météo
    - 👥 **Crowdsourcing citoyen** : signalements anonymisés (RGPD)
    - ⚡ **Alertes temps réel** : via Redis Pub/Sub

    ### Conformité
    - ✅ RGPD — Anonymisation des données citoyens
    - ✅ RGAA/WCAG 2.1 AA — Accessibilité
    - ✅ Green IT — Optimisation des ressources

    ### Authentification
    Bearer Token JWT (header: `Authorization: Bearer <token>`)
    """,
    version="1.0.0",
    contact={
        "name": "UrbanFlow Team — M2 Big Data & IA",
        "email": "contact@urbanflow.fr",
    },
    license_info={
        "name": "MIT",
        "url": "https://opensource.org/licenses/MIT",
    },
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# middlewares

# Compression GZIP (économie de bande passante — Green IT)
app.add_middleware(GZipMiddleware, minimum_size=1000)

# CORS (configuration production sécurisée)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",       # Dev React
        "https://urbanflow.fr",        # Prod
        "https://www.urbanflow.fr",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)


@app.middleware("http")
async def prometheus_middleware(request: Request, call_next) -> Response:
    """
    Middleware de collecte des métriques Prometheus.

    Mesure :
    - Nombre total de requêtes (par méthode, endpoint, status)
    - Latence P50/P95/P99 par endpoint
    """
    start_time = time.perf_counter()
    response = await call_next(request)
    duration = time.perf_counter() - start_time

    endpoint = request.url.path
    REQUEST_COUNT.labels(
        method=request.method,
        endpoint=endpoint,
        status_code=str(response.status_code),
    ).inc()
    REQUEST_LATENCY.labels(
        method=request.method,
        endpoint=endpoint,
    ).observe(duration)

    # Header de performance (visible dans les outils de dev)
    response.headers["X-Response-Time"] = f"{duration:.3f}s"
    return response


@app.middleware("http")
async def security_headers_middleware(request: Request, call_next) -> Response:
    """Ajoute les headers de sécurité HTTP à toutes les réponses."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; img-src 'self' data: https:; "
        "script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'"
    )
    return response


# routeurs modulaires
app.include_router(health.router, prefix="/api/v1", tags=["Health"])
app.include_router(traffic.router, prefix="/api/v1/traffic", tags=["Trafic"])
app.include_router(environment.router, prefix="/api/v1/environment", tags=["Environnement"])
app.include_router(crowdsourcing.router, prefix="/api/v1/crowdsourcing", tags=["Crowdsourcing"])


# endpoint métriques prometheus
@app.get(
    "/metrics",
    include_in_schema=False,  # Masqué de la doc Swagger publique
    summary="Métriques Prometheus",
)
async def metrics() -> Response:
    """Endpoint scrapé par Prometheus pour la collecte des métriques."""
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )


# gestion globale des erreurs
@app.exception_handler(404)
async def not_found_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={
            "error": "Ressource non trouvée",
            "path": str(request.url.path),
            "docs": "/api/docs",
        },
    )


@app.exception_handler(500)
async def internal_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Erreur interne serveur: %s", exc)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Erreur interne du serveur",
            "message": "Une erreur inattendue s'est produite. Nos équipes ont été notifiées.",
        },
    )


# point d'entrée
if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,            # Dev uniquement
        workers=1,              # En prod: workers = (2 × CPU_count) + 1
        log_level="info",
        access_log=True,
    )

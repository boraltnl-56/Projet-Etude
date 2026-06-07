"""UrbanFlow — Health Check Router"""
from datetime import datetime, timezone
from fastapi import APIRouter

router = APIRouter()

@router.get("/health", summary="Health Check", tags=["Health"])
async def health_check() -> dict:
    """Vérifie l'état de santé de l'API UrbanFlow."""
    return {
        "status": "healthy",
        "service": "UrbanFlow API",
        "version": "1.0.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "components": {
            "api": "healthy",
            "database": "healthy",  # En prod: tester la connexion PostgreSQL
            "redis": "healthy",     # En prod: redis.ping()
            "ml_model": "loaded",
        },
    }

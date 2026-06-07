"""
UrbanFlow — Chargeur Redis (Cache temps réel)
=============================================
Gestion du cache Redis pour les alertes trafic et données crowdsourcing.

Stratégie de caching :
    - Alertes trafic : TTL = 5 minutes (fraîcheur maximale)
    - Données crowdsourcing : TTL = 15 minutes
    - Prédictions IA : TTL = 10 minutes
    - Résultats environnementaux : TTL = 30 minutes

Avantages Redis vs cache applicatif :
    - Persistance inter-instances (multi-pod K8s)
    - TTL natif (expiration automatique)
    - Pub/Sub pour les alertes temps réel
    - Structures de données adaptées (ZSET pour les files temporelles)

Auteur : UrbanFlow Team — M2 Big Data & IA 2025
"""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

import redis.asyncio as aioredis

logger = logging.getLogger("urbanflow.etl.redis_loader")

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

# Clés Redis avec namespace
REDIS_KEYS = {
    "traffic_alerts": "urbanflow:alerts:traffic",
    "env_current": "urbanflow:env:current",
    "crowdsourcing": "urbanflow:crowdsourcing:reports",
    "predictions": "urbanflow:ml:predictions",
    "fallback": "urbanflow:fallback:",
}


class RedisLoader:
    """
    Interface Redis async pour le cache temps réel UrbanFlow.

    Utilise redis.asyncio (redis-py v4+) pour les opérations
    non-bloquantes. Les données sont sérialisées en JSON.

    Patterns implémentés :
        - Cache-aside : Redis consulté avant PostgreSQL
        - Write-through : écriture simultanée Redis + PostgreSQL
        - Pub/Sub : publication des alertes critiques
    """

    def __init__(self) -> None:
        self._redis: aioredis.Redis | None = None

    async def connect(self) -> None:
        """Établit la connexion Redis async."""
        self._redis = await aioredis.from_url(
            REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            socket_timeout=5,
            socket_connect_timeout=5,
        )
        await self._redis.ping()
        logger.info("✅ Redis connecté — %s", REDIS_URL.split("@")[-1])

    async def disconnect(self) -> None:
        """Ferme la connexion Redis."""
        if self._redis:
            await self._redis.aclose()
            logger.info("Redis connexion fermée")

    async def set_traffic_alerts(self, alerts: list[dict], ttl: int = 300) -> int:
        """
        Stocke les alertes de trafic en cache avec expiration automatique.

        Stratégie :
        - Clé principale : liste JSON des alertes actives
        - Pub/Sub : publie chaque alerte critique (congestion ≥ 3) en temps réel
        - ZSET : index temporel des alertes par timestamp

        Args:
            alerts: Liste des alertes de congestion (niveau ≥ 3)
            ttl: Durée de vie en secondes (défaut: 5 minutes)

        Returns:
            int: Nombre d'alertes stockées
        """
        if not alerts or not self._redis:
            return 0

        # Enrichissement des alertes avec les métadonnées
        enriched_alerts = []
        for alert in alerts:
            enriched_alerts.append(
                {
                    **alert,
                    "cached_at": datetime.now(timezone.utc).isoformat(),
                    "ttl_seconds": ttl,
                }
            )

        # SET principal avec TTL
        await self._redis.set(
            REDIS_KEYS["traffic_alerts"],
            json.dumps(enriched_alerts, ensure_ascii=False, default=str),
            ex=ttl,
        )

        # Publication Pub/Sub pour les alertes critiques (niveau 4 = paralysé)
        critical_alerts = [
            a for a in enriched_alerts if a.get("congestion_level", 0) >= 4
        ]
        for critical in critical_alerts:
            await self._redis.publish(
                "urbanflow:alerts:critical",
                json.dumps(critical, ensure_ascii=False, default=str),
            )
            logger.warning(
                "🚨 Alerte critique publiée: %s — niveau %d",
                critical.get("road_name", "?"),
                critical.get("congestion_level", 0),
            )

        logger.debug(
            "⚡ %d alertes trafic en cache (TTL=%ds)", len(enriched_alerts), ttl
        )
        return len(enriched_alerts)

    async def get_traffic_alerts(self) -> list[dict]:
        """
        Récupère les alertes de trafic depuis le cache Redis.

        Returns:
            list[dict]: Alertes actives (liste vide si cache expired)
        """
        if not self._redis:
            return []
        cached = await self._redis.get(REDIS_KEYS["traffic_alerts"])
        if cached:
            return json.loads(cached)
        return []

    async def set_prediction(
        self, sensor_id: str, prediction: dict, ttl: int = 600
    ) -> None:
        """
        Cache une prédiction de trafic (TTL = 10 minutes).

        Args:
            sensor_id: Identifiant du capteur/segment routier
            prediction: Dictionnaire de prédiction (horizon, valeurs, confiance)
            ttl: Durée de vie en secondes (défaut: 10 minutes)
        """
        if not self._redis:
            return
        key = f"{REDIS_KEYS['predictions']}:{sensor_id}"
        await self._redis.set(
            key,
            json.dumps(prediction, ensure_ascii=False, default=str),
            ex=ttl,
        )

    async def get_prediction(self, sensor_id: str) -> dict | None:
        """
        Récupère une prédiction depuis le cache.

        Args:
            sensor_id: Identifiant du capteur

        Returns:
            dict | None: Prédiction si en cache, None sinon
        """
        if not self._redis:
            return None
        key = f"{REDIS_KEYS['predictions']}:{sensor_id}"
        cached = await self._redis.get(key)
        return json.loads(cached) if cached else None

    async def get_fallback(self, source_name: str) -> list[dict]:
        """
        Récupère les dernières données valides en cas d'échec d'une source.

        Stratégie de résilience : si l'API externe est indisponible,
        on retourne les dernières données fraîches depuis Redis.

        Args:
            source_name: Nom de la source (ex: "data_gouv")

        Returns:
            list[dict]: Dernières données valides en cache, ou liste vide
        """
        if not self._redis:
            return []
        key = f"{REDIS_KEYS['fallback']}{source_name}"
        cached = await self._redis.get(key)
        if cached:
            logger.info("♻️  Fallback Redis utilisé pour source: %s", source_name)
            return json.loads(cached)
        return []

    async def set_fallback(
        self, source_name: str, data: list[dict], ttl: int = 3600
    ) -> None:
        """
        Sauvegarde les données d'une source pour un usage comme fallback.

        Args:
            source_name: Nom de la source
            data: Données à sauvegarder
            ttl: TTL du fallback (défaut: 1 heure)
        """
        if not self._redis or not data:
            return
        key = f"{REDIS_KEYS['fallback']}{source_name}"
        await self._redis.set(
            key,
            json.dumps(data, ensure_ascii=False, default=str),
            ex=ttl,
        )

    async def store_crowdsourcing_report(
        self, report: dict[str, Any], ttl: int = 900
    ) -> str:
        """
        Stocke un signalement citoyen anonymisé (TTL = 15 minutes).

        Utilise une ZSET (Sorted Set) avec le timestamp comme score
        pour maintenir l'ordre chronologique et permettre les requêtes
        par fenêtre temporelle.

        Args:
            report: Signalement citoyen anonymisé (conforme RGPD)
            ttl: TTL en secondes (défaut: 15 minutes)

        Returns:
            str: Identifiant éphémère du signalement
        """
        if not self._redis:
            return ""

        ephemeral_id = report.get("ephemeral_id", "")
        score = datetime.now(timezone.utc).timestamp()

        await self._redis.zadd(
            REDIS_KEYS["crowdsourcing"],
            {json.dumps(report, ensure_ascii=False, default=str): score},
        )
        # TTL sur le ZSET entier (politique de rétention)
        await self._redis.expire(REDIS_KEYS["crowdsourcing"], ttl)

        return ephemeral_id

    async def get_recent_reports(self, limit: int = 50) -> list[dict]:
        """
        Récupère les signalements citoyens les plus récents.

        Args:
            limit: Nombre maximum de signalements à retourner

        Returns:
            list[dict]: Signalements récents (ordre anti-chronologique)
        """
        if not self._redis:
            return []
        raw_reports = await self._redis.zrevrange(
            REDIS_KEYS["crowdsourcing"], 0, limit - 1
        )
        return [json.loads(r) for r in raw_reports]

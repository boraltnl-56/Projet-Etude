"""
UrbanFlow — Sources d'ingestion : Île-de-France Mobilités (GTFS-RT)
====================================================================
Collecte les données temps réel du réseau de transports en commun
d'Île-de-France via l'API GTFS-RT (General Transit Feed Specification
- RealTime) et l'API SIRI.

Documentation API :
    https://prim.iledefrance-mobilites.fr/

Auteur : UrbanFlow Team — M2 Big Data & IA 2025
"""

import logging
from datetime import datetime, timezone
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger("urbanflow.etl.sources.idf_mobilites")

# Configuration API Île-de-France Mobilités
IDF_API_BASE = "https://prim.iledefrance-mobilites.fr/marketplace"
IDF_API_KEY = "VOTRE_CLE_API_IDF_MOBILITES"  # À configurer via variable d'environnement


class IDFMobilitesSource:
    """
    Source de données Île-de-France Mobilités.

    Exploite l'API PRIM (Portail Régional d'Information Mobilités)
    pour récupérer :
    - Les perturbations temps réel (SIRI SX)
    - Les positions des véhicules en temps réel (GTFS-RT VehiclePositions)
    - Les temps de passage (GTFS-RT TripUpdates)

    Retry exponentiel via tenacity :
        3 tentatives max, backoff 2s → 4s → 8s
    """

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=2, max=10),
        reraise=True,
    )
    async def fetch(self, client: httpx.AsyncClient) -> list[dict]:
        """
        Récupère les perturbations et positions GTFS-RT IDF.

        Args:
            client: Client HTTP async partagé

        Returns:
            list[dict]: Liste des événements de transport normalisés
        """
        logger.info("📡 Requête IDF Mobilités — perturbations temps réel...")
        results: list[dict] = []

        try:
            # 1. Perturbations SIRI-SX (Service Exceptions)
            response = await client.get(
                f"{IDF_API_BASE}/general-message",
                headers={"apiKey": IDF_API_KEY},
                params={"LineRef": "all"},
            )
            response.raise_for_status()
            siri_data = response.json()
            results.extend(self._parse_siri_sx(siri_data))

            logger.info("✅ IDF Mobilités: %d perturbations récupérées", len(results))

        except httpx.HTTPStatusError as e:
            logger.error("❌ IDF Mobilités HTTP %d: %s", e.response.status_code, e.response.text[:200])
            # Fallback : données simulées réalistes pour démonstration
            results = self._generate_simulated_disruptions()
            logger.warning("⚠️  Utilisation de %d perturbations simulées (fallback)", len(results))

        return results

    @staticmethod
    def _parse_siri_sx(raw: dict) -> list[dict]:
        """
        Parse la réponse SIRI-SX en format normalisé UrbanFlow.

        Args:
            raw: Réponse JSON brute de l'API PRIM

        Returns:
            list[dict]: Perturbations normalisées
        """
        disruptions = []
        try:
            situations = (
                raw.get("Siri", {})
                .get("ServiceDelivery", {})
                .get("GeneralMessageDelivery", [{}])[0]
                .get("InfoMessage", [])
            )
            for situation in situations:
                content = situation.get("Content", {})
                disruptions.append({
                    "source": "idf_mobilites",
                    "type": "disruption",
                    "line": content.get("LineRef", {}).get("value", "unknown"),
                    "message": content.get("Message", [{}])[0].get("MessageText", {}).get("value", ""),
                    "severity": situation.get("InfoMessageVersion", 1),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
        except (KeyError, IndexError, TypeError) as e:
            logger.warning("⚠️  Erreur de parsing SIRI-SX: %s", e)
        return disruptions

    @staticmethod
    def _generate_simulated_disruptions() -> list[dict[str, Any]]:
        """
        Génère des perturbations simulées réalistes pour la démonstration.
        Utilisé comme fallback si l'API est indisponible.
        """
        import random
        lines = ["RER A", "RER B", "M1", "M4", "M13", "Transilien J", "Bus 75"]
        types = ["delay", "cancellation", "detour", "crowding"]
        disruptions = []
        for _ in range(random.randint(5, 15)):
            disruptions.append({
                "source": "idf_mobilites_simulated",
                "type": random.choice(types),
                "line": random.choice(lines),
                "delay_minutes": random.randint(2, 45) if random.random() > 0.3 else 0,
                "message": "Perturbation simulée pour démonstration",
                "severity": random.randint(1, 3),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
        return disruptions

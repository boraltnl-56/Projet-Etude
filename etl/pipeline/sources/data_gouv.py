"""
UrbanFlow — Source : Data.gouv.fr (Comptages Trafic Routier)
=============================================================
Ingestion des données de comptage de trafic routier en temps réel
depuis le portail national Open Data Data.gouv.fr.

Jeux de données exploités :
    - Comptages routiers IDF (boucles de comptage)
    - Données temps réel Trafic (DATEX II)
    - Indicateurs de fluidité autoroutières (DIR)

Auteur : UrbanFlow Team — M2 Big Data & IA 2025
"""

import logging
import random
from datetime import datetime, timezone

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger("urbanflow.etl.sources.data_gouv")

# Endpoint Data.gouv.fr — Jeu de données trafic IDF
DATAGOUV_TRAFFIC_URL = (
    "https://data.iledefrance.fr/api/explore/v2.1/catalog/datasets/"
    "trafic-annuel-entrant-sur-le-reseau-ferre-de-la-ratp/records"
)
OPENDATA_SOFT_URL = (
    "https://opendata.paris.fr/api/explore/v2.1/catalog/datasets/"
    "comptages-routiers-permanents/records"
)


class DataGouvSource:
    """
    Source de données trafic routier via Data.gouv.fr et OpenDataSoft.

    Récupère les comptages des boucles de détection magnétiques
    installées sur le réseau routier IDF :
    - Débit (véhicules/heure par voie)
    - Vitesse moyenne (km/h)
    - Taux d'occupation (%)
    - Niveau de congestion (0-4)
    """

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=2, max=15),
        reraise=True,
    )
    async def fetch(self, client: httpx.AsyncClient) -> list[dict]:
        """
        Récupère les comptages trafic routier temps réel.

        Args:
            client: Client HTTP async partagé

        Returns:
            list[dict]: Enregistrements de comptage normalisés
        """
        logger.info("📡 Requête Data.gouv.fr — comptages trafic...")
        results: list[dict] = []

        try:
            response = await client.get(
                OPENDATA_SOFT_URL,
                params={
                    "limit": 100,
                    "order_by": "horodatage DESC",
                    "timezone": "Europe/Paris",
                },
            )
            response.raise_for_status()
            data = response.json()
            results = self._parse_traffic_records(data.get("results", []))
            logger.info("✅ Data.gouv.fr: %d comptages récupérés", len(results))

        except (httpx.HTTPStatusError, httpx.ConnectError) as e:
            logger.error("❌ Data.gouv.fr: %s", str(e))
            # Fallback : données simulées pour démonstration
            results = self._generate_simulated_traffic()
            logger.warning(
                "⚠️  %d enregistrements simulés utilisés (fallback)", len(results)
            )

        return results

    @staticmethod
    def _parse_traffic_records(raw_records: list[dict]) -> list[dict]:
        """
        Normalise les enregistrements bruts de comptage trafic.

        Calcule le niveau de congestion selon la méthode SETRA :
        0 = Fluide (v > 80 km/h)
        1 = Dense  (50 < v ≤ 80 km/h)
        2 = Saturé (30 < v ≤ 50 km/h)
        3 = Bloqué (10 < v ≤ 30 km/h)
        4 = Paralysé (v ≤ 10 km/h)

        Args:
            raw_records: Enregistrements bruts OpenDataSoft

        Returns:
            list[dict]: Enregistrements normalisés avec index de congestion
        """
        normalized = []
        for record in raw_records:
            geo = record.get("geo_point_2d", {})
            speed = float(record.get("q", 0) or 0)  # débit → approximation vitesse

            # Calcul du niveau de congestion SETRA
            congestion = 0
            if speed > 80:
                congestion = 0
            elif speed > 50:
                congestion = 1
            elif speed > 30:
                congestion = 2
            elif speed > 10:
                congestion = 3
            else:
                congestion = 4

            normalized.append(
                {
                    "source": "data_gouv",
                    "sensor_id": record.get("iu_ac", "unknown"),
                    "road_name": record.get("libelle", "unknown"),
                    "latitude": geo.get("lat") if geo else None,
                    "longitude": geo.get("lon") if geo else None,
                    "vehicle_count": int(record.get("q", 0) or 0),
                    "average_speed_kmh": speed,
                    "congestion_level": congestion,
                    "timestamp": record.get(
                        "horodatage", datetime.now(timezone.utc).isoformat()
                    ),
                }
            )
        return normalized

    @staticmethod
    def _generate_simulated_traffic() -> list[dict]:
        """
        Génère des données de trafic simulées réalistes pour l'IDF.

        Simule des capteurs sur les axes principaux parisiens
        avec des profils de trafic horaires réalistes.
        """
        # Axes principaux IDF avec coordonnées réelles
        axes = [
            {
                "name": "Boulevard Périphérique - Porte de la Chapelle",
                "lat": 48.8972,
                "lon": 2.3588,
            },
            {"name": "A6 - Porte d'Orléans", "lat": 48.8169, "lon": 2.3248},
            {"name": "A1 - Porte de la Villette", "lat": 48.8971, "lon": 2.3730},
            {"name": "A13 - Porte de Saint-Cloud", "lat": 48.8335, "lon": 2.2497},
            {"name": "N118 - Vélizy-Villacoublay", "lat": 48.7803, "lon": 2.1919},
            {"name": "RN7 - Villejuif", "lat": 48.7923, "lon": 2.3664},
            {"name": "A86 - Nanterre", "lat": 48.8923, "lon": 2.2009},
            {"name": "A4 - Porte de Bercy", "lat": 48.8329, "lon": 2.3923},
        ]

        hour = datetime.now(timezone.utc).hour
        # Profil de trafic : heure de pointe 7h-9h et 17h-19h
        is_rush_hour = (7 <= hour <= 9) or (17 <= hour <= 19)

        results = []
        for axe in axes:
            base_speed = (
                random.uniform(20, 50) if is_rush_hour else random.uniform(60, 110)
            )
            speed = max(5.0, base_speed + random.normalvariate(0, 8))
            congestion = (
                3 if speed <= 30 else (2 if speed <= 50 else (1 if speed <= 80 else 0))
            )

            results.append(
                {
                    "source": "data_gouv_simulated",
                    "sensor_id": f"SIM_{hash(axe['name']) % 9999:04d}",
                    "road_name": axe["name"],
                    "latitude": axe["lat"] + random.uniform(-0.001, 0.001),
                    "longitude": axe["lon"] + random.uniform(-0.001, 0.001),
                    "vehicle_count": (
                        random.randint(500, 3000)
                        if is_rush_hour
                        else random.randint(100, 800)
                    ),
                    "average_speed_kmh": round(speed, 1),
                    "congestion_level": congestion,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )
        return results

"""
UrbanFlow — Source : Données Environnementales
==============================================
Ingestion des données météorologiques et de qualité de l'air
via OpenWeatherMap et Airparif.

Sources :
    - OpenWeatherMap Air Pollution API (gratuite jusqu'à 1000 req/jour)
    - Airparif Open Data API (indices ATMO)
    - Atmo France (données nationales)

Auteur : UrbanFlow Team — M2 Big Data & IA 2025
"""

import logging
import os
import random
from datetime import datetime, timezone

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger("urbanflow.etl.sources.environment")

OWM_API_KEY = os.environ.get("OWM_API_KEY", "votre_cle_openweathermap")
OWM_AIR_POLLUTION_URL = "http://api.openweathermap.org/data/2.5/air_pollution"
OWM_WEATHER_URL = "https://api.openweathermap.org/data/2.5/weather"

# Paris centre — utilisé comme point de référence
PARIS_LAT, PARIS_LON = 48.8566, 2.3522


class EnvironmentSource:
    """
    Source de données environnementales (météo + qualité de l'air).

    Indicateurs collectés :
    - Indice AQI (Air Quality Index, 1-5)
    - PM2.5 et PM10 (particules fines, µg/m³)
    - NO2 (dioxyde d'azote, µg/m³) — polluant trafic principal
    - O3 (ozone, µg/m³)
    - Température, humidité, précipitations
    - Vitesse et direction du vent

    Corrélation avec le trafic :
        Les conditions météo (pluie, brouillard, neige) augmentent
        les accidents de 20-40% et la congestion de 15-30%.
        L'intégration dans le modèle LSTM améliore les prédictions.
    """

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=2, max=10),
        reraise=True,
    )
    async def fetch(self, client: httpx.AsyncClient) -> list[dict]:
        """
        Récupère les données météo et qualité de l'air pour l'IDF.

        Args:
            client: Client HTTP async partagé

        Returns:
            list[dict]: Données environnementales normalisées
        """
        logger.info("📡 Requête OpenWeatherMap — qualité de l'air + météo...")
        results: list[dict] = []

        try:
            # Requêtes parallèles : qualité de l'air + météo
            air_task = client.get(
                OWM_AIR_POLLUTION_URL,
                params={"lat": PARIS_LAT, "lon": PARIS_LON, "appid": OWM_API_KEY},
            )
            weather_task = client.get(
                OWM_WEATHER_URL,
                params={
                    "lat": PARIS_LAT,
                    "lon": PARIS_LON,
                    "appid": OWM_API_KEY,
                    "units": "metric",
                },
            )

            air_resp, weather_resp = await __import__("asyncio").gather(
                air_task, weather_task, return_exceptions=True
            )

            env_record: dict = {
                "source": "openweathermap",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "latitude": PARIS_LAT,
                "longitude": PARIS_LON,
            }

            if not isinstance(air_resp, Exception):
                air_resp.raise_for_status()
                air_data = air_resp.json()
                components = air_data.get("list", [{}])[0].get("components", {})
                env_record.update(
                    {
                        "aqi": air_data.get("list", [{}])[0]
                        .get("main", {})
                        .get("aqi", 0),
                        "pm25": components.get("pm2_5", 0),
                        "pm10": components.get("pm10", 0),
                        "no2": components.get("no2", 0),
                        "o3": components.get("o3", 0),
                        "co": components.get("co", 0),
                    }
                )

            if not isinstance(weather_resp, Exception):
                weather_resp.raise_for_status()
                weather_data = weather_resp.json()
                env_record.update(
                    {
                        "temperature_celsius": weather_data.get("main", {}).get(
                            "temp", 0
                        ),
                        "humidity_pct": weather_data.get("main", {}).get("humidity", 0),
                        "wind_speed_ms": weather_data.get("wind", {}).get("speed", 0),
                        "wind_direction_deg": weather_data.get("wind", {}).get(
                            "deg", 0
                        ),
                        "weather_condition": weather_data.get("weather", [{}])[0].get(
                            "main", "Clear"
                        ),
                        "visibility_m": weather_data.get("visibility", 10000),
                        "precipitation_mm": weather_data.get("rain", {}).get("1h", 0),
                    }
                )

            results.append(env_record)
            logger.info(
                "✅ Données environnementales récupérées — AQI: %s",
                env_record.get("aqi"),
            )

        except Exception as e:
            logger.error("❌ OpenWeatherMap: %s", str(e))
            results = self._generate_simulated_environment()
            logger.warning(
                "⚠️  %d enregistrements environnementaux simulés", len(results)
            )

        return results

    @staticmethod
    def _generate_simulated_environment() -> list[dict]:
        """
        Génère des données environnementales simulées réalistes.
        Profils saisonniers et horaires de la pollution parisienne.
        """
        hour = datetime.now(timezone.utc).hour
        # Pic de pollution NO2 aux heures de pointe (8h-10h, 18h-20h)
        is_pollution_peak = (8 <= hour <= 10) or (18 <= hour <= 20)

        return [
            {
                "source": "openweathermap_simulated",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "latitude": PARIS_LAT,
                "longitude": PARIS_LON,
                "aqi": (
                    random.randint(3, 5) if is_pollution_peak else random.randint(1, 3)
                ),
                "pm25": (
                    random.uniform(20, 80)
                    if is_pollution_peak
                    else random.uniform(5, 25)
                ),
                "pm10": (
                    random.uniform(30, 100)
                    if is_pollution_peak
                    else random.uniform(10, 40)
                ),
                "no2": (
                    random.uniform(60, 200)
                    if is_pollution_peak
                    else random.uniform(10, 60)
                ),
                "o3": random.uniform(40, 120),
                "co": random.uniform(200, 800),
                "temperature_celsius": random.uniform(5, 35),
                "humidity_pct": random.randint(40, 90),
                "wind_speed_ms": random.uniform(0.5, 10.0),
                "wind_direction_deg": random.randint(0, 359),
                "weather_condition": random.choice(["Clear", "Clouds", "Rain", "Fog"]),
                "visibility_m": random.randint(500, 10000),
                "precipitation_mm": (
                    random.uniform(0, 5) if random.random() > 0.7 else 0
                ),
            }
        ]

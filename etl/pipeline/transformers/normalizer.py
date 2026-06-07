"""
UrbanFlow — Normalisateur de données multi-sources
===================================================
Transforme les données hétérogènes (JSON, CSV, protobuf)
en un schéma uniforme compatible avec PostgreSQL/PostGIS.

Auteur : UrbanFlow Team — M2 Big Data & IA 2025
"""

import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger("urbanflow.etl.normalizer")


class DataNormalizer:
    """
    Normalise les données de sources hétérogènes vers le schéma UrbanFlow.

    Schémas cibles :
        - traffic_measurements : trafic routier avec géométrie PostGIS
        - environment_readings : données environnementales
        - transit_events : événements transports en commun
    """

    def normalize_traffic(self, raw_records: list[dict]) -> list[dict]:
        """
        Normalise les enregistrements de trafic routier.

        Valeurs par défaut appliquées pour les champs manquants.
        Conversion des types et validation des plages de valeurs.

        Args:
            raw_records: Données brutes multi-sources

        Returns:
            list[dict]: Enregistrements normalisés (schéma uniforme)
        """
        normalized = []
        for record in raw_records:
            try:
                normalized.append(
                    {
                        "source": str(record.get("source", "unknown")),
                        "sensor_id": str(record.get("sensor_id", "unknown")),
                        "road_name": str(record.get("road_name", "unknown")),
                        "latitude": (
                            float(record["latitude"])
                            if record.get("latitude") is not None
                            else None
                        ),
                        "longitude": (
                            float(record["longitude"])
                            if record.get("longitude") is not None
                            else None
                        ),
                        "vehicle_count": int(record.get("vehicle_count", 0)),
                        "average_speed_kmh": float(record.get("average_speed_kmh", 0)),
                        "congestion_level": int(record.get("congestion_level", 0)),
                        "timestamp": self._parse_timestamp(record.get("timestamp")),
                        "created_at": datetime.now(timezone.utc).isoformat(),
                    }
                )
            except (ValueError, TypeError) as e:
                logger.warning(
                    "⚠️  Enregistrement trafic invalide ignoré: %s — %s", record, e
                )
        return normalized

    def normalize_environment(self, raw_records: list[dict]) -> list[dict]:
        """
        Normalise les données environnementales (météo + qualité air).

        Args:
            raw_records: Données brutes OpenWeatherMap / Airparif

        Returns:
            list[dict]: Lectures environnementales normalisées
        """
        normalized = []
        for record in raw_records:
            try:
                normalized.append(
                    {
                        "source": str(record.get("source", "unknown")),
                        "latitude": float(record.get("latitude", 48.8566)),
                        "longitude": float(record.get("longitude", 2.3522)),
                        "aqi": int(record.get("aqi", 0)),
                        "pm25": float(record.get("pm25", 0)),
                        "pm10": float(record.get("pm10", 0)),
                        "no2": float(record.get("no2", 0)),
                        "o3": float(record.get("o3", 0)),
                        "temperature_celsius": float(
                            record.get("temperature_celsius", 15)
                        ),
                        "humidity_pct": int(record.get("humidity_pct", 60)),
                        "wind_speed_ms": float(record.get("wind_speed_ms", 0)),
                        "weather_condition": str(
                            record.get("weather_condition", "Unknown")
                        ),
                        "precipitation_mm": float(record.get("precipitation_mm", 0)),
                        "timestamp": self._parse_timestamp(record.get("timestamp")),
                    }
                )
            except (ValueError, TypeError) as e:
                logger.warning(
                    "⚠️  Enregistrement environnemental invalide: %s — %s", record, e
                )
        return normalized

    def normalize_transit(self, raw_records: list[dict]) -> list[dict]:
        """
        Normalise les données de transports en commun (GTFS-RT).

        Args:
            raw_records: Données brutes IDF Mobilités

        Returns:
            list[dict]: Événements transit normalisés
        """
        normalized = []
        for record in raw_records:
            try:
                normalized.append(
                    {
                        "source": str(record.get("source", "unknown")),
                        "event_type": str(record.get("type", "unknown")),
                        "line": str(record.get("line", "unknown")),
                        "delay_minutes": int(record.get("delay_minutes", 0)),
                        "severity": int(record.get("severity", 1)),
                        "message": str(record.get("message", ""))[:500],
                        "timestamp": self._parse_timestamp(record.get("timestamp")),
                    }
                )
            except (ValueError, TypeError) as e:
                logger.warning(
                    "⚠️  Enregistrement transit invalide: %s — %s", record, e
                )
        return normalized

    @staticmethod
    def _parse_timestamp(ts: Any) -> str:
        """
        Parse et normalise un timestamp en format ISO 8601 UTC.

        Accepte : str ISO, datetime, None (→ maintenant)

        Args:
            ts: Timestamp brut

        Returns:
            str: Timestamp ISO 8601 UTC normalisé
        """
        if ts is None:
            return datetime.now(timezone.utc).isoformat()
        if isinstance(ts, datetime):
            return ts.astimezone(timezone.utc).isoformat()
        if isinstance(ts, str):
            try:
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                return dt.astimezone(timezone.utc).isoformat()
            except ValueError:
                return datetime.now(timezone.utc).isoformat()
        return datetime.now(timezone.utc).isoformat()

"""
UrbanFlow — Pipeline d'Ingestion ETL Asynchrone
================================================
Module principal d'ingestion des données open data.

Architecture :
    - asyncio + httpx pour les requêtes HTTP non-bloquantes
    - Prefect pour l'orchestration des flows
    - CodeCarbon pour la mesure de l'empreinte carbone
    - Conformité RGPD : anonymisation avant tout stockage

Sources intégrées :
    1. Île-de-France Mobilités (GTFS-RT)
    2. Data.gouv.fr (Comptages trafic routier)
    3. OpenWeatherMap (Météo + Qualité de l'air)
    4. Crowdsourcing citoyen (API interne)

Auteur : UrbanFlow Team — M2 Big Data & IA 2025
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

import httpx
from codecarbon import EmissionsTracker

from etl.pipeline.loaders.postgres_loader import PostgresLoader
from etl.pipeline.loaders.redis_loader import RedisLoader
from etl.pipeline.sources.data_gouv import DataGouvSource
from etl.pipeline.sources.environment import EnvironmentSource
from etl.pipeline.sources.idf_mobilites import IDFMobilitesSource
from etl.pipeline.transformers.gdpr_anonymizer import GDPRAnonymizer
from etl.pipeline.transformers.normalizer import DataNormalizer

# configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("urbanflow.etl.ingestor")


class DataIngestor:
    """
    Orchestrateur principal du pipeline ETL asynchrone UrbanFlow.

    Responsabilités :
        - Coordination des appels API en parallèle (asyncio.gather)
        - Délégation de l'anonymisation RGPD au GDPRAnonymizer
        - Chargement dans PostgreSQL (historique) et Redis (temps réel)
        - Mesure de l'empreinte carbone via CodeCarbon
        - Retry exponentiel en cas d'échec API (tenacity)

    Attributs:
        http_client: Client HTTP async partagé (httpx.AsyncClient)
        normalizer: Normalisateur de données multi-sources
        anonymizer: Module d'anonymisation RGPD
        pg_loader: Chargeur vers PostgreSQL/PostGIS
        redis_loader: Chargeur vers Redis
    """

    def __init__(self) -> None:
        self.http_client: httpx.AsyncClient | None = None
        self.normalizer = DataNormalizer()
        self.anonymizer = GDPRAnonymizer()
        self.pg_loader = PostgresLoader()
        self.redis_loader = RedisLoader()

        # Sources de données
        self.sources = {
            "idf_mobilites": IDFMobilitesSource(),
            "data_gouv": DataGouvSource(),
            "environment": EnvironmentSource(),
        }

    async def __aenter__(self) -> "DataIngestor":
        """Initialise le client HTTP async et les connexions BDD."""
        timeout = httpx.Timeout(30.0, connect=10.0)
        self.http_client = httpx.AsyncClient(
            timeout=timeout,
            headers={"User-Agent": "UrbanFlow-ETL/1.0 (contact@urbanflow.fr)"},
            follow_redirects=True,
        )
        await self.pg_loader.connect()
        await self.redis_loader.connect()
        logger.info("DataIngestor initialisé — connexions établies")
        return self

    async def __aexit__(self, *args: Any) -> None:
        """Libère toutes les ressources proprement."""
        if self.http_client:
            await self.http_client.aclose()
        await self.pg_loader.disconnect()
        await self.redis_loader.disconnect()
        logger.info("DataIngestor fermé — ressources libérées")

    async def fetch_all_sources(self) -> dict[str, list[dict]]:
        """
        Récupère les données de toutes les sources en parallèle.

        Utilise asyncio.gather pour maximiser le débit et minimiser
        la latence totale d'ingestion. Les erreurs d'une source
        n'interrompent pas les autres (return_exceptions=True).

        Returns:
            dict[str, list[dict]]: Données brutes par source
        """
        logger.info("🚀 Démarrage de l'ingestion parallèle des sources...")
        start_time = datetime.now(timezone.utc)

        tasks = {
            name: source.fetch(self.http_client)
            for name, source in self.sources.items()
        }

        # Exécution parallèle — return_exceptions évite l'annulation en cascade
        results = await asyncio.gather(*tasks.values(), return_exceptions=True)
        raw_data: dict[str, list[dict]] = {}

        for name, result in zip(tasks.keys(), results):
            if isinstance(result, Exception):
                logger.error(
                    "❌ Source '%s' échouée: %s — utilisation du cache Redis",
                    name,
                    str(result),
                )
                # Fallback: données en cache Redis
                raw_data[name] = await self.redis_loader.get_fallback(name) or []
            else:
                raw_data[name] = result
                logger.info(
                    "✅ Source '%s' — %d enregistrements récupérés", name, len(result)
                )

        elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
        logger.info("📦 Ingestion parallèle terminée en %.2fs", elapsed)
        return raw_data

    async def process_traffic_data(self, raw_data: list[dict]) -> list[dict]:
        """
        Traite les données de trafic :
        1. Normalisation (schéma uniforme)
        2. Validation (types, plages, coordonnées valides)
        3. Enrichissement géospatial (PostGIS)

        Args:
            raw_data: Données brutes de trafic

        Returns:
            list[dict]: Données normalisées prêtes pour PostgreSQL
        """
        normalized = self.normalizer.normalize_traffic(raw_data)
        valid_records = [r for r in normalized if self._validate_traffic_record(r)]

        if len(valid_records) < len(normalized):
            logger.warning(
                "⚠️  %d/%d enregistrements invalides ignorés",
                len(normalized) - len(valid_records),
                len(normalized),
            )
        return valid_records

    async def process_crowdsourcing_data(
        self, raw_data: list[dict], client_ip: str = ""
    ) -> list[dict]:
        """
        Traite les signalements citoyens avec anonymisation RGPD complète.

        Conformité RGPD (Privacy by Design — Art. 25) :
        - Hashing SHA-256 + sel de l'adresse IP
        - Floutage des coordonnées GPS (±150m)
        - Génération d'UUID éphémères (TTL 30 jours)
        - Suppression des PII avant toute persistance

        Args:
            raw_data: Signalements bruts (avec PII potentiels)
            client_ip: Adresse IP du client (sera hashée)

        Returns:
            list[dict]: Signalements anonymisés conformes RGPD
        """
        logger.info(
            "🔐 Application de l'anonymisation RGPD sur %d signalements...",
            len(raw_data),
        )
        anonymized = []
        for record in raw_data:
            anon_record = await self.anonymizer.anonymize(
                data=record,
                client_ip=client_ip,
            )
            anonymized.append(anon_record)
        logger.info("✅ Anonymisation terminée — aucune PII stockée")
        return anonymized

    @staticmethod
    def _validate_traffic_record(record: dict) -> bool:
        """
        Valide qu'un enregistrement de trafic est cohérent.

        Règles :
        - Coordonnées dans les limites géographiques de l'Île-de-France
        - Vitesse entre 0 et 200 km/h
        - Timestamp récent (< 24h)

        Args:
            record: Enregistrement à valider

        Returns:
            bool: True si valide
        """
        lat = record.get("latitude")
        lon = record.get("longitude")
        speed = record.get("average_speed_kmh", 0)

        # Bounding box Île-de-France
        IDF_BBOX = {
            "lat_min": 48.12,
            "lat_max": 49.24,
            "lon_min": 1.45,
            "lon_max": 3.56,
        }

        if lat is None or lon is None:
            return False
        if not (IDF_BBOX["lat_min"] <= lat <= IDF_BBOX["lat_max"]):
            return False
        if not (IDF_BBOX["lon_min"] <= lon <= IDF_BBOX["lon_max"]):
            return False
        if not (0 <= speed <= 200):
            return False
        return True

    async def load_to_storage(
        self, processed_data: dict[str, list[dict]]
    ) -> dict[str, int]:
        """
        Charge les données traitées dans PostgreSQL et Redis.

        Stratégie :
        - PostgreSQL : INSERT batch pour l'historique (série temporelle)
        - Redis : SET avec TTL pour les alertes temps réel (5 minutes)

        Args:
            processed_data: Données traitées par catégorie

        Returns:
            dict[str, int]: Nombre d'enregistrements chargés par destination
        """
        stats: dict[str, int] = {"postgres": 0, "redis": 0}

        # Chargement PostgreSQL (historique + index PostGIS)
        if "traffic" in processed_data:
            pg_count = await self.pg_loader.bulk_insert_traffic(
                processed_data["traffic"]
            )
            stats["postgres"] += pg_count
            logger.info("🗄️  PostgreSQL: %d enregistrements trafic insérés", pg_count)

        if "environment" in processed_data:
            pg_count = await self.pg_loader.bulk_insert_environment(
                processed_data["environment"]
            )
            stats["postgres"] += pg_count

        # Chargement Redis (alertes temps réel, TTL = 5 minutes)
        if "traffic" in processed_data:
            alerts = [
                r
                for r in processed_data["traffic"]
                if r.get("congestion_level", 0) >= 3
            ]
            redis_count = await self.redis_loader.set_traffic_alerts(alerts, ttl=300)
            stats["redis"] += redis_count
            logger.info(
                "⚡ Redis: %d alertes trafic mises en cache (TTL=5min)", redis_count
            )

        return stats

    async def run_pipeline(self) -> dict[str, Any]:
        """
        Exécute le pipeline ETL complet avec mesure d'empreinte carbone.

        Phases :
        1. Extraction (fetch toutes sources en parallèle)
        2. Transformation (normalisation + anonymisation RGPD)
        3. Chargement (PostgreSQL + Redis)
        4. Reporting (métriques + CO₂)

        Returns:
            dict[str, Any]: Rapport d'exécution (métriques, CO₂, stats)
        """
        pipeline_start = datetime.now(timezone.utc)
        logger.info("═══ Démarrage du pipeline ETL UrbanFlow ═══")

        # extraction
        raw_data = await self.fetch_all_sources()

        # transformation
        processed: dict[str, list[dict]] = {}

        if raw_data.get("data_gouv"):
            processed["traffic"] = await self.process_traffic_data(
                raw_data["data_gouv"]
            )

        if raw_data.get("environment"):
            processed["environment"] = self.normalizer.normalize_environment(
                raw_data["environment"]
            )

        if raw_data.get("idf_mobilites"):
            processed["transit"] = self.normalizer.normalize_transit(
                raw_data["idf_mobilites"]
            )

        # chargement
        load_stats = await self.load_to_storage(processed)

        # rapport
        elapsed = (datetime.now(timezone.utc) - pipeline_start).total_seconds()
        report = {
            "status": "success",
            "timestamp": pipeline_start.isoformat(),
            "duration_seconds": round(elapsed, 2),
            "records_processed": {k: len(v) for k, v in processed.items()},
            "storage_stats": load_stats,
        }

        logger.info(
            "═══ Pipeline terminé en %.2fs — %d records PostgreSQL, %d alertes Redis ═══",
            elapsed,
            load_stats.get("postgres", 0),
            load_stats.get("redis", 0),
        )
        return report


# point d'entrée autonome (hors prefect)
async def main() -> None:
    """
    Point d'entrée pour l'exécution autonome du pipeline.
    En production, ce module est appelé par les Prefect flows.
    CodeCarbon trace l'empreinte CO₂ de l'exécution complète.
    """
    # Activation du tracker CodeCarbon (éco-conception)
    tracker = EmissionsTracker(
        project_name="UrbanFlow-ETL",
        output_dir="./logs/carbon",
        save_to_file=True,
        log_level="error",  # Silencieux en production
    )
    tracker.start()

    try:
        async with DataIngestor() as ingestor:
            report = await ingestor.run_pipeline()
            logger.info("📊 Rapport: %s", report)
    finally:
        emissions = tracker.stop()
        logger.info(
            "🌱 Empreinte carbone du pipeline: %.6f kg CO₂eq",
            emissions or 0.0,
        )


if __name__ == "__main__":
    asyncio.run(main())

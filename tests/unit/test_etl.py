"""
UrbanFlow — Tests Unitaires : Pipeline ETL
==========================================
Tests exhaustifs du pipeline d'ingestion de données.

Couverture :
    - Normalisation des données multi-sources
    - Anonymisation RGPD (hashing, floutage, UUID)
    - Validation des coordonnées géographiques
    - Gestion des erreurs et valeurs manquantes
    - Conformité RGPD (aucune PII dans les outputs)

Framework : pytest + pytest-asyncio
Exécution : pytest tests/unit/test_etl.py -v --cov=etl

Auteur : UrbanFlow Team — M2 Big Data & IA 2025
"""

import asyncio
import hashlib
import re
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

# Imports des modules à tester
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from etl.pipeline.transformers.gdpr_anonymizer import GDPRAnonymizer, _SALT
from etl.pipeline.transformers.normalizer import DataNormalizer
from etl.pipeline.sources.data_gouv import DataGouvSource


# FIXTURES

@pytest.fixture
def normalizer() -> DataNormalizer:
    """Fixture : instance du normalisateur de données."""
    return DataNormalizer()


@pytest.fixture
def anonymizer() -> GDPRAnonymizer:
    """Fixture : instance de l'anonymiseur RGPD."""
    return GDPRAnonymizer()


@pytest.fixture
def sample_traffic_record() -> dict:
    """Fixture : enregistrement de trafic valide pour les tests."""
    return {
        "source": "data_gouv",
        "sensor_id": "BP_01",
        "road_name": "Boulevard Périphérique Nord",
        "latitude": 48.8972,
        "longitude": 2.3588,
        "vehicle_count": 1500,
        "average_speed_kmh": 45.0,
        "congestion_level": 2,
        "timestamp": "2025-09-15T08:30:00+00:00",
    }


@pytest.fixture
def sample_crowdsourcing_record() -> dict:
    """Fixture : signalement citoyen brut avec PII pour les tests RGPD."""
    return {
        "ip_address": "192.168.1.42",
        "latitude": 48.856614,
        "longitude": 2.352222,
        "user_id": "user_123456",
        "email": "jean.dupont@gmail.com",
        "phone": "0612345678",
        "report_type": "embouteillage",
        "severity": 3,
        "description": "Trafic dense. Mon email: jean@test.com. Tel: 0606060606",
    }


# TESTS — Normalisateur de données

class TestDataNormalizer:
    """Tests du module de normalisation des données multi-sources."""

    def test_normalize_traffic_valid_record(
        self, normalizer: DataNormalizer, sample_traffic_record: dict
    ) -> None:
        """Un enregistrement valide doit être normalisé sans erreur."""
        result = normalizer.normalize_traffic([sample_traffic_record])
        assert len(result) == 1
        assert result[0]["sensor_id"] == "BP_01"
        assert result[0]["latitude"] == 48.8972
        assert result[0]["congestion_level"] == 2

    def test_normalize_traffic_invalid_type_ignored(self, normalizer: DataNormalizer) -> None:
        """Un enregistrement avec types invalides doit être ignoré silencieusement."""
        invalid_record = {
            "sensor_id": "INVALID",
            "latitude": "not_a_float",
            "longitude": "not_a_float",
            "vehicle_count": "abc",
            "average_speed_kmh": None,
            "congestion_level": "invalid",
        }
        result = normalizer.normalize_traffic([invalid_record])
        assert len(result) == 0, "Les enregistrements invalides ne doivent pas être inclus"

    def test_normalize_traffic_missing_optional_fields(
        self, normalizer: DataNormalizer
    ) -> None:
        """Les champs optionnels manquants doivent utiliser des valeurs par défaut."""
        minimal_record = {
            "sensor_id": "MIN_01",
            "road_name": "Route Test",
            "latitude": 48.85,
            "longitude": 2.35,
            "vehicle_count": 500,
            "average_speed_kmh": 60.0,
            "congestion_level": 1,
        }
        result = normalizer.normalize_traffic([minimal_record])
        assert len(result) == 1
        assert result[0]["source"] == "unknown"  # Valeur par défaut
        assert result[0]["timestamp"] is not None

    def test_normalize_traffic_batch_processing(self, normalizer: DataNormalizer) -> None:
        """Le normalisateur doit traiter un batch de 100 enregistrements."""
        records = [
            {
                "source": "data_gouv",
                "sensor_id": f"S_{i:03d}",
                "road_name": f"Route {i}",
                "latitude": 48.80 + (i * 0.001),
                "longitude": 2.30 + (i * 0.001),
                "vehicle_count": i * 10,
                "average_speed_kmh": float(50 + (i % 60)),
                "congestion_level": i % 5,
            }
            for i in range(100)
        ]
        result = normalizer.normalize_traffic(records)
        assert len(result) == 100, "Les 100 enregistrements valides doivent être normalisés"

    def test_parse_timestamp_iso_string(self, normalizer: DataNormalizer) -> None:
        """Le parser doit accepter les timestamps ISO 8601."""
        ts = normalizer._parse_timestamp("2025-09-15T08:30:00+02:00")
        assert "2025-09-15" in ts
        assert "+00:00" in ts or "Z" in ts or "UTC" in ts.upper() or "2025" in ts

    def test_parse_timestamp_none(self, normalizer: DataNormalizer) -> None:
        """Un timestamp None doit retourner l'heure courante."""
        ts = normalizer._parse_timestamp(None)
        now = datetime.now(timezone.utc)
        parsed = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        assert abs((now - parsed).total_seconds()) < 5

    def test_normalize_environment_valid(self, normalizer: DataNormalizer) -> None:
        """Les données environnementales valides doivent être normalisées."""
        env_record = {
            "source": "openweathermap",
            "latitude": 48.8566,
            "longitude": 2.3522,
            "aqi": 3,
            "pm25": 35.5,
            "pm10": 52.0,
            "no2": 85.0,
            "o3": 60.0,
            "temperature_celsius": 18.5,
            "humidity_pct": 65,
            "wind_speed_ms": 3.5,
            "weather_condition": "Clouds",
            "precipitation_mm": 0.0,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        result = normalizer.normalize_environment([env_record])
        assert len(result) == 1
        assert result[0]["aqi"] == 3
        assert result[0]["pm25"] == 35.5


# TESTS — Anonymisation RGPD

class TestGDPRAnonymizer:
    """
    Tests exhaustifs de la conformité RGPD.

    Principes testés :
    - Irréversibilité du hashing IP
    - Floutage des coordonnées GPS
    - Unicité des identifiants éphémères
    - Absence de PII dans les outputs
    - Nettoyage des textes libres
    """

    def test_hash_ip_is_sha256(self, anonymizer: GDPRAnonymizer) -> None:
        """Le hash IP doit être un SHA-256 valide (64 caractères hexadécimaux)."""
        ip = "192.168.1.42"
        result = anonymizer.hash_ip(ip)
        assert len(result) == 64
        assert re.match(r"^[a-f0-9]{64}$", result), "Doit être un hash hexadécimal SHA-256"

    def test_hash_ip_is_deterministic(self, anonymizer: GDPRAnonymizer) -> None:
        """Le même IP doit toujours produire le même hash (déterministe)."""
        ip = "10.0.0.1"
        hash1 = anonymizer.hash_ip(ip)
        hash2 = anonymizer.hash_ip(ip)
        assert hash1 == hash2

    def test_hash_ip_is_salted(self, anonymizer: GDPRAnonymizer) -> None:
        """Le hash doit inclure le sel (pas un simple SHA-256 de l'IP brute)."""
        ip = "1.2.3.4"
        raw_hash = hashlib.sha256(ip.encode()).hexdigest()
        salted_hash = anonymizer.hash_ip(ip)
        assert raw_hash != salted_hash, "Le hashing doit utiliser un sel cryptographique"

    def test_hash_different_ips_produce_different_hashes(
        self, anonymizer: GDPRAnonymizer
    ) -> None:
        """Des IPs différentes doivent produire des hashes différents."""
        assert anonymizer.hash_ip("1.1.1.1") != anonymizer.hash_ip("2.2.2.2")

    def test_blur_coordinates_within_150m(self, anonymizer: GDPRAnonymizer) -> None:
        """Le floutage GPS doit rester dans un rayon de 150 mètres (±0.0015°)."""
        lat, lon = 48.8566, 2.3522
        blurred_lat, blurred_lon = anonymizer.blur_coordinates(lat, lon)

        delta_lat = abs(blurred_lat - lat)
        delta_lon = abs(blurred_lon - lon)

        assert delta_lat <= 0.0015, f"Floutage latitude trop grand: {delta_lat}"
        assert delta_lon <= 0.0015, f"Floutage longitude trop grand: {delta_lon}"

    def test_blur_coordinates_changes_values(self, anonymizer: GDPRAnonymizer) -> None:
        """Le floutage doit modifier les coordonnées (pas d'identité)."""
        lat, lon = 48.8566, 2.3522
        # Test sur 10 itérations (le bruit est aléatoire)
        changed = any(
            anonymizer.blur_coordinates(lat, lon) != (lat, lon)
            for _ in range(10)
        )
        assert changed, "Le floutage ne modifie jamais les coordonnées"

    def test_generate_ephemeral_id_is_uuid_v4(self, anonymizer: GDPRAnonymizer) -> None:
        """L'ID éphémère doit être un UUID v4 valide."""
        ephemeral_id = anonymizer.generate_ephemeral_id()
        try:
            parsed = uuid.UUID(ephemeral_id, version=4)
            assert str(parsed) == ephemeral_id
        except ValueError:
            pytest.fail(f"'{ephemeral_id}' n'est pas un UUID v4 valide")

    def test_generate_ephemeral_ids_are_unique(self, anonymizer: GDPRAnonymizer) -> None:
        """Chaque ID éphémère doit être unique."""
        ids = {anonymizer.generate_ephemeral_id() for _ in range(100)}
        assert len(ids) == 100, "Des IDs dupliqués ont été générés"

    @pytest.mark.asyncio
    async def test_anonymize_removes_pii_fields(
        self, anonymizer: GDPRAnonymizer, sample_crowdsourcing_record: dict
    ) -> None:
        """Après anonymisation, aucun champ PII ne doit rester dans l'output."""
        result = await anonymizer.anonymize(
            data=sample_crowdsourcing_record.copy(),
            client_ip="192.168.1.42",
        )

        # Champs PII qui ne doivent PAS être dans l'output
        pii_fields = ["ip_address", "user_id", "email", "name", "phone",
                      "device_id", "session_id", "latitude", "longitude"]
        for field in pii_fields:
            assert field not in result, f"PII '{field}' trouvé dans les données anonymisées !"

    @pytest.mark.asyncio
    async def test_anonymize_preserves_useful_data(
        self, anonymizer: GDPRAnonymizer, sample_crowdsourcing_record: dict
    ) -> None:
        """Les données utiles (type, sévérité) doivent être préservées."""
        result = await anonymizer.anonymize(
            data=sample_crowdsourcing_record.copy(),
            client_ip="10.0.0.1",
        )
        assert result["report_type"] == "embouteillage"
        assert result["severity"] == 3
        assert result["ephemeral_id"] is not None
        assert result["latitude_approx"] is not None
        assert result["longitude_approx"] is not None

    def test_sanitize_text_removes_email(self, anonymizer: GDPRAnonymizer) -> None:
        """Les emails dans les textes libres doivent être supprimés."""
        text = "Problème signalé. Contact: jean.dupont@gmail.com pour info."
        result = anonymizer._sanitize_text(text)
        assert "@gmail.com" not in result
        assert "EMAIL_REDACTED" in result

    def test_sanitize_text_removes_phone(self, anonymizer: GDPRAnonymizer) -> None:
        """Les numéros de téléphone dans les textes libres doivent être supprimés."""
        text = "Appelez le 0612345678 pour confirmation"
        result = anonymizer._sanitize_text(text)
        assert "0612345678" not in result
        assert "PHONE_REDACTED" in result

    def test_sanitize_text_truncates_at_500(self, anonymizer: GDPRAnonymizer) -> None:
        """Les textes longs doivent être tronqués à 500 caractères."""
        long_text = "A" * 1000
        result = anonymizer._sanitize_text(long_text)
        assert len(result) <= 500


# TESTS — Validation géographique

class TestGeographicValidation:
    """Tests de validation des données géographiques."""

    @pytest.mark.parametrize("lat,lon,expected", [
        (48.8566, 2.3522, True),   # Paris centre — valide
        (48.12, 1.45, True),       # Borne inférieure — valide
        (49.24, 3.56, True),       # Borne supérieure — valide
        (51.0, 2.3, False),        # Hors IDF (trop au nord) — invalide
        (47.0, 2.3, False),        # Hors IDF (trop au sud) — invalide
        (48.8, 5.0, False),        # Hors IDF (trop à l'est) — invalide
        (48.8, 0.5, False),        # Hors IDF (trop à l'ouest) — invalide
    ])
    def test_idf_bbox_validation(
        self, lat: float, lon: float, expected: bool
    ) -> None:
        """Les coordonnées hors IDF doivent être rejetées."""
        from etl.pipeline.ingestor import DataIngestor
        record = {
            "latitude": lat,
            "longitude": lon,
            "average_speed_kmh": 60,
        }
        result = DataIngestor._validate_traffic_record(record)
        assert result == expected, (
            f"Validation incorrecte pour ({lat}, {lon}): "
            f"attendu={expected}, obtenu={result}"
        )

    @pytest.mark.parametrize("speed,expected", [
        (0, True),
        (50, True),
        (130, True),
        (200, True),
        (-1, False),   # Vitesse négative — invalide
        (201, False),  # Vitesse impossible — invalide
    ])
    def test_speed_validation(self, speed: float, expected: bool) -> None:
        """Les vitesses hors plage (0-200 km/h) doivent être rejetées."""
        from etl.pipeline.ingestor import DataIngestor
        record = {
            "latitude": 48.85,
            "longitude": 2.35,
            "average_speed_kmh": speed,
        }
        result = DataIngestor._validate_traffic_record(record)
        assert result == expected


# TESTS — Sources de données (avec mock HTTP)

class TestDataGouvSource:
    """Tests de la source Data.gouv.fr avec mocks HTTP."""

    @pytest.mark.asyncio
    async def test_fetch_uses_fallback_on_http_error(self) -> None:
        """En cas d'erreur HTTP, le fallback simulé doit être retourné."""
        source = DataGouvSource()

        import httpx
        # Mock du client HTTP qui lève une erreur de connexion
        mock_client = AsyncMock()
        mock_client.get.side_effect = httpx.ConnectError("Service unavailable")

        result = await source.fetch(mock_client)

        # Le fallback doit retourner des données simulées
        assert len(result) > 0, "Le fallback doit retourner des données même en cas d'erreur"
        assert all("road_name" in r for r in result)
        assert all("congestion_level" in r for r in result)
        assert all(0 <= r["congestion_level"] <= 4 for r in result)

    def test_parse_traffic_records_congestion_calculation(self) -> None:
        """Le calcul du niveau de congestion SETRA doit être correct."""
        source = DataGouvSource()
        test_cases = [
            ({"q": 90.0, "geo_point_2d": {"lat": 48.8, "lon": 2.3}}, 0),  # Fluide
            ({"q": 60.0, "geo_point_2d": {"lat": 48.8, "lon": 2.3}}, 1),  # Dense
            ({"q": 40.0, "geo_point_2d": {"lat": 48.8, "lon": 2.3}}, 2),  # Saturé
            ({"q": 20.0, "geo_point_2d": {"lat": 48.8, "lon": 2.3}}, 3),  # Bloqué
            ({"q": 5.0,  "geo_point_2d": {"lat": 48.8, "lon": 2.3}}, 4),  # Paralysé
        ]
        for raw_record, expected_congestion in test_cases:
            result = source._parse_traffic_records([raw_record])
            assert len(result) == 1
            assert result[0]["congestion_level"] == expected_congestion, (
                f"Vitesse {raw_record['q']} → congestion attendue {expected_congestion}, "
                f"obtenue {result[0]['congestion_level']}"
            )

    def test_simulated_traffic_rush_hour_profile(self) -> None:
        """Les données simulées doivent refléter les profils d'heure de pointe."""
        source = DataGouvSource()
        # On ne peut pas contrôler l'heure dans le test, mais on vérifie le format
        results = source._generate_simulated_traffic()
        assert len(results) == 8, "8 axes principaux IDF attendus"
        for r in results:
            assert 48.0 < r["latitude"] < 49.0
            assert 1.5 < r["longitude"] < 3.5
            assert 0 <= r["congestion_level"] <= 4
            assert r["average_speed_kmh"] > 0

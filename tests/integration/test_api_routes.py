

import json
import sys
import os
import uuid

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))

from app.main import app

# client de test
@pytest.fixture(scope="module")
def client() -> TestClient:
    """Client de test FastAPI — scope module pour éviter le reload."""
    with TestClient(app) as c:
        yield c


# TESTS — Health Check

class TestHealthCheck:
    """Tests du endpoint de health check."""

    def test_health_returns_200(self, client: TestClient) -> None:
        """Le health check doit retourner HTTP 200."""
        response = client.get("/api/v1/health")
        assert response.status_code == 200

    def test_health_response_schema(self, client: TestClient) -> None:
        """La réponse doit respecter le schéma attendu."""
        response = client.get("/api/v1/health")
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert "version" in data
        assert "components" in data

    def test_health_content_type_json(self, client: TestClient) -> None:
        """La réponse doit être en JSON."""
        response = client.get("/api/v1/health")
        assert "application/json" in response.headers["content-type"]


# TESTS — Routes Trafic

class TestTrafficRoutes:
    """Tests des endpoints de trafic routier."""

    def test_get_current_traffic_200(self, client: TestClient) -> None:
        """GET /traffic/current doit retourner HTTP 200."""
        response = client.get("/api/v1/traffic/current")
        assert response.status_code == 200

    def test_get_current_traffic_returns_list(self, client: TestClient) -> None:
        """La réponse doit être une liste de mesures."""
        response = client.get("/api/v1/traffic/current")
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0

    def test_traffic_record_schema(self, client: TestClient) -> None:
        """Chaque mesure de trafic doit avoir les champs requis."""
        response = client.get("/api/v1/traffic/current")
        records = response.json()
        required_fields = {
            "sensor_id", "road_name", "latitude", "longitude",
            "vehicle_count", "average_speed_kmh", "congestion_level", "timestamp"
        }
        for record in records:
            for field in required_fields:
                assert field in record, f"Champ obligatoire manquant: {field}"

    def test_traffic_congestion_level_range(self, client: TestClient) -> None:
        """Le niveau de congestion doit être entre 0 et 4 (SETRA)."""
        response = client.get("/api/v1/traffic/current")
        for record in response.json():
            assert 0 <= record["congestion_level"] <= 4, (
                f"Niveau de congestion invalide: {record['congestion_level']}"
            )

    def test_traffic_coordinates_in_idf(self, client: TestClient) -> None:
        """Les coordonnées doivent être dans la bounding box IDF."""
        response = client.get("/api/v1/traffic/current")
        for record in response.json():
            assert 48.12 <= record["latitude"] <= 49.24, "Latitude hors IDF"
            assert 1.45 <= record["longitude"] <= 3.56, "Longitude hors IDF"

    def test_traffic_speed_non_negative(self, client: TestClient) -> None:
        """La vitesse moyenne ne peut pas être négative."""
        response = client.get("/api/v1/traffic/current")
        for record in response.json():
            assert record["average_speed_kmh"] >= 0

    def test_get_current_traffic_limit_param(self, client: TestClient) -> None:
        """Le paramètre limit doit limiter le nombre de résultats."""
        response_limited = client.get("/api/v1/traffic/current?limit=2")
        assert response_limited.status_code == 200
        assert len(response_limited.json()) <= 2

    def test_predict_traffic_valid_request(self, client: TestClient) -> None:
        """POST /traffic/predict avec des données valides doit retourner 200."""
        payload = {
            "sensor_id": "BP_NORD_01",
            "horizon_minutes": 60,
            "include_confidence": True,
        }
        response = client.post("/api/v1/traffic/predict", json=payload)
        assert response.status_code == 200

    def test_predict_traffic_response_schema(self, client: TestClient) -> None:
        """La prédiction doit respecter le schéma PredictionResponse."""
        payload = {"sensor_id": "TEST_SENSOR", "horizon_minutes": 30}
        response = client.post("/api/v1/traffic/predict", json=payload)
        data = response.json()
        required = {
            "sensor_id", "predicted_congestion_level", "predicted_speed_kmh",
            "prediction_horizon_minutes", "model_used", "computed_at"
        }
        for field in required:
            assert field in data, f"Champ manquant: {field}"
        assert data["model_used"] == "hybrid_arima_lstm"
        assert 0 <= data["predicted_congestion_level"] <= 4

    def test_predict_traffic_invalid_horizon(self, client: TestClient) -> None:
        """Un horizon de prédiction invalide (> 240 min) doit retourner 422."""
        payload = {"sensor_id": "TEST", "horizon_minutes": 9999}
        response = client.post("/api/v1/traffic/predict", json=payload)
        assert response.status_code == 422, "Validation Pydantic doit rejeter horizon > 240"

    def test_heatmap_returns_weighted_points(self, client: TestClient) -> None:
        """La heatmap doit retourner des points avec weight entre 0 et 1."""
        response = client.get("/api/v1/traffic/heatmap")
        assert response.status_code == 200
        for point in response.json():
            assert "lat" in point
            assert "lon" in point
            assert "weight" in point
            assert 0.0 <= point["weight"] <= 1.0, f"Weight hors plage: {point['weight']}"

    def test_alerts_returns_high_congestion_only(self, client: TestClient) -> None:
        """Les alertes doivent ne contenir que les congestions ≥ min_level."""
        response = client.get("/api/v1/traffic/alerts?min_level=3")
        assert response.status_code == 200
        data = response.json()
        for alert in data.get("alerts", []):
            assert alert["congestion_level"] >= 3


# TESTS — Crowdsourcing (RGPD)

class TestCrowdsourcingRoutes:
    """Tests des endpoints crowdsourcing avec vérification RGPD."""

    def test_submit_report_valid(self, client: TestClient) -> None:
        """Un signalement valide doit être accepté avec HTTP 201."""
        payload = {
            "latitude": 48.8566,
            "longitude": 2.3522,
            "report_type": "embouteillage",
            "severity": 3,
            "description": "Trafic dense sur le Périphérique",
        }
        response = client.post("/api/v1/crowdsourcing/report", json=payload)
        assert response.status_code == 201

    def test_submit_report_returns_ephemeral_id(self, client: TestClient) -> None:
        """La réponse doit contenir un ID éphémère (UUID v4)."""
        payload = {
            "latitude": 48.8566,
            "longitude": 2.3522,
            "report_type": "accident",
            "severity": 5,
        }
        response = client.post("/api/v1/crowdsourcing/report", json=payload)
        data = response.json()
        assert "ephemeral_id" in data
        # Validation UUID v4
        try:
            parsed_uuid = uuid.UUID(data["ephemeral_id"], version=4)
            assert str(parsed_uuid) == data["ephemeral_id"]
        except ValueError:
            pytest.fail(f"ephemeral_id n'est pas un UUID v4: {data['ephemeral_id']}")

    def test_submit_report_contains_rgpd_notice(self, client: TestClient) -> None:
        """La réponse doit inclure une notice RGPD explicite."""
        payload = {
            "latitude": 48.80,
            "longitude": 2.30,
            "report_type": "travaux",
            "severity": 2,
        }
        response = client.post("/api/v1/crowdsourcing/report", json=payload)
        data = response.json()
        assert "rgpd_notice" in data
        assert len(data["rgpd_notice"]) > 20, "La notice RGPD doit être substantielle"

    def test_submit_report_invalid_type_rejected(self, client: TestClient) -> None:
        """Un type de signalement invalide doit être rejeté (422)."""
        payload = {
            "latitude": 48.8566,
            "longitude": 2.3522,
            "report_type": "INVALID_TYPE",
            "severity": 1,
        }
        response = client.post("/api/v1/crowdsourcing/report", json=payload)
        assert response.status_code == 422

    def test_submit_report_out_of_idf_rejected(self, client: TestClient) -> None:
        """Des coordonnées hors IDF doivent être rejetées (422)."""
        payload = {
            "latitude": 43.0,  # Hors IDF (Marseille)
            "longitude": 5.4,
            "report_type": "embouteillage",
            "severity": 1,
        }
        response = client.post("/api/v1/crowdsourcing/report", json=payload)
        assert response.status_code == 422

    def test_get_reports_no_pii_in_response(self, client: TestClient) -> None:
        """Les signalements retournés ne doivent jamais contenir de PII."""
        response = client.get("/api/v1/crowdsourcing/reports")
        assert response.status_code == 200
        pii_fields = ["ip_address", "email", "phone", "user_id", "device_id"]
        for report in response.json():
            for pii in pii_fields:
                assert pii not in report, f"PII '{pii}' trouvé dans la réponse API !"


# TESTS — Sécurité & Headers

class TestSecurityHeaders:
    """Tests des headers de sécurité HTTP."""

    def test_security_headers_present(self, client: TestClient) -> None:
        """Les headers de sécurité doivent être présents sur toutes les réponses."""
        response = client.get("/api/v1/health")
        assert "x-content-type-options" in response.headers
        assert response.headers["x-content-type-options"] == "nosniff"
        assert "x-frame-options" in response.headers
        assert response.headers["x-frame-options"] == "DENY"

    def test_response_time_header(self, client: TestClient) -> None:
        """Le header X-Response-Time doit être présent (monitoring)."""
        response = client.get("/api/v1/health")
        assert "x-response-time" in response.headers

    def test_404_returns_json(self, client: TestClient) -> None:
        """Les 404 doivent retourner du JSON, pas du HTML."""
        response = client.get("/api/v1/nonexistent-endpoint")
        assert response.status_code == 404
        data = response.json()
        assert "error" in data or "detail" in data


# TESTS — Environnement

class TestEnvironmentRoutes:
    """Tests des endpoints de données environnementales."""

    def test_get_environment_200(self, client: TestClient) -> None:
        """GET /environment/current doit retourner HTTP 200."""
        response = client.get("/api/v1/environment/current")
        assert response.status_code == 200

    def test_aqi_in_valid_range(self, client: TestClient) -> None:
        """L'indice AQI doit être entre 1 et 5."""
        response = client.get("/api/v1/environment/current")
        for reading in response.json():
            assert 1 <= reading["aqi"] <= 5, f"AQI invalide: {reading['aqi']}"

    def test_get_aqi_history_7_days(self, client: TestClient) -> None:
        """L'historique AQI doit couvrir 7 jours."""
        response = client.get("/api/v1/environment/aqi-history")
        assert response.status_code == 200
        data = response.json()
        assert data["period_days"] == 7
        assert len(data["history"]) == 7

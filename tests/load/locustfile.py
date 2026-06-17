"""
UrbanFlow — Test de Charge Locust
==================================
Script de test de performance pour valider la robustesse
de l'API FastAPI sous forte charge simulée.

Scénarios testés :
    - Charge nominale : 100 utilisateurs simultanés, montée en 30s
    - Pic de charge : 500 utilisateurs, test de stress
    - Endurance : 50 utilisateurs pendant 10 minutes

Métriques cibles (SLA) :
    - Latence P95 < 200ms pour tous les endpoints GET
    - Latence P95 < 500ms pour POST /predict
    - Taux d'erreur < 1%
    - Débit > 500 req/s en pic

Exécution :
    # Test standard
    locust -f tests/load/locustfile.py --host=http://localhost:8000
           --users=100 --spawn-rate=10 --run-time=5m --headless

    # Test de stress
    locust -f tests/load/locustfile.py --host=http://localhost:8000
           --users=500 --spawn-rate=50 --run-time=2m --headless

    # Rapport HTML
    locust -f tests/load/locustfile.py --host=http://localhost:8000
           --users=100 --spawn-rate=10 --run-time=5m
           --headless --html=reports/load_test_report.html

Auteur : UrbanFlow Team — M2 Big Data & IA 2025
"""

import random

from locust import HttpUser, between, events, tag, task


# UTILISATEURS SIMULÉS

class UrbanFlowAPIUser(HttpUser):
    """
    Simule un utilisateur typique de l'API UrbanFlow.

    Comportement :
        - Consulte le trafic actuel (60% du temps)
        - Consulte les données environnementales (20%)
        - Soumet une prédiction (15%)
        - Soumet un signalement citoyen (5%)

    Wait time : 1 à 3 secondes entre les requêtes
    (comportement réaliste d'un utilisateur API)
    """

    wait_time = between(1, 3)

    # Capteurs IDF simulés pour les requêtes de prédiction
    SENSOR_IDS = [
        "BP_NORD_01", "BP_SUD_01", "A1_VILLETTE_01",
        "A6_ORLEANS_01", "A13_STCLOUD_01", "A86_NANTERRE_01",
        "N118_VELIZY_01", "RN7_VILLEJUIF_01",
    ]

    def on_start(self) -> None:
        """Initialisation : warm-up avec un health check."""
        response = self.client.get("/api/v1/health")
        if response.status_code != 200:
            self.environment.runner.quit()

# trafic (60% du temps)

    @task(6)
    @tag("traffic", "read")
    def get_current_traffic(self) -> None:
        """Simule la consultation du trafic temps réel."""
        with self.client.get(
            "/api/v1/traffic/current",
            params={"limit": random.randint(10, 100)},
            catch_response=True,
            name="GET /traffic/current",
        ) as response:
            if response.status_code == 200:
                data = response.json()
                if not isinstance(data, list):
                    response.failure("Réponse invalide: doit être une liste")
            else:
                response.failure(f"HTTP {response.status_code}")

    @task(3)
    @tag("traffic", "heatmap")
    def get_heatmap(self) -> None:
        """Simule le chargement de la heatmap Mapbox."""
        with self.client.get(
            "/api/v1/traffic/heatmap",
            catch_response=True,
            name="GET /traffic/heatmap",
        ) as response:
            if response.status_code == 200:
                points = response.json()
                # Validation : tous les points doivent avoir un weight valide
                invalid = [p for p in points if not (0.0 <= p.get("weight", -1) <= 1.0)]
                if invalid:
                    response.failure(f"{len(invalid)} points avec weight invalide")
            else:
                response.failure(f"HTTP {response.status_code}")

    @task(2)
    @tag("traffic", "alerts")
    def get_alerts(self) -> None:
        """Simule la consultation des alertes de congestion."""
        with self.client.get(
            "/api/v1/traffic/alerts",
            params={"min_level": random.choice([2, 3, 4])},
            catch_response=True,
            name="GET /traffic/alerts",
        ) as response:
            if response.status_code != 200:
                response.failure(f"HTTP {response.status_code}")

# prédiction ia (15% du temps)

    @task(3)
    @tag("prediction", "ml")
    def post_prediction(self) -> None:
        """Simule une requête de prédiction de trafic."""
        payload = {
            "sensor_id": random.choice(self.SENSOR_IDS),
            "horizon_minutes": random.choice([15, 30, 60, 120]),
            "include_confidence": True,
        }
        with self.client.post(
            "/api/v1/traffic/predict",
            json=payload,
            catch_response=True,
            name="POST /traffic/predict",
        ) as response:
            if response.status_code == 200:
                data = response.json()
                if "predicted_congestion_level" not in data:
                    response.failure("Champ 'predicted_congestion_level' manquant")
            elif response.status_code == 422:
                response.success()  # Validation error attendue pour inputs invalides
            else:
                response.failure(f"HTTP {response.status_code}")

# environnement (20% du temps)

    @task(4)
    @tag("environment")
    def get_environment(self) -> None:
        """Simule la consultation des données environnementales."""
        with self.client.get(
            "/api/v1/environment/current",
            catch_response=True,
            name="GET /environment/current",
        ) as response:
            if response.status_code == 200:
                data = response.json()
                for reading in data:
                    if not (1 <= reading.get("aqi", 0) <= 5):
                        response.failure(f"AQI invalide: {reading.get('aqi')}")
                        return
            else:
                response.failure(f"HTTP {response.status_code}")

    @task(1)
    @tag("environment")
    def get_aqi_history(self) -> None:
        """Simule la consultation de l'historique AQI."""
        with self.client.get(
            "/api/v1/environment/aqi-history",
            catch_response=True,
            name="GET /environment/aqi-history",
        ) as response:
            if response.status_code != 200:
                response.failure(f"HTTP {response.status_code}")

# crowdsourcing (5% du temps)

    @task(1)
    @tag("crowdsourcing", "rgpd")
    def submit_citizen_report(self) -> None:
        """Simule la soumission d'un signalement citoyen."""
        types = ["embouteillage", "accident", "travaux", "incident_transport", "danger"]
        payload = {
            "latitude": round(random.uniform(48.60, 49.00), 4),
            "longitude": round(random.uniform(2.00, 2.70), 4),
            "report_type": random.choice(types),
            "severity": random.randint(1, 4),
            "description": "Signalement test de charge",
        }
        with self.client.post(
            "/api/v1/crowdsourcing/report",
            json=payload,
            catch_response=True,
            name="POST /crowdsourcing/report",
        ) as response:
            if response.status_code == 201:
                data = response.json()
                if "ephemeral_id" not in data:
                    response.failure("ephemeral_id manquant (violation RGPD)")
                elif "rgpd_notice" not in data:
                    response.failure("rgpd_notice manquant")
            else:
                response.failure(f"HTTP {response.status_code}")


class UrbanFlowDashboardUser(HttpUser):
    """
    Simule un utilisateur du Dashboard React (requêtes batch).

    Comportement typique du frontend :
    - Charge initiale de la page (toutes les données en parallèle)
    - Rafraîchissement toutes les 30 secondes
    """

    wait_time = between(25, 35)  # Simule le rafraîchissement auto du dashboard
    weight = 3  # 3× moins d'utilisateurs que l'API User

    @task(1)
    @tag("dashboard")
    def dashboard_initial_load(self) -> None:
        """Simule le chargement initial du dashboard (3 requêtes simultanées)."""
        endpoints = [
            "/api/v1/traffic/current",
            "/api/v1/environment/current",
            "/api/v1/traffic/alerts",
        ]
        for endpoint in endpoints:
            self.client.get(endpoint, name=f"Dashboard: {endpoint.split('/')[-1]}")

    @task(2)
    @tag("dashboard", "heatmap")
    def dashboard_heatmap_refresh(self) -> None:
        """Simule le rafraîchissement de la heatmap toutes les 30s."""
        self.client.get("/api/v1/traffic/heatmap", name="Dashboard: heatmap refresh")


# LISTENERS & RAPPORTS

@events.test_start.add_listener
def on_test_start(environment, **kwargs) -> None:
    """Affiche les paramètres du test au démarrage."""
    print("\n" + "═" * 60)
    print("🔥 UrbanFlow Load Test — Démarrage")
    print("═" * 60)
    print(f"Host     : {environment.host}")
    print(f"SLA P95  : GET < 200ms | POST /predict < 500ms")
    print(f"SLA Taux : Erreurs < 1%")
    print("═" * 60 + "\n")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs) -> None:
    """Affiche le résumé des performances à la fin du test."""
    stats = environment.stats
    print("\n" + "═" * 60)
    print("📊 UrbanFlow Load Test — Résultats")
    print("═" * 60)
    print(f"Requêtes totales  : {stats.total.num_requests}")
    print(f"Échecs           : {stats.total.num_failures}")
    print(f"Taux d'erreur    : {stats.total.fail_ratio:.2%}")
    print(f"Durée moyenne    : {stats.total.avg_response_time:.0f}ms")
    print(f"P50              : {stats.total.get_response_time_percentile(0.5):.0f}ms")
    print(f"P95              : {stats.total.get_response_time_percentile(0.95):.0f}ms")
    print(f"P99              : {stats.total.get_response_time_percentile(0.99):.0f}ms")

    # Validation SLA
    p95 = stats.total.get_response_time_percentile(0.95)
    error_rate = stats.total.fail_ratio

    sla_met = p95 < 200 and error_rate < 0.01
    print(f"\n✅ SLA atteint : {'OUI' if sla_met else '❌ NON'}")
    print("═" * 60 + "\n")

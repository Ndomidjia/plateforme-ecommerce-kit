"""Mon test de performance / charge sur l'API (voir docs/performance.md).

Usage :
    python api/create_admin.py perf_test "PerfTest!2026"   # une fois
    locust -f scripts/locustfile.py --host=http://127.0.0.1:8000

Puis ouvrir http://localhost:8089 pour piloter le test (nombre
d'utilisateurs simulés, montée en charge), ou en mode headless :
    locust -f scripts/locustfile.py --host=http://127.0.0.1:8000 \
        --headless -u 20 -r 5 -t 60s --csv=docs/assets/perf --html=docs/assets/perf_report.html

Je simule le mélange de pages que parcourrait un utilisateur du dashboard
-- pas les endpoints d'écriture (création de compte, RGPD, recalcul de
modèle) : ceux-ci ont des effets de bord réels (création de comptes,
entraînement d'un modèle de plusieurs minutes, anonymisation de données)
qu'un test de charge répétable ne doit pas déclencher en boucle.
"""
import os
import random

from locust import HttpUser, between, task

USERNAME = os.environ.get("PERF_USERNAME", "perf_test")
PASSWORD = os.environ.get("PERF_PASSWORD", "PerfTest!2026")

# IDs réels du catalogue Retailrocket (vus dans le dashboard, page
# Recommandations) -- pour que /analytics/recommendations/{id} ne tape pas
# systématiquement un produit inconnu (404), ce qui fausserait les temps de
# réponse mesurés.
SAMPLE_ITEM_IDS = [187946, 461686, 5411, 370653, 219512, 298009, 96924, 309778, 257040, 384302]


class DashboardUser(HttpUser):
    """Un utilisateur qui enchaîne les pages du dashboard, comme en usage réel."""
    wait_time = between(1, 3)

    def on_start(self):
        resp = self.client.post(
            "/auth/login",
            data={"username": USERNAME, "password": PASSWORD},
            name="/auth/login",
        )
        resp.raise_for_status()
        self.headers = {"Authorization": f"Bearer {resp.json()['access_token']}"}

    @task(5)
    def overview(self):
        self.client.get("/analytics/overview", headers=self.headers, name="/analytics/overview")

    @task(3)
    def rfm(self):
        self.client.get("/analytics/rfm/summary", headers=self.headers, name="/analytics/rfm/summary")
        self.client.get("/analytics/rfm?limit=50&offset=0", headers=self.headers, name="/analytics/rfm")

    @task(3)
    def churn(self):
        self.client.get("/analytics/churn/summary", headers=self.headers, name="/analytics/churn/summary")
        self.client.get("/analytics/churn?limit=50&offset=0", headers=self.headers, name="/analytics/churn")

    @task(2)
    def funnel(self):
        self.client.get("/analytics/funnel", headers=self.headers, name="/analytics/funnel")

    @task(2)
    def recommendations(self):
        item_id = random.choice(SAMPLE_ITEM_IDS)
        self.client.get(
            f"/analytics/recommendations/{item_id}?limit=10",
            headers=self.headers, name="/analytics/recommendations/[id]",
        )

    @task(2)
    def association_rules(self):
        self.client.get("/analytics/association-rules?limit=50", headers=self.headers, name="/analytics/association-rules")

    @task(2)
    def sentiment(self):
        self.client.get("/analytics/sentiment/summary", headers=self.headers, name="/analytics/sentiment/summary")
        self.client.get("/analytics/sentiment/trend", headers=self.headers, name="/analytics/sentiment/trend")

    @task(1)
    def customer_360(self):
        self.client.get("/analytics/customer-360/summary", headers=self.headers, name="/analytics/customer-360/summary")

    @task(1)
    def retention_estimate(self):
        self.client.get(
            "/analytics/churn/retention-estimate?top_n=500&success_rate=0.3",
            headers=self.headers, name="/analytics/churn/retention-estimate",
        )

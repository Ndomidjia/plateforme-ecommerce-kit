"""Authentification (JWT) et contrôle d'accès par rôle (RBAC) -- jusqu'ici
jamais vérifiés que manuellement en cliquant dans le dashboard. C'est la
frontière de sécurité de toute l'API : un admin/analyst mal cloisonné expose
les endpoints RGPD (données personnelles brutes) ou d'administration."""


def test_login_success_returns_bearer_token(client, admin_token):
    assert isinstance(admin_token, str) and len(admin_token) > 20


def test_login_with_wrong_password_is_rejected(client):
    resp = client.post("/auth/login", data={"username": "admin", "password": "definitely-wrong"})
    assert resp.status_code == 401


def test_login_with_unknown_user_is_rejected(client):
    resp = client.post("/auth/login", data={"username": "no_such_user_xyz", "password": "whatever"})
    assert resp.status_code == 401


def test_unauthenticated_request_is_rejected(client):
    resp = client.get("/analytics/overview")
    assert resp.status_code == 401


def test_invalid_token_is_rejected(client):
    resp = client.get("/analytics/overview", headers={"Authorization": "Bearer not-a-real-jwt"})
    assert resp.status_code == 401


def test_analyst_can_read_analytics(client, analyst_token):
    resp = client.get("/analytics/overview", headers={"Authorization": f"Bearer {analyst_token}"})
    assert resp.status_code == 200


def test_analyst_cannot_access_admin_endpoints(client, analyst_token):
    resp = client.get("/admin/overview", headers={"Authorization": f"Bearer {analyst_token}"})
    assert resp.status_code == 403


def test_analyst_cannot_access_rgpd_endpoints(client, analyst_token):
    resp = client.get("/rgpd/churn/1/export", headers={"Authorization": f"Bearer {analyst_token}"})
    assert resp.status_code == 403


def test_analyst_cannot_create_users(client, analyst_token):
    resp = client.post(
        "/auth/users",
        json={"username": "should_not_be_created", "password": "x", "role": "analyst"},
        headers={"Authorization": f"Bearer {analyst_token}"},
    )
    assert resp.status_code == 403


def test_admin_can_access_admin_endpoints(client, admin_token):
    resp = client.get("/admin/overview", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200


def test_admin_can_access_rgpd_endpoints(client, admin_token):
    # 404 (client inconnu) est un succès ici : ça prouve que le rôle est
    # passé le contrôle RBAC (403 aurait signalé une régression), même si le
    # client id=0 n'existe pas.
    resp = client.get("/rgpd/churn/0/export", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code in (200, 404)

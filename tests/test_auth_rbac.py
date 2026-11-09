"""Mon authentification (JWT) et mon contrôle d'accès par rôle (RBAC) --
jusqu'ici je ne les vérifiais que manuellement en cliquant dans mon
dashboard. C'est la frontière de sécurité de toute mon API : un
admin/analyst mal cloisonné expose mes endpoints RGPD (données personnelles
brutes) ou d'administration."""
import uuid

from sqlalchemy import text


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


def test_deleted_account_token_is_revoked_immediately(client, admin_token, engine):
    """Je vérifie la révocation : un jeton émis pour un compte qu'on supprime
    ensuite ne doit plus fonctionner, sans attendre son expiration naturelle
    (voir api/deps.py -- je revérifie l'existence du compte à chaque requête)."""
    from security import hash_password  # api/ est sur sys.path (voir conftest.py)

    username = f"pytest_revoke_{uuid.uuid4().hex[:8]}"
    password = "Pytest!2026x"
    with engine.begin() as conn:
        conn.execute(
            text("INSERT INTO app.users (username, hashed_password, role) VALUES (:u, :p, 'analyst')"),
            {"u": username, "p": hash_password(password)},
        )

    login_resp = client.post("/auth/login", data={"username": username, "password": password})
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]

    # Le jeton fonctionne tant que le compte existe.
    resp = client.get("/analytics/overview", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200

    # Un admin supprime le compte.
    del_resp = client.delete(f"/auth/users/{username}", headers={"Authorization": f"Bearer {admin_token}"})
    assert del_resp.status_code in (200, 204)

    # Le même jeton, toujours non expiré, doit maintenant être rejeté.
    resp = client.get("/analytics/overview", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401


def test_login_locks_out_after_too_many_failed_attempts(client):
    """Anti-bruteforce par compte (voir api/rate_limit.py) : 5 échecs
    verrouillent le compte 15 min, même avec le bon mot de passe ensuite.
    Je ne teste pas ici le seuil par IP (20 échecs) : le déclencher
    verrouillerait l'IP partagée par tout le TestClient de cette session et
    casserait les autres tests pendant 15 min."""
    import rate_limit

    username = f"pytest_lockout_{uuid.uuid4().hex[:8]}"
    ip = "testclient"  # IP par défaut vue par Starlette TestClient

    try:
        for _ in range(5):
            resp = client.post("/auth/login", data={"username": username, "password": "wrong"})
            assert resp.status_code == 401

        # Le compte est maintenant verrouillé -- même un mot de passe correct
        # (hypothétique ici, le compte n'existe pas) est rejeté en 429, pas 401.
        resp = client.post("/auth/login", data={"username": username, "password": "whatever"})
        assert resp.status_code == 429
        assert "Retry-After" in resp.headers
    finally:
        rate_limit.reset(username, ip)


def test_login_resets_failed_attempts_after_success(client, engine):
    """Un login réussi repart sur une ardoise propre : des échecs qui
    n'atteignent pas le seuil ne doivent pas s'accumuler indéfiniment vers
    un verrouillage après une connexion réussie entre-temps."""
    import rate_limit
    from security import hash_password

    username = f"pytest_reset_{uuid.uuid4().hex[:8]}"
    password = "Pytest!2026x"
    ip = "testclient"
    with engine.begin() as conn:
        conn.execute(
            text("INSERT INTO app.users (username, hashed_password, role) VALUES (:u, :p, 'analyst')"),
            {"u": username, "p": hash_password(password)},
        )

    try:
        for _ in range(3):  # sous le seuil de 5
            resp = client.post("/auth/login", data={"username": username, "password": "wrong"})
            assert resp.status_code == 401

        resp = client.post("/auth/login", data={"username": username, "password": password})
        assert resp.status_code == 200  # connexion réussie -> compteur remis à zéro

        for _ in range(3):  # encore sous le seuil, en repartant de zéro
            resp = client.post("/auth/login", data={"username": username, "password": "wrong"})
            assert resp.status_code == 401

        resp = client.post("/auth/login", data={"username": username, "password": password})
        assert resp.status_code == 200  # toujours pas verrouillé : le compteur a bien été remis à zéro
    finally:
        rate_limit.reset(username, ip)
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM app.users WHERE username = :u"), {"u": username})

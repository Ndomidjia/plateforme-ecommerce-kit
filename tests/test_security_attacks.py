"""Simulation d'attaque sur mon API -- je me mets à la place d'un attaquant
pour vérifier que mes défenses (anti-bruteforce, JWT, requêtes paramétrées,
RBAC) tiennent réellement sous tentative d'exploitation, pas seulement en
théorie dans docs/securite.md. Je couvre les quatre familles de vecteurs
qu'un pentest manuel ciblerait en priorité sur une API à authentification
par jeton : bruteforce/anti-bruteforce, falsification de JWT, injection
SQL, élévation de privilèges.

Je documente le résultat de cette simulation dans docs/securite.md, y
compris si je ne trouve rien à exploiter : une tentative d'attaque qui
échoue proprement est un résultat positif à montrer en soutenance, pas un
test sans valeur.
"""
import base64
import json
import uuid
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from sqlalchemy import text


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """Ces tests déclenchent volontairement mon anti-bruteforce
    (api/rate_limit.py), dont les compteurs sont des dictionnaires en
    mémoire partagés par tout le TestClient de la session pytest (même IP
    "testclient" vue par Starlette pour toutes les requêtes, voir
    tests/test_auth_rbac.py). Je nettoie avant ET après chaque test de ce
    fichier pour ne dépendre ni de l'ordre d'exécution des autres fichiers
    de tests, ni laisser un verrouillage fuiter vers les tests suivants."""
    import rate_limit
    rate_limit.reset("_security_test_cleanup", "testclient")
    yield
    rate_limit.reset("_security_test_cleanup", "testclient")


def _b64url(data: dict) -> bytes:
    return base64.urlsafe_b64encode(json.dumps(data).encode()).rstrip(b"=")


# ---------------------------------------------------------------------------
# 1. Bruteforce / anti-bruteforce -- complète tests/test_auth_rbac.py, qui
#    vérifie déjà le verrouillage par compte. J'ajoute ici deux scénarios
#    d'attaquant qu'il ne couvre pas encore.
# ---------------------------------------------------------------------------

def test_login_error_does_not_reveal_account_existence(client, engine):
    """Un attaquant qui énumère des noms de compte ne doit pas pouvoir
    distinguer "ce compte n'existe pas" de "ce compte existe, mauvais mot
    de passe" via le code HTTP ou le message renvoyé -- sinon il peut
    constituer une liste de comptes valides avant même de bruteforcer un
    mot de passe."""
    from security import hash_password

    username = f"pytest_enum_{uuid.uuid4().hex[:8]}"
    ghost = f"pytest_ghost_{uuid.uuid4().hex[:8]}"
    password = "Pytest!2026x"
    with engine.begin() as conn:
        conn.execute(
            text("INSERT INTO app.users (username, hashed_password, role) VALUES (:u, :p, 'analyst')"),
            {"u": username, "p": hash_password(password)},
        )

    try:
        resp_known_wrong_pw = client.post("/auth/login", data={"username": username, "password": "wrong"})
        resp_unknown = client.post("/auth/login", data={"username": ghost, "password": "whatever"})

        assert resp_known_wrong_pw.status_code == resp_unknown.status_code == 401
        assert resp_known_wrong_pw.json()["detail"] == resp_unknown.json()["detail"]
    finally:
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM app.users WHERE username = :u"), {"u": username})


def test_credential_stuffing_spray_across_accounts_triggers_ip_lockout(client):
    """Un attaquant qui essaie un même mot de passe deviné sur 20 comptes
    différents (une seule tentative par compte, pour rester sous mon seuil
    par compte de 5) doit tout de même se faire bloquer par mon seuil par
    IP (20 échecs / 15 min, voir api/rate_limit.py) -- sinon le
    verrouillage par compte seul ne protège pas contre un credential
    stuffing qui vise large plutôt qu'un compte précis."""
    for _ in range(20):
        username = f"pytest_spray_{uuid.uuid4().hex[:8]}"
        resp = client.post("/auth/login", data={"username": username, "password": "P@ssw0rd123"})
        assert resp.status_code == 401

    resp = client.post(
        "/auth/login",
        data={"username": f"pytest_spray_{uuid.uuid4().hex[:8]}", "password": "P@ssw0rd123"},
    )
    assert resp.status_code == 429
    assert "Retry-After" in resp.headers


# ---------------------------------------------------------------------------
# 2. Falsification de JWT
# ---------------------------------------------------------------------------

def test_token_with_tampered_signature_is_rejected(client, analyst_token):
    """Je modifie un seul caractère de la signature d'un vrai jeton --
    toute altération, même minime, doit invalider la vérification HMAC."""
    header, payload, signature = analyst_token.split(".")
    tampered_signature = ("A" if signature[0] != "A" else "B") + signature[1:]
    forged = f"{header}.{payload}.{tampered_signature}"
    resp = client.get("/analytics/overview", headers={"Authorization": f"Bearer {forged}"})
    assert resp.status_code == 401


def test_token_signed_with_wrong_secret_is_rejected(client):
    """Un attaquant qui ne connaît pas JWT_SECRET_KEY (voir Vault,
    docs/securite.md) ne doit pas pouvoir fabriquer un jeton valide, même
    en devinant parfaitement le format des claims attendus."""
    from config import JWT_ALGORITHM

    exp = datetime.now(timezone.utc) + timedelta(minutes=30)
    forged = jwt.encode(
        {"sub": "whoever", "role": "admin", "exp": exp},
        "ce-n-est-pas-le-vrai-secret-de-l-api",
        algorithm=JWT_ALGORITHM,
    )
    resp = client.get("/admin/overview", headers={"Authorization": f"Bearer {forged}"})
    assert resp.status_code == 401


def test_token_with_algorithm_none_is_rejected(client):
    """Attaque classique "alg: none" : un jeton sans signature, que
    certaines bibliothèques JWT mal configurées acceptent en faisant
    confiance à l'algorithme déclaré dans l'en-tête plutôt qu'à celui
    attendu côté serveur. api/security.py appelle jwt.decode avec
    algorithms=[JWT_ALGORITHM] explicite -- je vérifie que PyJWT refuse
    bien ce jeton plutôt que de s'y fier."""
    header = _b64url({"alg": "none", "typ": "JWT"})
    exp = int((datetime.now(timezone.utc) + timedelta(minutes=30)).timestamp())
    payload = _b64url({"sub": "admin", "role": "admin", "exp": exp})
    forged = f"{header.decode()}.{payload.decode()}."

    resp = client.get("/admin/overview", headers={"Authorization": f"Bearer {forged}"})
    assert resp.status_code == 401


def test_token_with_forged_admin_role_claim_is_rejected(client, analyst_token):
    """Je prends un vrai jeton analyst, je décode ses claims sans vérifier
    la signature (ce qu'un attaquant peut faire aussi : le payload JWT
    n'est que du base64, pas chiffré), je remplace role par admin, et je
    re-signe avec un secret que je n'ai évidemment pas le droit de
    connaître. Sans le vrai secret de l'API, cette nouvelle signature ne
    peut pas être valide."""
    from config import JWT_ALGORITHM

    claims = jwt.decode(analyst_token, options={"verify_signature": False})
    assert claims["role"] == "analyst"
    claims["role"] = "admin"
    forged = jwt.encode(claims, "secret-devine-par-l-attaquant-pas-le-vrai", algorithm=JWT_ALGORITHM)

    resp = client.get("/admin/overview", headers={"Authorization": f"Bearer {forged}"})
    assert resp.status_code == 401


def test_expired_token_is_rejected(client):
    """Même signé avec le vrai secret, un jeton dont `exp` est dans le
    passé doit être rejeté -- je vérifie aussi le message précis renvoyé
    par api/deps.py pour m'assurer que c'est bien l'expiration qui est
    détectée, pas une autre validation qui échouerait par coïncidence."""
    from config import JWT_ALGORITHM, JWT_SECRET_KEY

    expired = jwt.encode(
        {"sub": "admin", "role": "admin", "exp": datetime.now(timezone.utc) - timedelta(minutes=5)},
        JWT_SECRET_KEY,
        algorithm=JWT_ALGORITHM,
    )
    resp = client.get("/analytics/overview", headers={"Authorization": f"Bearer {expired}"})
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Jeton expiré"


# ---------------------------------------------------------------------------
# 3. Injection SQL -- api/ utilise SQLAlchemy Core avec text() et des
#    paramètres liés (:nom) partout où une valeur vient du client ; je
#    vérifie ici que ça tient face aux payloads classiques plutôt que de
#    le relire seulement dans le code.
# ---------------------------------------------------------------------------

SQLI_PAYLOADS = [
    "' OR '1'='1",
    "' OR '1'='1' --",
    "'; DROP TABLE app.users; --",
    "' UNION SELECT username, hashed_password, role FROM app.users --",
    "admin'--",
]


@pytest.mark.parametrize("payload", SQLI_PAYLOADS)
def test_login_rejects_sql_injection_in_credentials(client, payload):
    """Aucun de ces payloads ne doit contourner l'authentification ni
    faire planter l'API (un code 500 révélerait une requête mal formée
    côté serveur, donc une faille potentielle même sans fuite de
    données)."""
    resp = client.post("/auth/login", data={"username": payload, "password": payload})
    assert resp.status_code == 401


@pytest.mark.parametrize("payload", SQLI_PAYLOADS)
def test_rfm_lookup_rejects_sql_injection_in_path_param(client, admin_token, payload):
    resp = client.get(
        "/analytics/rfm/" + payload,
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    # Requête paramétrée (:cid) -- un identifiant injecté ne matche jamais
    # rien : 404 attendu, jamais 500 ni 200 avec des données imprévues.
    assert resp.status_code == 404


@pytest.mark.parametrize("payload", SQLI_PAYLOADS)
def test_rfm_list_rejects_sql_injection_in_query_param(client, admin_token, payload):
    resp = client.get(
        "/analytics/rfm",
        params={"segment": payload},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert resp.json() == []


# ---------------------------------------------------------------------------
# 4. Élévation de privilèges -- balayage systématique de mes endpoints
#    réservés à l'admin plutôt qu'un test au cas par cas : si j'ajoute un
#    jour un nouvel endpoint admin et que j'oublie require_role("admin"),
#    c'est ici qu'il faut l'ajouter à ADMIN_ONLY_ENDPOINTS pour que ce test
#    le détecte automatiquement.
# ---------------------------------------------------------------------------

ADMIN_ONLY_ENDPOINTS = [
    ("GET", "/admin/overview"),
    ("GET", "/admin/recompute/status"),
    ("POST", "/admin/recompute/rfm_olist"),
    ("GET", "/admin/models"),
    ("POST", "/admin/models/churn_scoring/rollback"),
    ("GET", "/auth/users"),
    ("DELETE", "/auth/users/pytest_security_sweep_nonexistent"),
    ("GET", "/rgpd/churn/1/export"),
    ("DELETE", "/rgpd/churn/1"),
]


@pytest.mark.parametrize("method,path", ADMIN_ONLY_ENDPOINTS)
def test_unauthenticated_request_is_rejected_on_every_admin_endpoint(client, method, path):
    resp = client.request(method, path)
    assert resp.status_code == 401


@pytest.mark.parametrize("method,path", ADMIN_ONLY_ENDPOINTS)
def test_analyst_role_is_rejected_on_every_admin_endpoint(client, analyst_token, method, path):
    """Un compte analyst qui tente d'atteindre un endpoint admin -- le
    scénario d'élévation de privilèges le plus direct avec mon RBAC à deux
    rôles (voir api/deps.py). require_role() doit couper la requête avant
    qu'elle n'atteigne la moindre logique métier, donc aucun effet de bord
    même sur les endpoints qui écrivent (recalcul, rollback, suppression)."""
    resp = client.request(method, path, headers={"Authorization": f"Bearer {analyst_token}"})
    assert resp.status_code == 403

"""Mes fixtures partagées.

Je réponds ici à la question de soutenance "aucun test automatisé n'existe,
comment la fiabilité a-t-elle été vérifiée jusqu'à présent ?" : avant ce
dossier, je vérifiais manuellement (contrôles SQL de sql/99_controles.sql
exécutés à la main après chaque ETL, métriques de validation croisée
relues dans les logs, inspection visuelle du dashboard pendant mon
développement -- voir docs/journal-de-bord.md pour des incidents que j'ai
trouvés ainsi). Ce dossier formalise et automatise une partie de ça
(qualité des données, RBAC de l'API, garde-fou de promotion de modèle) ;
voir docs/tests.md pour le périmètre que je couvre et, également important,
ce que je ne couvre PAS encore (pas de test sur mes notebooks EDA, pas de
test end-to-end de mon dashboard React).

Mes tests tournent contre la même base PostgreSQL que mon développement
(pas de base de test isolée) : choix que j'assume, proportionné à l'échelle
de mon projet (voir docs/tests.md) -- ils lisent les données existantes
(contrôles qualité, RBAC) ou nettoient explicitement ce qu'ils écrivent
(modèle factice dans test_model_registry.py), sans jamais toucher aux
tables analytics.* réelles (churn_scores, customer_360...).
"""
import importlib.util
import os
import sys
from pathlib import Path

import pytest
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

REPO_ROOT = Path(__file__).resolve().parent.parent
API_DIR = REPO_ROOT / "api"
ANALYTICS_DIR = REPO_ROOT / "analytics"

load_dotenv(REPO_ROOT / ".env")


def load_analytics_module(name: str):
    """Charge un module analytics/<name>.py par chemin direct (importlib) et
    l'enregistre dans sys.modules sous son nom, SANS jamais ajouter
    analytics/ à sys.path (conflit de nom avec api/config.py, voir
    ci-dessus) -- mes scripts analytics/*.py importent `config` seulement à
    l'intérieur de main() (jamais en tête de module) précisément pour rester
    chargeables ainsi, pour tester leurs fonctions pures sans dépendre d'une
    base de données. L'enregistrement dans sys.modules permet aussi aux
    imports entre scripts analytics/ entre eux (ex: analyse_seuil_bot.py
    importe recommend_retailrocket.py) de se résoudre via le cache --
    charger la dépendance en premier (voir tests/unit/) suffit alors."""
    if name in sys.modules:
        return sys.modules[name]
    path = ANALYTICS_DIR / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module

# Seul répertoire que j'ajoute à sys.path pour toute la session de tests :
# api/ et analytics/ définissent chacun leur propre config.py (contenu
# différent, voir api/config.py vs analytics/config.py) -- les mélanger sur
# sys.path ferait résoudre `import config` de façon non déterministe selon
# l'ordre d'import. Je charge analytics/model_registry.py par chemin direct
# (importlib) plutôt que par sys.path dans test_model_registry.py,
# précisément pour éviter ce piège.
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))


@pytest.fixture(scope="session")
def engine():
    return create_engine(os.environ["DATABASE_URL"])


@pytest.fixture(scope="session")
def client():
    from fastapi.testclient import TestClient
    from main import app
    return TestClient(app)


def _make_throwaway_user(engine, role: str) -> tuple[str, str]:
    import uuid
    from security import hash_password  # api/security.py (api/ est sur sys.path)

    username = f"pytest_{role}_{uuid.uuid4().hex[:8]}"
    password = "Pytest!2026x"
    with engine.begin() as conn:
        conn.execute(
            text("INSERT INTO app.users (username, hashed_password, role) VALUES (:u, :p, :r)"),
            {"u": username, "p": hash_password(password), "r": role},
        )
    return username, password


@pytest.fixture(scope="session")
def admin_token(engine, client):
    username, password = _make_throwaway_user(engine, "admin")
    resp = client.post("/auth/login", data={"username": username, "password": password})
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    yield token
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM app.users WHERE username = :u"), {"u": username})


@pytest.fixture(scope="session")
def analyst_token(engine, client):
    username, password = _make_throwaway_user(engine, "analyst")
    resp = client.post("/auth/login", data={"username": username, "password": password})
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    yield token
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM app.users WHERE username = :u"), {"u": username})

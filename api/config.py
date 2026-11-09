"""Configuration de l'API (lit Vault si disponible, sinon le fichier .env)."""
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine

from secrets_provider import get_secret

load_dotenv()

# Les deux secrets sensibles (mot de passe DB inclus dans l'URL de connexion,
# clé de signature JWT) passent par Vault quand il est configuré -- voir
# secrets_provider.py et docker-compose.yml (service `vault`). Le reste
# (algorithme, durée de vie du jeton) n'est pas un secret, juste de la
# configuration : inutile de le vaulter.
DATABASE_URL = get_secret("ecommerce/api", "database_url", "DATABASE_URL")
JWT_SECRET_KEY = get_secret("ecommerce/api", "jwt_secret_key", "JWT_SECRET_KEY")
JWT_ALGORITHM = os.environ.get("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))

def get_engine():
    # pool_pre_ping : teste chaque connexion avant de la réutiliser et la
    # remplace silencieusement si elle est morte. Sans ça, un redémarrage de
    # PostgreSQL (ex: Docker Desktop relancé) laisse le pool de connexions
    # de l'API dans un état invalide -- chaque requête échoue en 500
    # (OperationalError "connection abort") jusqu'à un redémarrage manuel de
    # l'API. Incident réel rencontré et corrigé le 28/07 (voir journal de bord).
    #
    # pool_size/max_overflow : les valeurs par défaut de SQLAlchemy (5 + 10,
    # soit 15 connexions max) saturaient dès 20 utilisateurs simulés en
    # charge (voir docs/performance.md) -- chaque requête en attente d'une
    # connexion au-delà de ce plafond finissait en 500
    # (sqlalchemy.exc.TimeoutError après 30s). PostgreSQL accepte par défaut
    # jusqu'à 100 connexions simultanées (max_connections) : 40 me laisse de
    # la marge pour d'autres clients (psql, scripts analytics/) sans
    # épuiser le pool de PostgreSQL lui-même.
    return create_engine(DATABASE_URL, pool_pre_ping=True, pool_size=20, max_overflow=20)

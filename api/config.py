"""Configuration de l'API (lit le fichier .env)."""
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine

load_dotenv()

DATABASE_URL = os.environ["DATABASE_URL"]
JWT_SECRET_KEY = os.environ["JWT_SECRET_KEY"]
JWT_ALGORITHM = os.environ.get("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))

def get_engine():
    # pool_pre_ping : teste chaque connexion avant de la réutiliser et la
    # remplace silencieusement si elle est morte. Sans ça, un redémarrage de
    # PostgreSQL (ex: Docker Desktop relancé) laisse le pool de connexions
    # de l'API dans un état invalide -- chaque requête échoue en 500
    # (OperationalError "connection abort") jusqu'à un redémarrage manuel de
    # l'API. Incident réel rencontré et corrigé le 28/07 (voir journal de bord).
    return create_engine(DATABASE_URL, pool_pre_ping=True)

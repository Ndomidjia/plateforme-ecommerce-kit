"""Connexion à PostgreSQL pour l'API (une connexion par requête HTTP)."""
from config import get_engine

engine = get_engine()

def get_db():
    with engine.connect() as conn:
        yield conn

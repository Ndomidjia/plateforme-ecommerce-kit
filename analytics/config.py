"""Configuration commune des modules analytics (lit Vault si disponible,
sinon le fichier .env -- voir secrets_provider.py)."""
from dotenv import load_dotenv
from sqlalchemy import create_engine

from secrets_provider import get_secret

load_dotenv()

DATABASE_URL = get_secret("ecommerce/api", "database_url", "DATABASE_URL")

def get_engine():
    return create_engine(DATABASE_URL)

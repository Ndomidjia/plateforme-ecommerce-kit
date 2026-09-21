"""Configuration commune des modules analytics (lit le fichier .env)."""
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine

load_dotenv()

DATABASE_URL = os.environ["DATABASE_URL"]

def get_engine():
    return create_engine(DATABASE_URL)

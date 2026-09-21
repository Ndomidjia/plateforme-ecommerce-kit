"""Configuration commune du pipeline ETL (lit le fichier .env)."""
import os
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine

load_dotenv()

DATABASE_URL = os.environ["DATABASE_URL"]
RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"

def get_engine():
    return create_engine(DATABASE_URL)

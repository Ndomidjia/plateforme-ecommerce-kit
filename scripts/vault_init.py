"""Pousse mes secrets (.env) dans Vault (voir docker-compose.yml, service
`vault`, et docs/securite.md).

A lancer une fois après `docker compose up -d` (Vault doit tourner), avant
de démarrer l'API ou les scripts analytics -- mais rien ne casse si je
l'oublie : api/config.py et analytics/config.py retombent sur .env tant que
ce secret n'existe pas encore dans Vault (voir secrets_provider.py dans
chacun des deux répertoires). Ce script est donc l'étape qui fait
effectivement passer du stockage en clair à Vault, pas une étape bloquante.

Usage : python scripts/vault_init.py
"""
import os
import sys
from pathlib import Path

import hvac
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(REPO_ROOT / ".env")


def main():
    vault_addr = os.environ.get("VAULT_ADDR", "http://localhost:8200")
    vault_token = os.environ.get("VAULT_TOKEN") or os.environ.get("VAULT_DEV_ROOT_TOKEN")
    if not vault_token:
        print("VAULT_TOKEN (ou VAULT_DEV_ROOT_TOKEN) absent de .env -- rien à faire.")
        sys.exit(1)

    client = hvac.Client(url=vault_addr, token=vault_token)
    if not client.is_authenticated():
        print(f"Impossible de m'authentifier auprès de Vault ({vault_addr}). Est-il démarré "
              f"(`docker compose up -d vault`) ?")
        sys.exit(1)

    client.secrets.kv.v2.create_or_update_secret(
        path="ecommerce/api",
        secret={
            "database_url": os.environ["DATABASE_URL"],
            "jwt_secret_key": os.environ["JWT_SECRET_KEY"],
        },
    )
    print(f"Secrets écrits dans Vault ({vault_addr}) sous secret/ecommerce/api.")
    print("L'API et les scripts analytics les liront désormais depuis Vault plutôt que .env.")


if __name__ == "__main__":
    main()

# Construit depuis la racine du dépôt (contexte = racine, pas api/), car
# requirements.txt vit à la racine, partagé avec analytics/ -- voir
# docs/deploiement.md pour la commande de build exacte.
FROM python:3.12-slim

# gcc/libpq-dev : nécessaires pour compiler certaines dépendances natives
# (ex. torch sur une architecture pour laquelle PyPI n'a pas de roue
# précompilée) -- je les garde même si la majorité de mes dépendances a des
# roues prêtes à l'emploi, pour ne pas découvrir ce manque uniquement sur le
# serveur de déploiement.
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY api/ ./api/
COPY analytics/ ./analytics/
COPY scripts/vault_init.py ./scripts/vault_init.py

WORKDIR /app/api

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=5 \
    CMD curl -sf http://127.0.0.1:8000/health || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

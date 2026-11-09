"""Mon fournisseur de secrets : lit depuis HashiCorp Vault (service `vault`
de docker-compose.yml) quand c'est configuré et disponible, et retombe sur
les variables d'environnement (.env, via python-dotenv) sinon.

Le repli est délibéré, pas un bug : en CI (.github/workflows/ci.yml), Vault
ne tourne pas du tout, et même en local je n'ai pas forcément lancé le
conteneur `vault` ou exécuté `scripts/vault_init.py` -- l'API doit rester
utilisable dans les deux cas. Voir docs/securite.md pour la justification
et les limites de cette intégration (mode dev Vault uniquement, pas un
déploiement de production).

Dupliqué à l'identique dans analytics/secrets_provider.py plutôt que
partagé : api/ et analytics/ tournent dans deux répertoires/process
distincts avec chacun leur propre config.py (même raison que pour
MODEL_LIVE_TABLES dans api/routers/admin.py).
"""
import logging
import os

log = logging.getLogger("api.secrets_provider")

_client = None
_tried_vault = False


def _get_vault_client():
    global _client, _tried_vault
    if _tried_vault:
        return _client
    _tried_vault = True

    vault_addr = os.environ.get("VAULT_ADDR")
    vault_token = os.environ.get("VAULT_TOKEN") or os.environ.get("VAULT_DEV_ROOT_TOKEN")
    if not vault_addr or not vault_token:
        log.info("VAULT_ADDR/VAULT_TOKEN absents -- secrets lus depuis .env")
        return None

    try:
        import hvac
        import requests
        from requests.adapters import HTTPAdapter

        # timeout court + zéro retry : si Vault n'est pas démarré (cas
        # fréquent en dev, voir docs/securite.md), je veux échouer vite et
        # retomber sur .env plutôt que subir les ~4 tentatives avec backoff
        # que `requests` fait par défaut (plusieurs secondes cumulées, même
        # avec un timeout court par tentative).
        session = requests.Session()
        session.mount("http://", HTTPAdapter(max_retries=0))
        session.mount("https://", HTTPAdapter(max_retries=0))
        client = hvac.Client(url=vault_addr, token=vault_token, timeout=2, session=session)
        if not client.is_authenticated():
            log.warning("Vault configuré (%s) mais jeton invalide -- repli sur .env", vault_addr)
            return None
    except Exception as exc:
        log.warning("Vault injoignable (%s) -- repli sur .env : %s", vault_addr, exc)
        return None

    _client = client
    log.info("Secrets lus depuis Vault (%s)", vault_addr)
    return _client


def get_secret(vault_path: str, vault_key: str, env_var: str) -> str:
    """Lit `vault_key` dans le secret KV v2 situé à `vault_path` si Vault
    est disponible et que le secret y existe, sinon retombe sur la variable
    d'environnement `env_var`."""
    client = _get_vault_client()
    if client is not None:
        try:
            secret = client.secrets.kv.v2.read_secret_version(path=vault_path, raise_on_deleted_version=True)
            return secret["data"]["data"][vault_key]
        except Exception as exc:
            log.warning(
                "Lecture Vault échouée pour secret/%s (clé %s) -- repli sur %s : %s",
                vault_path, vault_key, env_var, exc,
            )

    return os.environ[env_var]

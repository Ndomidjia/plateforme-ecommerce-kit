"""Ma protection anti-bruteforce sur /auth/login.

Je limite les tentatives de connexion échouées, par compte ET par adresse
IP, avec un verrouillage temporaire une fois le seuil dépassé :
- par compte (5 échecs / 15 min) : empêche de bruteforcer un mot de passe
  précis, même depuis des IP différentes ;
- par IP (20 échecs / 15 min) : empêche de "sprayer" plusieurs comptes
  connus depuis une même source, seuil plus large pour ne pas bloquer un
  oubli de mot de passe isolé.

Compteurs en mémoire dans le processus API, comme le suivi des recalculs
dans api/routers/admin.py -- même limite assumée : ne survit pas à un
redémarrage de l'API, ne fonctionnerait pas avec plusieurs workers uvicorn
(une vraie solution partagée type Redis serait nécessaire en production).
Pour ce projet à instance unique, c'est suffisant pour démontrer et tester
la protection.
"""
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

PER_ACCOUNT_MAX_ATTEMPTS = 5
PER_ACCOUNT_WINDOW = timedelta(minutes=15)
PER_ACCOUNT_LOCKOUT = timedelta(minutes=15)

PER_IP_MAX_ATTEMPTS = 20
PER_IP_WINDOW = timedelta(minutes=15)
PER_IP_LOCKOUT = timedelta(minutes=15)


@dataclass
class _Bucket:
    attempts: list = field(default_factory=list)
    locked_until: datetime | None = None


_by_account: dict[str, _Bucket] = defaultdict(_Bucket)
_by_ip: dict[str, _Bucket] = defaultdict(_Bucket)


def _check_and_prune(bucket: _Bucket, window: timedelta) -> timedelta | None:
    """Retourne le temps restant si verrouillé, sinon None (et nettoie les
    tentatives sorties de la fenêtre glissante)."""
    now = datetime.now(timezone.utc)
    if bucket.locked_until is not None:
        if now < bucket.locked_until:
            return bucket.locked_until - now
        bucket.locked_until = None
        bucket.attempts = []
    bucket.attempts = [t for t in bucket.attempts if now - t < window]
    return None


def seconds_until_unlocked(username: str, ip: str) -> float | None:
    """A appeler AVANT de vérifier le mot de passe. Retourne le nombre de
    secondes avant déverrouillage si le compte ou l'IP est actuellement
    verrouillé, sinon None (la tentative peut continuer)."""
    remaining = _check_and_prune(_by_account[username], PER_ACCOUNT_WINDOW)
    if remaining is not None:
        return remaining.total_seconds()
    remaining = _check_and_prune(_by_ip[ip], PER_IP_WINDOW)
    if remaining is not None:
        return remaining.total_seconds()
    return None


def record_failed_attempt(username: str, ip: str) -> None:
    now = datetime.now(timezone.utc)

    account_bucket = _by_account[username]
    account_bucket.attempts.append(now)
    if len(account_bucket.attempts) >= PER_ACCOUNT_MAX_ATTEMPTS:
        account_bucket.locked_until = now + PER_ACCOUNT_LOCKOUT
        account_bucket.attempts = []

    ip_bucket = _by_ip[ip]
    ip_bucket.attempts.append(now)
    if len(ip_bucket.attempts) >= PER_IP_MAX_ATTEMPTS:
        ip_bucket.locked_until = now + PER_IP_LOCKOUT
        ip_bucket.attempts = []


def reset(username: str, ip: str) -> None:
    """A appeler après une connexion réussie : repart sur une ardoise
    propre plutôt que de laisser des échecs anciens s'accumuler vers un
    futur verrouillage injustifié."""
    _by_account.pop(username, None)
    _by_ip.pop(ip, None)

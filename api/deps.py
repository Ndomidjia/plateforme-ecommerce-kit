"""Dépendances FastAPI : utilisateur courant (JWT) et contrôle des rôles (RBAC)."""
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import text
from sqlalchemy.engine import Connection

from database import get_db
from security import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

def get_current_user(token: str = Depends(oauth2_scheme), db: Connection = Depends(get_db)) -> dict:
    """Décode le JWT et renvoie {"username", "role"}.

    Je revérifie l'existence du compte en base à chaque requête (une requête
    de plus par appel, négligeable ici) plutôt que de faire confiance au
    contenu du jeton pendant toute sa durée de vie (60 min par défaut) :
    c'est ce qui me permet de révoquer l'accès immédiatement quand un compte
    est supprimé, sans attendre l'expiration naturelle du jeton. Je relis
    aussi le rôle depuis la base (pas celui du jeton) : un changement de
    rôle entre-temps est donc pris en compte tout de suite lui aussi.
    """
    try:
        payload = decode_access_token(token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Jeton expiré")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Jeton invalide")

    username = payload["sub"]
    row = db.execute(
        text("SELECT role FROM app.users WHERE username = :u"), {"u": username}
    ).mappings().first()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Compte supprimé ou désactivé -- jeton révoqué",
        )

    return {"username": username, "role": row["role"]}

def require_role(*allowed_roles: str):
    """Fabrique une dépendance qui n'autorise que les rôles listés."""
    def check_role(user: dict = Depends(get_current_user)) -> dict:
        if user["role"] not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Rôle '{user['role']}' non autorisé pour cette action",
            )
        return user
    return check_role

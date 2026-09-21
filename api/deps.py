"""Dépendances FastAPI : utilisateur courant (JWT) et contrôle des rôles (RBAC)."""
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from security import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    """Décode le JWT et renvoie {"username", "role"}.

    Ne revérifie pas l'existence de l'utilisateur en base à chaque requête
    (on fait confiance au contenu du jeton pendant sa durée de vie, 60 min
    par défaut) : plus simple, au prix de ne pas pouvoir révoquer un jeton
    avant son expiration si un compte est désactivé entre-temps.
    """
    try:
        payload = decode_access_token(token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Jeton expiré")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Jeton invalide")

    return {"username": payload["sub"], "role": payload["role"]}

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

"""Authentification (login) et gestion des comptes API (admin uniquement)."""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.engine import Connection

from database import get_db
from deps import require_role
from security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class UserCreate(BaseModel):
    username: str
    password: str
    role: str  # "admin" ou "analyst"

class UserOut(BaseModel):
    username: str
    role: str

class UserWithMeta(BaseModel):
    username: str
    role: str
    created_at: str

@router.post("/login", response_model=Token)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Connection = Depends(get_db)):
    row = db.execute(
        text("SELECT username, hashed_password, role FROM app.users WHERE username = :username"),
        {"username": form.username},
    ).mappings().first()

    if row is None or not verify_password(form.password, row["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Identifiants invalides",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token(username=row["username"], role=row["role"])
    return Token(access_token=token)

@router.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    db: Connection = Depends(get_db),
    _admin: dict = Depends(require_role("admin")),
):
    if payload.role not in ("admin", "analyst"):
        raise HTTPException(status_code=422, detail="role doit être 'admin' ou 'analyst'")

    exists = db.execute(
        text("SELECT 1 FROM app.users WHERE username = :username"),
        {"username": payload.username},
    ).first()
    if exists:
        raise HTTPException(status_code=409, detail="Ce nom d'utilisateur existe déjà")

    db.execute(
        text("INSERT INTO app.users (username, hashed_password, role) "
             "VALUES (:username, :hashed_password, :role)"),
        {"username": payload.username, "hashed_password": hash_password(payload.password), "role": payload.role},
    )
    db.commit()
    return UserOut(username=payload.username, role=payload.role)

@router.get("/users", response_model=list[UserWithMeta])
def list_users(db: Connection = Depends(get_db), _admin: dict = Depends(require_role("admin"))):
    rows = db.execute(
        text("SELECT username, role, created_at::text FROM app.users ORDER BY created_at")
    ).mappings().all()
    return rows

@router.delete("/users/{username}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    username: str,
    db: Connection = Depends(get_db),
    admin: dict = Depends(require_role("admin")),
):
    if username == admin["username"]:
        raise HTTPException(status_code=400, detail="Impossible de supprimer son propre compte")

    row = db.execute(
        text("SELECT role FROM app.users WHERE username = :username"), {"username": username}
    ).mappings().first()
    if row is None:
        raise HTTPException(status_code=404, detail="Utilisateur inconnu")

    if row["role"] == "admin":
        admin_count = db.execute(text("SELECT COUNT(*) FROM app.users WHERE role = 'admin'")).scalar()
        if admin_count <= 1:
            raise HTTPException(status_code=400, detail="Impossible de supprimer le dernier compte admin")

    db.execute(text("DELETE FROM app.users WHERE username = :username"), {"username": username})
    db.commit()

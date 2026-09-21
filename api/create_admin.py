"""Crée le tout premier compte admin (nécessaire au démarrage : l'endpoint
POST /auth/users exige déjà d'être admin, donc ce premier compte doit être
créé hors API).

Usage : python create_admin.py <username> <password>
"""
import sys
from sqlalchemy import text
from config import get_engine
from security import hash_password

def main():
    if len(sys.argv) != 3:
        print("Usage : python create_admin.py <username> <password>")
        raise SystemExit(1)
    username, password = sys.argv[1], sys.argv[2]

    engine = get_engine()
    with engine.begin() as conn:
        exists = conn.execute(
            text("SELECT 1 FROM app.users WHERE username = :u"), {"u": username}
        ).first()
        if exists:
            print(f"Le compte '{username}' existe déjà.")
            raise SystemExit(1)
        conn.execute(
            text("INSERT INTO app.users (username, hashed_password, role) "
                 "VALUES (:u, :p, 'admin')"),
            {"u": username, "p": hash_password(password)},
        )
    print(f"Compte admin '{username}' créé.")

if __name__ == "__main__":
    main()

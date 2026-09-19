"""Crea o actualiza los usuarios iniciales del entorno de desarrollo."""

from sqlalchemy.orm import Session

from app.auth import hash_password
from app.db import SessionLocal, ensure_schema as db_ensure_schema
from app.models import Player

ADMIN_USERNAME = "Mr_Ganzo"
ADMIN_EMAIL = "mr_ganzo@example.com"
ADMIN_PASSWORD = "adminGanzo"


def ensure_schema() -> None:
    db_ensure_schema()


def seed_admin(db: Session) -> Player:
    player = db.query(Player).filter(Player.username == ADMIN_USERNAME).first()
    if player is None:
        player = Player(username=ADMIN_USERNAME, email=ADMIN_EMAIL, password_hash=hash_password(ADMIN_PASSWORD), is_admin=True)
        db.add(player)
    else:
        player.email = ADMIN_EMAIL
        player.password_hash = hash_password(ADMIN_PASSWORD)
        player.is_admin = True
        player.is_active = True
    db.commit()
    db.refresh(player)
    return player


if __name__ == "__main__":
    ensure_schema()
    with SessionLocal() as db:
        admin = seed_admin(db)
    print(f"Admin seed listo: {admin.username} (id={admin.id})")

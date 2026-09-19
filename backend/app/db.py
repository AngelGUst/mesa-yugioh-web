from collections.abc import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from config import settings


connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def ensure_schema() -> None:
    Base.metadata.create_all(bind=engine)
    with engine.begin() as connection:
        player_columns = {column["name"] for column in inspect(connection).get_columns("players")}
        if "is_admin" not in player_columns:
            connection.execute(text("ALTER TABLE players ADD COLUMN is_admin BOOLEAN NOT NULL DEFAULT FALSE"))

        card_columns = {column["name"] for column in inspect(connection).get_columns("cards")}
        card_migrations = {
            "human_readable_card_type": "VARCHAR(100)",
            "frame_type": "VARCHAR(50)",
            "archetype": "VARCHAR(255)",
            "ygoprodeck_url": "VARCHAR(500)",
            "image_url_small": "VARCHAR(500)",
            "image_url_cropped": "VARCHAR(500)",
        }
        for column, column_type in card_migrations.items():
            if column not in card_columns:
                connection.execute(text(f"ALTER TABLE cards ADD COLUMN {column} {column_type}"))

        deck_card_columns = {column["name"] for column in inspect(connection).get_columns("deck_cards")}
        deck_card_migrations = {
            "section": "VARCHAR(10) NOT NULL DEFAULT 'main'",
            "preferred_print_id": "INTEGER",
        }
        for column, column_type in deck_card_migrations.items():
            if column not in deck_card_columns:
                connection.execute(text(f"ALTER TABLE deck_cards ADD COLUMN {column} {column_type}"))

        duel_columns = {column["name"] for column in inspect(connection).get_columns("duels")}
        duel_migrations = {
            "name": "VARCHAR(100)",
            "player1_deck_id": "INTEGER",
            "player2_deck_id": "INTEGER",
        }
        for column, column_type in duel_migrations.items():
            if column not in duel_columns:
                connection.execute(text(f"ALTER TABLE duels ADD COLUMN {column} {column_type}"))


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

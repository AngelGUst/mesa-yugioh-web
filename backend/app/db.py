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
        _migrate_card_print_identity(connection)
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
            "revision": "INTEGER NOT NULL DEFAULT 1",
        }
        for column, column_type in duel_migrations.items():
            if column not in duel_columns:
                connection.execute(text(f"ALTER TABLE duels ADD COLUMN {column} {column_type}"))

        spectator_columns = {column["name"] for column in inspect(connection).get_columns("duel_spectators")}
        if "revoked_at" not in spectator_columns:
            timestamp_type = "TIMESTAMP WITH TIME ZONE" if connection.dialect.name == "postgresql" else "DATETIME"
            connection.execute(text(f"ALTER TABLE duel_spectators ADD COLUMN revoked_at {timestamp_type}"))

        event_columns = {column["name"] for column in inspect(connection).get_columns("duel_events")}
        event_migrations = {
            "actor_player_id": "INTEGER",
            "source_device": "VARCHAR(20) NOT NULL DEFAULT 'web'",
            "card_id": "INTEGER",
            "duel_card_id": "INTEGER",
            "source_zone": "VARCHAR(24)",
            "target_zone": "VARCHAR(24)",
        }
        for column, column_type in event_migrations.items():
            if column not in event_columns:
                connection.execute(text(f"ALTER TABLE duel_events ADD COLUMN {column} {column_type}"))

        duel_card_columns = {column["name"] for column in inspect(connection).get_columns("duel_cards")}
        if "client_action_id" not in duel_card_columns:
            connection.execute(text("ALTER TABLE duel_cards ADD COLUMN client_action_id VARCHAR(36)"))
        connection.execute(text(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_duel_card_client_action_id "
            "ON duel_cards (client_action_id)"
        ))


def _migrate_card_print_identity(connection) -> None:
    unique_constraints = inspect(connection).get_unique_constraints("card_prints")
    if not any(constraint["name"] == "uq_card_print_set_code" for constraint in unique_constraints):
        return

    if connection.dialect.name == "postgresql":
        connection.execute(text("ALTER TABLE card_prints DROP CONSTRAINT uq_card_print_set_code"))
        connection.execute(text(
            "ALTER TABLE card_prints ADD CONSTRAINT uq_card_print_identity "
            "UNIQUE (card_id, set_code, rarity_code, rarity)"
        ))
        return

    if connection.dialect.name == "sqlite":
        connection.execute(text("""
            CREATE TABLE card_prints_replacement (
                id INTEGER NOT NULL PRIMARY KEY,
                card_id INTEGER NOT NULL,
                set_name VARCHAR(255) NOT NULL,
                set_code VARCHAR(100) NOT NULL,
                language VARCHAR(10),
                rarity VARCHAR(100),
                rarity_code VARCHAR(50),
                price VARCHAR(50),
                CONSTRAINT uq_card_print_identity UNIQUE (card_id, set_code, rarity_code, rarity),
                FOREIGN KEY(card_id) REFERENCES cards (id) ON DELETE CASCADE
            )
        """))
        connection.execute(text("""
            INSERT INTO card_prints_replacement
                (id, card_id, set_name, set_code, language, rarity, rarity_code, price)
            SELECT id, card_id, set_name, set_code, language, rarity, rarity_code, price
            FROM card_prints
        """))
        connection.execute(text("DROP TABLE card_prints"))
        connection.execute(text("ALTER TABLE card_prints_replacement RENAME TO card_prints"))
        connection.execute(text("CREATE INDEX ix_card_prints_card_id ON card_prints (card_id)"))
        connection.execute(text("CREATE INDEX ix_card_prints_set_code ON card_prints (set_code)"))


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

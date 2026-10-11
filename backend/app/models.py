from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


CASCADING_DELETE = "all, delete-orphan"
PLAYER_ID_FOREIGN_KEY = "players.id"
DECK_ID_FOREIGN_KEY = "decks.id"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Player(Base):
    __tablename__ = "players"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    lp_wins: Mapped[int] = mapped_column(default=0)
    lp_losses: Mapped[int] = mapped_column(default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    decks: Mapped[list["Deck"]] = relationship(back_populates="player", cascade=CASCADING_DELETE)
    duels_as_player1: Mapped[list["Duel"]] = relationship(
        back_populates="player1", foreign_keys="Duel.player1_id", cascade=CASCADING_DELETE
    )
    duels_as_player2: Mapped[list["Duel"]] = relationship(
        back_populates="player2", foreign_keys="Duel.player2_id"
    )


class Card(Base):
    __tablename__ = "cards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ygoprodeck_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    card_type: Mapped[str | None] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(Text)
    atk: Mapped[int | None] = mapped_column(Integer)
    def_: Mapped[int | None] = mapped_column("def", Integer)
    level: Mapped[int | None] = mapped_column(Integer)
    race: Mapped[str | None] = mapped_column(String(100))
    attribute: Mapped[str | None] = mapped_column(String(50))
    human_readable_card_type: Mapped[str | None] = mapped_column(String(100))
    frame_type: Mapped[str | None] = mapped_column(String(50))
    archetype: Mapped[str | None] = mapped_column(String(255))
    ygoprodeck_url: Mapped[str | None] = mapped_column(String(500))
    image_url: Mapped[str | None] = mapped_column(String(500))
    image_url_small: Mapped[str | None] = mapped_column(String(500))
    image_url_cropped: Mapped[str | None] = mapped_column(String(500))
    raw_data: Mapped[dict | None] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    deck_entries: Mapped[list["DeckCard"]] = relationship(back_populates="card")
    prints: Mapped[list["CardPrint"]] = relationship(back_populates="card", cascade=CASCADING_DELETE)


class CardPrint(Base):
    __tablename__ = "card_prints"
    __table_args__ = (
        UniqueConstraint("card_id", "set_code", "rarity_code", "rarity", name="uq_card_print_identity"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    card_id: Mapped[int] = mapped_column(ForeignKey("cards.id", ondelete="CASCADE"), index=True)
    set_name: Mapped[str] = mapped_column(String(255))
    set_code: Mapped[str] = mapped_column(String(100), index=True)
    language: Mapped[str | None] = mapped_column(String(10))
    rarity: Mapped[str | None] = mapped_column(String(100))
    rarity_code: Mapped[str | None] = mapped_column(String(50))
    price: Mapped[str | None] = mapped_column(String(50))

    card: Mapped[Card] = relationship(back_populates="prints")


class Deck(Base):
    __tablename__ = "decks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(Text)
    player_id: Mapped[int] = mapped_column(ForeignKey(PLAYER_ID_FOREIGN_KEY), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    player: Mapped[Player] = relationship(back_populates="decks")
    card_entries: Mapped[list["DeckCard"]] = relationship(back_populates="deck", cascade=CASCADING_DELETE)


class DeckCard(Base):
    __tablename__ = "deck_cards"
    __table_args__ = (UniqueConstraint("deck_id", "card_id", name="uq_deck_card"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    deck_id: Mapped[int] = mapped_column(ForeignKey("decks.id", ondelete="CASCADE"), index=True)
    card_id: Mapped[int] = mapped_column(ForeignKey("cards.id"), index=True)
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    section: Mapped[str] = mapped_column(String(10), default="main", nullable=False)
    preferred_print_id: Mapped[int | None] = mapped_column(ForeignKey("card_prints.id"))

    deck: Mapped[Deck] = relationship(back_populates="card_entries")
    card: Mapped[Card] = relationship(back_populates="deck_entries")
    preferred_print: Mapped[CardPrint | None] = relationship(foreign_keys=[preferred_print_id])


class Duel(Base):
    __tablename__ = "duels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    duel_code: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    name: Mapped[str | None] = mapped_column(String(100))
    player1_id: Mapped[int] = mapped_column(ForeignKey(PLAYER_ID_FOREIGN_KEY), index=True)
    player2_id: Mapped[int | None] = mapped_column(ForeignKey(PLAYER_ID_FOREIGN_KEY), index=True)
    player1_deck_id: Mapped[int | None] = mapped_column(ForeignKey(DECK_ID_FOREIGN_KEY))
    player2_deck_id: Mapped[int | None] = mapped_column(ForeignKey(DECK_ID_FOREIGN_KEY))
    player1_lp: Mapped[int] = mapped_column(Integer, default=8000)
    player2_lp: Mapped[int] = mapped_column(Integer, default=8000)
    status: Mapped[str] = mapped_column(String(20), default="waiting")
    turn: Mapped[int] = mapped_column(Integer, default=1)
    current_phase: Mapped[str] = mapped_column(String(50), default="DRAW_PHASE")
    current_player: Mapped[int] = mapped_column(Integer, default=1)
    revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    winner_id: Mapped[int | None] = mapped_column(ForeignKey(PLAYER_ID_FOREIGN_KEY))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    player1: Mapped[Player] = relationship(back_populates="duels_as_player1", foreign_keys=[player1_id])
    player2: Mapped[Player | None] = relationship(back_populates="duels_as_player2", foreign_keys=[player2_id])
    player1_deck: Mapped[Deck | None] = relationship(foreign_keys=[player1_deck_id])
    player2_deck: Mapped[Deck | None] = relationship(foreign_keys=[player2_deck_id])
    events: Mapped[list["DuelEvent"]] = relationship(back_populates="duel", cascade=CASCADING_DELETE)
    cards: Mapped[list["DuelCard"]] = relationship(back_populates="duel", cascade=CASCADING_DELETE)
    spectator_grants: Mapped[list["DuelSpectator"]] = relationship(back_populates="duel", cascade=CASCADING_DELETE)
    camera_sessions: Mapped[list["DuelCameraSession"]] = relationship(back_populates="duel", cascade=CASCADING_DELETE)

    @property
    def player1_username(self) -> str:
        return self.player1.username

    @property
    def player2_username(self) -> str | None:
        return self.player2.username if self.player2 else None


class DuelEvent(Base):
    __tablename__ = "duel_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    duel_id: Mapped[int] = mapped_column(ForeignKey("duels.id", ondelete="CASCADE"), index=True)
    event_type: Mapped[str] = mapped_column(String(50))
    payload: Mapped[dict | None] = mapped_column(JSON)
    actor_player_id: Mapped[int | None] = mapped_column(ForeignKey(PLAYER_ID_FOREIGN_KEY))
    source_device: Mapped[str] = mapped_column(String(20), default="web", nullable=False)
    card_id: Mapped[int | None] = mapped_column(ForeignKey("cards.id"))
    duel_card_id: Mapped[int | None] = mapped_column(ForeignKey("duel_cards.id"))
    source_zone: Mapped[str | None] = mapped_column(String(24))
    target_zone: Mapped[str | None] = mapped_column(String(24))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    duel: Mapped[Duel] = relationship(back_populates="events")
    actor: Mapped[Player | None] = relationship(foreign_keys=[actor_player_id])
    duel_card: Mapped["DuelCard | None"] = relationship(foreign_keys=[duel_card_id])

    @property
    def actor_username(self) -> str | None:
        return self.actor.username if self.actor else None


class DuelSpectator(Base):
    __tablename__ = "duel_spectators"
    __table_args__ = (UniqueConstraint("duel_id", "player_id", name="uq_duel_spectator"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    duel_id: Mapped[int] = mapped_column(ForeignKey("duels.id", ondelete="CASCADE"), index=True)
    player_id: Mapped[int] = mapped_column(ForeignKey(PLAYER_ID_FOREIGN_KEY, ondelete="CASCADE"), index=True)
    invited_by_id: Mapped[int] = mapped_column(ForeignKey(PLAYER_ID_FOREIGN_KEY, ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    duel: Mapped[Duel] = relationship(back_populates="spectator_grants")
    player: Mapped[Player] = relationship(foreign_keys=[player_id])
    invited_by: Mapped[Player] = relationship(foreign_keys=[invited_by_id])

    @property
    def username(self) -> str:
        return self.player.username


class DuelCameraSession(Base):
    __tablename__ = "duel_camera_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    duel_id: Mapped[int] = mapped_column(ForeignKey("duels.id", ondelete="CASCADE"), index=True)
    player_id: Mapped[int] = mapped_column(ForeignKey(PLAYER_ID_FOREIGN_KEY, ondelete="CASCADE"), index=True)
    pairing_token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    camera_token_hash: Mapped[str | None] = mapped_column(String(64), unique=True, index=True)
    pairing_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    paired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    session_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    duel: Mapped[Duel] = relationship(back_populates="camera_sessions")
    player: Mapped[Player] = relationship(foreign_keys=[player_id])


class DuelCard(Base):
    __tablename__ = "duel_cards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    duel_id: Mapped[int] = mapped_column(ForeignKey("duels.id", ondelete="CASCADE"), index=True)
    card_id: Mapped[int] = mapped_column(ForeignKey("cards.id"), index=True)
    player_id: Mapped[int] = mapped_column(ForeignKey(PLAYER_ID_FOREIGN_KEY), index=True)
    zone: Mapped[str] = mapped_column(String(24), index=True)
    position: Mapped[int | None] = mapped_column(Integer)
    face_down: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    preferred_print_id: Mapped[int | None] = mapped_column(ForeignKey("card_prints.id"))
    created_by_player_id: Mapped[int] = mapped_column(ForeignKey(PLAYER_ID_FOREIGN_KEY))
    updated_by_player_id: Mapped[int] = mapped_column(ForeignKey(PLAYER_ID_FOREIGN_KEY))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
    client_action_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    duel: Mapped[Duel] = relationship(back_populates="cards")
    card: Mapped[Card] = relationship()
    player: Mapped[Player] = relationship(foreign_keys=[player_id])
    created_by: Mapped[Player] = relationship(foreign_keys=[created_by_player_id])
    updated_by: Mapped[Player] = relationship(foreign_keys=[updated_by_player_id])

    @property
    def card_name(self) -> str:
        return self.card.name

    @property
    def image_url(self) -> str | None:
        return self.card.image_url_small or self.card.image_url

    @property
    def player_username(self) -> str:
        return self.player.username

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


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
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    decks: Mapped[list["Deck"]] = relationship(back_populates="player", cascade="all, delete-orphan")
    duels_as_player1: Mapped[list["Duel"]] = relationship(
        back_populates="player1", foreign_keys="Duel.player1_id", cascade="all, delete-orphan"
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
    image_url: Mapped[str | None] = mapped_column(String(500))
    raw_data: Mapped[dict | None] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    deck_entries: Mapped[list["DeckCard"]] = relationship(back_populates="card")


class Deck(Base):
    __tablename__ = "decks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(Text)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    player: Mapped[Player] = relationship(back_populates="decks")
    card_entries: Mapped[list["DeckCard"]] = relationship(back_populates="deck", cascade="all, delete-orphan")


class DeckCard(Base):
    __tablename__ = "deck_cards"
    __table_args__ = (UniqueConstraint("deck_id", "card_id", name="uq_deck_card"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    deck_id: Mapped[int] = mapped_column(ForeignKey("decks.id", ondelete="CASCADE"), index=True)
    card_id: Mapped[int] = mapped_column(ForeignKey("cards.id"), index=True)
    quantity: Mapped[int] = mapped_column(Integer, default=1)

    deck: Mapped[Deck] = relationship(back_populates="card_entries")
    card: Mapped[Card] = relationship(back_populates="deck_entries")


class Duel(Base):
    __tablename__ = "duels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    duel_code: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    player1_id: Mapped[int] = mapped_column(ForeignKey("players.id"), index=True)
    player2_id: Mapped[int | None] = mapped_column(ForeignKey("players.id"), index=True)
    player1_lp: Mapped[int] = mapped_column(Integer, default=8000)
    player2_lp: Mapped[int] = mapped_column(Integer, default=8000)
    status: Mapped[str] = mapped_column(String(20), default="waiting")
    turn: Mapped[int] = mapped_column(Integer, default=1)
    current_phase: Mapped[str] = mapped_column(String(50), default="DRAW_PHASE")
    current_player: Mapped[int] = mapped_column(Integer, default=1)
    winner_id: Mapped[int | None] = mapped_column(ForeignKey("players.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)

    player1: Mapped[Player] = relationship(back_populates="duels_as_player1", foreign_keys=[player1_id])
    player2: Mapped[Player | None] = relationship(back_populates="duels_as_player2", foreign_keys=[player2_id])
    events: Mapped[list["DuelEvent"]] = relationship(back_populates="duel", cascade="all, delete-orphan")


class DuelEvent(Base):
    __tablename__ = "duel_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    duel_id: Mapped[int] = mapped_column(ForeignKey("duels.id", ondelete="CASCADE"), index=True)
    event_type: Mapped[str] = mapped_column(String(50))
    payload: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    duel: Mapped[Duel] = relationship(back_populates="events")

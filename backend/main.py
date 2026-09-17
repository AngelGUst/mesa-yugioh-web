from contextlib import asynccontextmanager
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import create_access_token, get_current_player, hash_password, verify_password
from app.db import ensure_schema, get_db
from app.models import Card, Deck, DeckCard, Duel, DuelEvent, Player
from app.schemas import (
    CardResponse,
    DeckCreate,
    DeckResponse,
    DeckUpdate,
    DuelCreate,
    DuelEventCreate,
    DuelEventResponse,
    DuelResponse,
    DuelUpdate,
    PlayerCreate,
    PlayerLogin,
    PlayerResponse,
    TokenResponse,
)
from app.ygoprodeck import YGOProDeckError, fetch_cards, to_card_values
from config import settings


@asynccontextmanager
async def lifespan(_: FastAPI):
    ensure_schema()
    yield


app = FastAPI(title=settings.app_name, version=settings.app_version, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root() -> dict[str, str]:
    return {"message": settings.app_name, "version": settings.app_version, "status": "online"}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "healthy"}


@app.post("/api/auth/register", response_model=PlayerResponse, status_code=status.HTTP_201_CREATED)
def register(payload: PlayerCreate, db: Session = Depends(get_db)) -> Player:
    existing = db.scalar(select(Player).where((Player.username == payload.username) | (Player.email == payload.email)))
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Usuario o email ya existe")
    player = Player(username=payload.username, email=payload.email, password_hash=hash_password(payload.password))
    db.add(player)
    db.commit()
    db.refresh(player)
    return player


@app.post("/api/auth/login")
def login(payload: PlayerLogin, db: Session = Depends(get_db)) -> TokenResponse:
    player = db.scalar(select(Player).where(Player.username == payload.username))
    if player is None or not verify_password(payload.password, player.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales invalidas")
    return TokenResponse(access_token=create_access_token(player.id))


@app.get("/api/auth/me", response_model=PlayerResponse)
def me(player: Player = Depends(get_current_player)) -> Player:
    return player


@app.get("/api/cards", response_model=list[CardResponse])
def cards(search: str | None = None, db: Session = Depends(get_db)) -> list[Card]:
    query = select(Card).order_by(Card.name)
    if search:
        query = query.where(Card.name.ilike(f"%{search}%"))
    return list(db.scalars(query).all())


@app.post("/api/cards/import")
def import_cards(
    search: str | None = Query(default=None, description="Nombre exacto o parcial en YGOProDeck"),
    limit: int = Query(default=100, ge=1, le=500),
    _: Player = Depends(get_current_player),
    db: Session = Depends(get_db),
) -> dict[str, int | str | None]:
    try:
        imported = 0
        updated = 0
        for raw_card in fetch_cards(search)[:limit]:
            values = to_card_values(raw_card)
            card = db.scalar(select(Card).where(Card.ygoprodeck_id == values["ygoprodeck_id"]))
            if card is None:
                db.add(Card(**values))
                imported += 1
            else:
                for field, value in values.items():
                    setattr(card, field, value)
                updated += 1
        db.commit()
    except YGOProDeckError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    return {"search": search, "imported": imported, "updated": updated, "total": imported + updated}


def _replace_deck_cards(deck: Deck, card_inputs: list, db: Session) -> None:
    card_ids = [item.card_id for item in card_inputs]
    cards_by_id = {card.id: card for card in db.scalars(select(Card).where(Card.id.in_(card_ids))).all()}
    if len(cards_by_id) != len(set(card_ids)):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Una o mas cartas no existen")
    deck.card_entries.clear()
    deck.card_entries.extend(DeckCard(card_id=item.card_id, quantity=item.quantity) for item in card_inputs)


@app.post("/api/decks", response_model=DeckResponse, status_code=status.HTTP_201_CREATED)
def create_deck(payload: DeckCreate, player: Player = Depends(get_current_player), db: Session = Depends(get_db)) -> Deck:
    deck = Deck(name=payload.name, description=payload.description, player_id=player.id)
    _replace_deck_cards(deck, payload.cards, db)
    db.add(deck)
    db.commit()
    db.refresh(deck)
    return deck


@app.get("/api/decks", response_model=list[DeckResponse])
def list_decks(player: Player = Depends(get_current_player), db: Session = Depends(get_db)) -> list[Deck]:
    return list(db.scalars(select(Deck).where(Deck.player_id == player.id).order_by(Deck.updated_at.desc())).all())


def _owned_deck(deck_id: int, player: Player, db: Session) -> Deck:
    deck = db.scalar(select(Deck).where(Deck.id == deck_id, Deck.player_id == player.id))
    if deck is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deck no encontrado")
    return deck


@app.get("/api/decks/{deck_id}", response_model=DeckResponse)
def get_deck(deck_id: int, player: Player = Depends(get_current_player), db: Session = Depends(get_db)) -> Deck:
    return _owned_deck(deck_id, player, db)


@app.put("/api/decks/{deck_id}", response_model=DeckResponse)
def update_deck(deck_id: int, payload: DeckUpdate, player: Player = Depends(get_current_player), db: Session = Depends(get_db)) -> Deck:
    deck = _owned_deck(deck_id, player, db)
    if payload.name is not None:
        deck.name = payload.name
    if payload.description is not None:
        deck.description = payload.description
    if payload.cards is not None:
        _replace_deck_cards(deck, payload.cards, db)
    db.commit()
    db.refresh(deck)
    return deck


@app.delete("/api/decks/{deck_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_deck(deck_id: int, player: Player = Depends(get_current_player), db: Session = Depends(get_db)) -> None:
    deck = _owned_deck(deck_id, player, db)
    db.delete(deck)
    db.commit()


def _duel_for_player(duel_id: int, player: Player, db: Session) -> Duel:
    duel = db.scalar(select(Duel).where(
        Duel.id == duel_id,
        (Duel.player1_id == player.id) | (Duel.player2_id == player.id),
    ))
    if duel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Duelo no encontrado")
    return duel


@app.post("/api/duels", response_model=DuelResponse, status_code=status.HTTP_201_CREATED)
def create_duel(payload: DuelCreate, player: Player = Depends(get_current_player), db: Session = Depends(get_db)) -> Duel:
    if payload.player2_id == player.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No puedes desafiarte a ti mismo")
    if payload.player2_id is not None and db.get(Player, payload.player2_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Oponente no encontrado")
    duel = Duel(duel_code=uuid4().hex[:10].upper(), player1_id=player.id, player2_id=payload.player2_id)
    if payload.player2_id is not None:
        duel.status = "active"
    db.add(duel)
    db.commit()
    db.refresh(duel)
    return duel


@app.get("/api/duels", response_model=list[DuelResponse])
def list_duels(player: Player = Depends(get_current_player), db: Session = Depends(get_db)) -> list[Duel]:
    return list(db.scalars(select(Duel).where((Duel.player1_id == player.id) | (Duel.player2_id == player.id)).order_by(Duel.created_at.desc())).all())


@app.get("/api/duels/{duel_id}", response_model=DuelResponse)
def get_duel(duel_id: int, player: Player = Depends(get_current_player), db: Session = Depends(get_db)) -> Duel:
    return _duel_for_player(duel_id, player, db)


@app.put("/api/duels/{duel_id}", response_model=DuelResponse)
def update_duel(duel_id: int, payload: DuelUpdate, player: Player = Depends(get_current_player), db: Session = Depends(get_db)) -> Duel:
    duel = _duel_for_player(duel_id, player, db)
    changes = payload.model_dump(exclude_unset=True)
    if "player2_id" in changes and changes["player2_id"] is not None:
        if db.get(Player, changes["player2_id"]) is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Oponente no encontrado")
        if changes["player2_id"] == duel.player1_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Oponente invalido")
        changes["status"] = "active"
    for field, value in changes.items():
        setattr(duel, field, value)
    if duel.status == "finished" and duel.finished_at is None:
        duel.finished_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(duel)
    return duel


@app.delete("/api/duels/{duel_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_duel(duel_id: int, player: Player = Depends(get_current_player), db: Session = Depends(get_db)) -> None:
    duel = _duel_for_player(duel_id, player, db)
    db.delete(duel)
    db.commit()


@app.post("/api/duels/{duel_id}/events", response_model=DuelEventResponse, status_code=status.HTTP_201_CREATED)
def add_duel_event(duel_id: int, payload: DuelEventCreate, player: Player = Depends(get_current_player), db: Session = Depends(get_db)) -> DuelEvent:
    duel = _duel_for_player(duel_id, player, db)
    event = DuelEvent(duel_id=duel.id, event_type=payload.event_type, payload=payload.payload)
    db.add(event)
    db.commit()
    db.refresh(event)
    return event

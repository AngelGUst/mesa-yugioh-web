import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
import json
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import (
    create_access_token,
    decode_token_player_id,
    get_current_player,
    hash_password,
    verify_password,
)
from app.db import ensure_schema, get_db
from app.models import Card, CardPrint, Deck, DeckCard, Duel, DuelEvent, Player
from app.websocket_manager import ws_manager
from app.schemas import (
    CardResponse,
    DeckCreate,
    DeckImportRequest,
    DeckResponse,
    DeckUpdate,
    DuelCreate,
    DuelEventCreate,
    DuelEventResponse,
    DuelJoin,
    DuelResponse,
    DuelUpdate,
    PlayerCreate,
    PlayerLogin,
    PlayerResponse,
    TokenResponse,
)
from app.ygoprodeck import (
    YGOProDeckError,
    fetch_cards,
    fetch_cards_by_ids,
    parse_deck_content,
    to_card_print_values,
    to_card_values,
)
from config import settings


@asynccontextmanager
async def lifespan(_: FastAPI):
    ensure_schema()
    ws_manager.set_loop(asyncio.get_running_loop())
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
                card = Card(**values)
                db.add(card)
                imported += 1
            else:
                for field, value in values.items():
                    setattr(card, field, value)
                updated += 1
            db.flush()
            existing_prints = {
                (card_print.set_code, card_print.rarity_code, card_print.rarity): card_print
                for card_print in card.prints
            }
            imported_print_identities = set()
            for raw_print in raw_card.get("card_sets") or []:
                print_values = to_card_print_values(raw_print)
                print_identity = (
                    print_values["set_code"],
                    print_values["rarity_code"],
                    print_values["rarity"],
                )
                imported_print_identities.add(print_identity)
                card_print = existing_prints.get(print_identity)
                if card_print is None:
                    card_print = CardPrint(card_id=card.id, **print_values)
                    db.add(card_print)
                    existing_prints[print_identity] = card_print
                else:
                    for field, value in print_values.items():
                        setattr(card_print, field, value)
            for print_identity, card_print in existing_prints.items():
                if print_identity not in imported_print_identities:
                    db.delete(card_print)
        db.commit()
    except YGOProDeckError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    return {"search": search, "imported": imported, "updated": updated, "total": imported + updated}


def _replace_deck_cards(deck: Deck, card_inputs: list, db: Session) -> None:
    card_ids = [item.card_id for item in card_inputs]
    if len(card_ids) != len(set(card_ids)):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Una carta solo puede aparecer una vez por deck")
    cards_by_id = {card.id: card for card in db.scalars(select(Card).where(Card.id.in_(card_ids))).all()}
    if len(cards_by_id) != len(set(card_ids)):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Una o mas cartas no existen")
    print_ids = [item.preferred_print_id for item in card_inputs if item.preferred_print_id is not None]
    prints_by_id = {card_print.id: card_print for card_print in db.scalars(select(CardPrint).where(CardPrint.id.in_(print_ids))).all()}
    for item in card_inputs:
        if item.preferred_print_id is not None:
            card_print = prints_by_id.get(item.preferred_print_id)
            if card_print is None or card_print.card_id != item.card_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="La impresion seleccionada no pertenece a la carta",
                )
    existing_by_card_id = {entry.card_id: entry for entry in deck.card_entries}
    input_card_ids = set()
    new_entries = []

    for item in card_inputs:
        input_card_ids.add(item.card_id)
        if item.card_id in existing_by_card_id:
            entry = existing_by_card_id[item.card_id]
            entry.quantity = item.quantity
            entry.section = item.section
            entry.preferred_print_id = item.preferred_print_id
            new_entries.append(entry)
        else:
            new_entries.append(
                DeckCard(
                    card_id=item.card_id,
                    quantity=item.quantity,
                    section=item.section,
                    preferred_print_id=item.preferred_print_id,
                )
            )

    for card_id, entry in existing_by_card_id.items():
        if card_id not in input_card_ids:
            db.delete(entry)

    deck.card_entries = new_entries


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


@app.post("/api/decks/import", response_model=DeckResponse, status_code=status.HTTP_201_CREATED)
def import_deck(
    payload: DeckImportRequest,
    player: Player = Depends(get_current_player),
    db: Session = Depends(get_db),
) -> Deck:
    try:
        detected_name, sections = parse_deck_content(payload.content)
    except YGOProDeckError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    deck_name = payload.name or detected_name or "Deck Importado"

    all_refs = list(sections["main"] + sections["extra"] + sections["side"])
    numeric_ids = {int(ref) for ref in all_refs if isinstance(ref, int) or (isinstance(ref, str) and ref.isdigit())}
    name_refs = {str(ref) for ref in all_refs if isinstance(ref, str) and not ref.isdigit()}

    # 1. Look up existing cards
    existing_cards_by_ygo_id = {}
    if numeric_ids:
        for card in db.scalars(select(Card).where(Card.ygoprodeck_id.in_(numeric_ids))).all():
            existing_cards_by_ygo_id[card.ygoprodeck_id] = card

    existing_cards_by_name = {}
    if name_refs:
        for card in db.scalars(select(Card).where(Card.name.in_(name_refs))).all():
            existing_cards_by_name[card.name.lower()] = card

    # 2. Fetch missing cards by ID
    missing_numeric_ids = list(numeric_ids - set(existing_cards_by_ygo_id.keys()))
    if missing_numeric_ids:
        try:
            fetched = fetch_cards_by_ids(missing_numeric_ids)
            for raw_card in fetched:
                card_vals = to_card_values(raw_card)
                card = Card(**card_vals)
                db.add(card)
                db.flush()
                for raw_print in raw_card.get("card_sets") or []:
                    print_vals = to_card_print_values(raw_print)
                    db.add(CardPrint(card_id=card.id, **print_vals))
                existing_cards_by_ygo_id[card.ygoprodeck_id] = card
                existing_cards_by_name[card.name.lower()] = card
        except YGOProDeckError as exc:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    # 3. Fetch missing cards by Name
    for name_ref in name_refs:
        if name_ref.lower() not in existing_cards_by_name:
            try:
                fetched = fetch_cards(name_ref)
                for raw_card in fetched:
                    if raw_card["name"].lower() == name_ref.lower():
                        card_vals = to_card_values(raw_card)
                        card = Card(**card_vals)
                        db.add(card)
                        db.flush()
                        for raw_print in raw_card.get("card_sets") or []:
                            print_vals = to_card_print_values(raw_print)
                            db.add(CardPrint(card_id=card.id, **print_vals))
                        existing_cards_by_ygo_id[card.ygoprodeck_id] = card
                        existing_cards_by_name[card.name.lower()] = card
                        break
            except Exception:
                pass

    def resolve_card(ref: int | str) -> Card | None:
        if isinstance(ref, int) or (isinstance(ref, str) and ref.isdigit()):
            return existing_cards_by_ygo_id.get(int(ref))
        return existing_cards_by_name.get(str(ref).lower())

    deck = Deck(
        name=deck_name,
        description=payload.description or "Importado automáticamente",
        player_id=player.id,
    )
    db.add(deck)
    db.flush()

    seen_cards = {}
    for section_name in ["main", "extra", "side"]:
        raw_items = sections.get(section_name) or []
        counts = {}
        for item in raw_items:
            card = resolve_card(item)
            if card:
                counts[card.id] = counts.get(card.id, 0) + 1

        for card_id, count in counts.items():
            qty = min(3, count)
            if card_id not in seen_cards:
                preferred_print = db.scalar(select(CardPrint.id).where(CardPrint.card_id == card_id).limit(1))
                entry = DeckCard(
                    deck_id=deck.id,
                    card_id=card_id,
                    quantity=qty,
                    section=section_name,
                    preferred_print_id=preferred_print,
                )
                db.add(entry)
                seen_cards[card_id] = entry
            else:
                existing_entry = seen_cards[card_id]
                existing_entry.quantity = min(3, existing_entry.quantity + qty)

    db.commit()
    db.refresh(deck)
    return deck


@app.delete("/api/decks/{deck_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_deck(deck_id: int, player: Player = Depends(get_current_player), db: Session = Depends(get_db)) -> None:
    deck = _owned_deck(deck_id, player, db)
    referenced_duel = db.scalar(select(Duel.id).where(
        (Duel.player1_deck_id == deck.id) | (Duel.player2_deck_id == deck.id)
    ))
    if referenced_duel is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No puedes eliminar un deck seleccionado en un duelo. Elimina el duelo primero.",
        )
    db.delete(deck)
    db.commit()


def _duel_viewable(duel_id: int, db: Session) -> Duel:
    duel = db.scalar(select(Duel).where(Duel.id == duel_id))
    if duel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Duelo no encontrado")
    return duel


def _duel_for_player(duel_id: int, player: Player, db: Session) -> Duel:
    duel = _duel_viewable(duel_id, db)
    if duel.player1_id != player.id and duel.player2_id != player.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tienes permisos de jugador en este duelo")
    return duel


def _owned_deck_or_none(deck_id: int | None, player: Player, db: Session) -> int | None:
    if deck_id is None:
        return None
    _owned_deck(deck_id, player, db)
    return deck_id


@app.post("/api/duels", response_model=DuelResponse, status_code=status.HTTP_201_CREATED)
def create_duel(payload: DuelCreate, player: Player = Depends(get_current_player), db: Session = Depends(get_db)) -> Duel:
    duel = Duel(
        duel_code=uuid4().hex[:10].upper(),
        name=payload.name,
        player1_id=player.id,
        player1_deck_id=_owned_deck_or_none(payload.deck_id, player, db),
    )
    db.add(duel)
    db.commit()
    db.refresh(duel)
    return duel


@app.post("/api/duels/join", response_model=DuelResponse)
def join_duel(payload: DuelJoin, player: Player = Depends(get_current_player), db: Session = Depends(get_db)) -> Duel:
    duel = db.scalar(select(Duel).where(Duel.duel_code == payload.duel_code.upper()))
    if duel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sala no encontrada")
    if duel.player1_id == player.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Ya eres el creador de esta sala")
    if duel.player2_id is not None or duel.status != "waiting":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="La sala ya no esta disponible")
    duel.player2_id = player.id
    duel.player2_deck_id = _owned_deck_or_none(payload.deck_id, player, db)
    duel.status = "active"
    db.commit()
    db.refresh(duel)

    ws_manager.broadcast_sync(duel.id, {
        "type": "DUEL_UPDATED",
        "duel": DuelResponse.model_validate(duel).model_dump(mode="json"),
    })
    return duel


@app.get("/api/duels", response_model=list[DuelResponse])
def list_duels(player: Player = Depends(get_current_player), db: Session = Depends(get_db)) -> list[Duel]:
    return list(db.scalars(select(Duel).where((Duel.player1_id == player.id) | (Duel.player2_id == player.id)).order_by(Duel.created_at.desc())).all())


@app.get("/api/duels/{duel_id}", response_model=DuelResponse)
def get_duel(duel_id: int, player: Player = Depends(get_current_player), db: Session = Depends(get_db)) -> Duel:
    return _duel_viewable(duel_id, db)


@app.put("/api/duels/{duel_id}", response_model=DuelResponse)
def update_duel(duel_id: int, payload: DuelUpdate, player: Player = Depends(get_current_player), db: Session = Depends(get_db)) -> Duel:
    duel = _duel_for_player(duel_id, player, db)
    changes = payload.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(duel, field, value)
    if duel.status == "finished" and duel.finished_at is None:
        duel.finished_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(duel)

    ws_manager.broadcast_sync(duel.id, {
        "type": "DUEL_UPDATED",
        "duel": DuelResponse.model_validate(duel).model_dump(mode="json"),
    })
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

    ws_manager.broadcast_sync(duel.id, {
        "type": "DUEL_EVENT",
        "event": DuelEventResponse.model_validate(event).model_dump(mode="json"),
    })
    return event


@app.websocket("/api/duels/{duel_id}/ws")
async def duel_websocket(
    websocket: WebSocket,
    duel_id: int,
    token: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    duel = db.scalar(select(Duel).where(Duel.id == duel_id))
    if duel is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    player_id = decode_token_player_id(token)
    role = "spectator"
    if player_id is not None and (duel.player1_id == player_id or duel.player2_id == player_id):
        role = "player"

    await ws_manager.connect(duel_id, websocket)

    await websocket.send_json({
        "type": "CONNECTED",
        "duel_id": duel_id,
        "role": role,
        "player_id": player_id,
    })

    try:
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                if msg.get("action") == "PING":
                    await websocket.send_json({"type": "PONG"})
            except Exception:
                pass
    except WebSocketDisconnect:
        ws_manager.disconnect(duel_id, websocket)
    except Exception:
        ws_manager.disconnect(duel_id, websocket)

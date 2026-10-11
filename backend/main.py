import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import secrets
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session

from app.auth import (
    create_access_token,
    decode_token_player_id,
    bearer_scheme,
    get_current_player,
    hash_password,
    verify_password,
)
from app.db import ensure_schema, get_db
from app.models import (
    Card,
    CardPrint,
    Deck,
    DeckCard,
    Duel,
    DuelCameraSession,
    DuelCard,
    DuelEvent,
    DuelSpectator,
    Player,
)
from app.websocket_manager import ws_manager
from app.schemas import (
    CardResponse,
    CameraDeckCard,
    CameraCardPlacement,
    CameraPairingRedeem,
    CameraSessionInfo,
    CameraSessionResponse,
    DeckCreate,
    DeckImportRequest,
    DeckResponse,
    DeckUpdate,
    DuelCreate,
    DuelCardCreate,
    DuelCardMove,
    DuelCardResponse,
    DuelEventCreate,
    DuelEventResponse,
    DuelJoin,
    DuelResponse,
    DuelSpectatorCreate,
    DuelSpectatorResponse,
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


def _duel_viewable(duel_id: int, player: Player, db: Session) -> Duel:
    duel = db.scalar(select(Duel).where(Duel.id == duel_id))
    if duel is None or player.id not in (duel.player1_id, duel.player2_id):
        invite = db.scalar(
            select(DuelSpectator.id).where(
                DuelSpectator.duel_id == duel_id,
                DuelSpectator.player_id == player.id,
                DuelSpectator.revoked_at.is_(None),
            )
        ) if duel is not None and duel.status != "finished" else None
        if invite is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Duelo no encontrado")
    return duel


def _duel_snapshot_data(duel: Duel, viewer: Player | None = None) -> dict:
    response = DuelResponse.model_validate(duel).model_dump(mode="json")
    if viewer is not None:
        response["viewer_role"] = "player" if viewer.id in (duel.player1_id, duel.player2_id) else "spectator"
        private_zones = {"main_deck", "extra_deck", "side_deck", "hand"}
        hidden_card_ids = {
            card.id for card in duel.cards
            if viewer.id != card.player_id and (card.face_down or card.zone in private_zones)
        }
    else:
        hidden_card_ids = _globally_hidden_card_ids(duel)
    _redact_event_card_ids(response["events"], hidden_card_ids)
    return response


def _duel_response_data(duel: Duel, player: Player) -> dict:
    return _duel_snapshot_data(duel, player)


def _active_spectator_invites(duel_id: int, db: Session) -> list[DuelSpectator]:
    return list(db.scalars(
        select(DuelSpectator)
        .where(DuelSpectator.duel_id == duel_id, DuelSpectator.revoked_at.is_(None))
        .order_by(DuelSpectator.created_at)
    ).all())


def _token_digest(token: str) -> str:
    return sha256(token.encode("utf-8")).hexdigest()


def _utc_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _camera_deck_cards(duel: Duel, player: Player, db: Session) -> list[CameraDeckCard]:
    deck_id = duel.player1_deck_id if duel.player1_id == player.id else duel.player2_deck_id
    if deck_id is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="El jugador no tiene un deck asignado")
    entries = db.scalars(select(DeckCard).where(DeckCard.deck_id == deck_id).order_by(DeckCard.card_id)).all()
    return [
        CameraDeckCard(
            card_id=entry.card_id,
            name=entry.card.name,
            section=entry.section,
            quantity=entry.quantity,
            preferred_print_id=entry.preferred_print_id,
            image_url_small=entry.card.image_url_small,
        )
        for entry in entries
    ]


def _camera_session_context(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> tuple[DuelCameraSession, Duel, Player]:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sesión de cámara requerida")
    session = db.scalar(select(DuelCameraSession).where(
        DuelCameraSession.camera_token_hash == _token_digest(credentials.credentials),
        DuelCameraSession.revoked_at.is_(None),
    ))
    now = datetime.now(timezone.utc)
    if session is None or session.session_expires_at is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sesión de cámara inválida")
    expires_at = session.session_expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= now:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sesión de cámara expirada")

    duel = db.get(Duel, session.duel_id)
    player = db.scalar(select(Player).where(Player.id == session.player_id, Player.is_active.is_(True)))
    if duel is None or duel.status == "finished" or player is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="La sesión de cámara ya no está activa")
    return session, duel, player


def _camera_session_data(duel: Duel, player: Player, db: Session) -> dict:
    expires = db.scalar(select(DuelCameraSession.session_expires_at).where(
        DuelCameraSession.duel_id == duel.id,
        DuelCameraSession.player_id == player.id,
        DuelCameraSession.revoked_at.is_(None),
        DuelCameraSession.session_expires_at.is_not(None),
    ).order_by(DuelCameraSession.created_at.desc()).limit(1))
    return {
        "expires_at": _utc_datetime(expires) if expires is not None else None,
        "duel_id": duel.id,
        "duel_code": duel.duel_code,
        "player_id": player.id,
        "player_username": player.username,
        "deck_cards": _camera_deck_cards(duel, player, db),
    }


def _duel_for_player(duel_id: int, player: Player, db: Session) -> Duel:
    duel = db.scalar(select(Duel).where(Duel.id == duel_id).with_for_update())
    if duel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Duelo no encontrado")
    if duel.player1_id != player.id and duel.player2_id != player.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tienes permisos de jugador en este duelo")
    return duel


def _owned_deck_or_none(deck_id: int | None, player: Player, db: Session) -> int | None:
    if deck_id is None:
        return None
    _owned_deck(deck_id, player, db)
    return deck_id


def _bump_duel_revision(duel: Duel, db: Session) -> None:
    db.flush()
    db.execute(
        update(Duel)
        .where(Duel.id == duel.id)
        .values(revision=Duel.revision + 1)
    )
    db.refresh(duel, attribute_names=["revision"])


def _resolve_duel_card_position(
    duel_id: int,
    player_id: int,
    zone: str,
    position: int | None,
    db: Session,
    exclude_card_id: int | None = None,
) -> int:
    fixed_slots = {"monster_zone": 4, "spell_trap_zone": 4, "extra_monster": 1, "pendulum": 1}
    single_slots = {"field_spell"}
    if zone in single_slots:
        position = 0
    elif zone in fixed_slots:
        if position is None or position > fixed_slots[zone]:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="La zona requiere una posición válida")
    elif position is None:
        last_position = db.scalar(select(DuelCard.position).where(
            DuelCard.duel_id == duel_id,
            DuelCard.player_id == player_id,
            DuelCard.zone == zone,
        ).order_by(DuelCard.position.desc()).limit(1))
        position = (last_position + 1) if last_position is not None else 0

    occupancy_query = select(DuelCard.id).where(
        DuelCard.duel_id == duel_id,
        DuelCard.zone == zone,
        DuelCard.position == position,
    )
    if zone != "extra_monster":
        occupancy_query = occupancy_query.where(DuelCard.player_id == player_id)
    if exclude_card_id is not None:
        occupancy_query = occupancy_query.where(DuelCard.id != exclude_card_id)
    occupied = db.scalar(occupancy_query)
    if occupied is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Esa posición de la zona ya está ocupada")
    return position


def _duel_card_response(card: DuelCard, viewer: Player) -> dict:
    data = DuelCardResponse.model_validate(card).model_dump(mode="json")
    private_zone = card.zone in {"main_deck", "extra_deck", "side_deck", "hand"}
    hidden = viewer.id != card.player_id and (private_zone or card.face_down)
    if hidden:
        data["card_id"] = None
        data["card_name"] = "Carta oculta"
        data["image_url"] = None
        data["preferred_print_id"] = None
    data["hidden"] = hidden
    return data


def _globally_hidden_card_ids(duel: Duel) -> set[int]:
    private_zones = {"main_deck", "extra_deck", "side_deck", "hand"}
    return {
        card.id for card in duel.cards
        if card.face_down or card.zone in private_zones
    }


def _redact_event_card_ids(events: list[dict], hidden_card_ids: set[int]) -> None:
    for event in events:
        if event.get("duel_card_id") in hidden_card_ids:
            event["card_id"] = None
            event["duel_card_id"] = None


def _broadcast_duel_event(duel: Duel, event: DuelEvent) -> None:
    hidden_card_ids = _globally_hidden_card_ids(duel)
    event_data = DuelEventResponse.model_validate(event).model_dump(mode="json")
    if event.duel_card_id in hidden_card_ids:
        event_data["card_id"] = None
        event_data["duel_card_id"] = None
    duel_data = _duel_snapshot_data(duel)
    ws_manager.broadcast_sync(duel.id, {
        "type": "DUEL_EVENT",
        "revision": duel.revision,
        "event": event_data,
        "duel": duel_data,
    })


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
    duel = db.scalar(select(Duel).where(Duel.duel_code == payload.duel_code.upper()).with_for_update())
    if duel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sala no encontrada")
    if duel.player1_id == player.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Ya eres el creador de esta sala")
    if duel.player2_id is not None or duel.status != "waiting":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="La sala ya no esta disponible")
    duel.player2_id = player.id
    duel.player2_deck_id = _owned_deck_or_none(payload.deck_id, player, db)
    duel.status = "active"
    _bump_duel_revision(duel, db)
    db.commit()
    db.refresh(duel)

    ws_manager.broadcast_sync(duel.id, {
        "type": "DUEL_UPDATED",
        "revision": duel.revision,
        "duel": _duel_snapshot_data(duel),
    })
    return duel


@app.get("/api/duels", response_model=list[DuelResponse])
def list_duels(player: Player = Depends(get_current_player), db: Session = Depends(get_db)) -> list[dict]:
    spectator_duels = select(DuelSpectator.duel_id).where(
        DuelSpectator.player_id == player.id,
        DuelSpectator.revoked_at.is_(None),
    )
    duels = db.scalars(
        select(Duel)
        .where(or_(Duel.player1_id == player.id, Duel.player2_id == player.id, Duel.id.in_(spectator_duels)))
        .order_by(Duel.created_at.desc())
    ).all()
    visible_duels = [
        duel for duel in duels
        if duel.status != "finished" or player.id in (duel.player1_id, duel.player2_id)
    ]
    return [_duel_response_data(duel, player) for duel in visible_duels]


@app.get("/api/duels/{duel_id}", response_model=DuelResponse)
def get_duel(duel_id: int, player: Player = Depends(get_current_player), db: Session = Depends(get_db)) -> dict:
    return _duel_response_data(_duel_viewable(duel_id, player, db), player)


@app.post("/api/duels/{duel_id}/camera-pairings")
def create_camera_pairing(
    duel_id: int,
    player: Player = Depends(get_current_player),
    db: Session = Depends(get_db),
) -> dict:
    duel = _duel_for_player(duel_id, player, db)
    if duel.status == "finished":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="El duelo ya terminó")
    deck_id = duel.player1_deck_id if duel.player1_id == player.id else duel.player2_deck_id
    if deck_id is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Asigna un deck antes de vincular la cámara")

    now = datetime.now(timezone.utc)
    existing = db.scalars(select(DuelCameraSession).where(
        DuelCameraSession.duel_id == duel.id,
        DuelCameraSession.player_id == player.id,
        DuelCameraSession.revoked_at.is_(None),
        DuelCameraSession.paired_at.is_(None),
    ).with_for_update()).all()
    for old_pairing in existing:
        old_pairing.revoked_at = now

    pairing_token = secrets.token_urlsafe(32)
    pairing = DuelCameraSession(
        duel_id=duel.id,
        player_id=player.id,
        pairing_token_hash=_token_digest(pairing_token),
        pairing_expires_at=now + timedelta(minutes=5),
    )
    db.add(pairing)
    db.commit()
    return {
        "pairing_token": pairing_token,
        "expires_at": _utc_datetime(pairing.pairing_expires_at),
        "duel_id": duel.id,
        "duel_code": duel.duel_code,
    }


@app.post("/api/camera-pairings/redeem", response_model=CameraSessionResponse)
def redeem_camera_pairing(
    payload: CameraPairingRedeem,
    db: Session = Depends(get_db),
) -> CameraSessionResponse:
    pairing = db.scalar(select(DuelCameraSession).where(
        DuelCameraSession.pairing_token_hash == _token_digest(payload.pairing_token),
    ).with_for_update())
    now = datetime.now(timezone.utc)
    if pairing is None or pairing.revoked_at is not None or pairing.paired_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="El código QR no es válido o ya fue utilizado")
    expires_at = pairing.pairing_expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= now:
        pairing.revoked_at = now
        db.commit()
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="El código QR expiró; genera uno nuevo desde el tablero")

    duel = db.get(Duel, pairing.duel_id)
    player = db.scalar(select(Player).where(Player.id == pairing.player_id, Player.is_active.is_(True)))
    if duel is None or duel.status == "finished" or player is None:
        pairing.revoked_at = now
        db.commit()
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="El duelo ya no admite cámaras")

    camera_token = secrets.token_urlsafe(32)
    pairing.paired_at = now
    pairing.camera_token_hash = _token_digest(camera_token)
    pairing.session_expires_at = now + timedelta(hours=12)
    db.commit()
    return CameraSessionResponse(
        camera_token=camera_token,
        expires_at=_utc_datetime(pairing.session_expires_at),
        duel_id=duel.id,
        duel_code=duel.duel_code,
        player_id=player.id,
        player_username=player.username,
        deck_cards=_camera_deck_cards(duel, player, db),
    )


@app.get("/api/camera-session", response_model=CameraSessionInfo)
def get_camera_session(
    context: tuple[DuelCameraSession, Duel, Player] = Depends(_camera_session_context),
    db: Session = Depends(get_db),
) -> dict:
    _, duel, player = context
    return _camera_session_data(duel, player, db)


@app.get("/api/camera-session/cards", response_model=list[DuelCardResponse])
def list_camera_board_cards(
    context: tuple[DuelCameraSession, Duel, Player] = Depends(_camera_session_context),
    db: Session = Depends(get_db),
) -> list[dict]:
    _, duel, player = context
    cards = db.scalars(
        select(DuelCard)
        .where(DuelCard.duel_id == duel.id)
        .order_by(DuelCard.created_at)
    ).all()
    return [_duel_card_response(card, player) for card in cards]


@app.post("/api/camera-session/revoke", status_code=status.HTTP_204_NO_CONTENT)
def revoke_camera_session(
    context: tuple[DuelCameraSession, Duel, Player] = Depends(_camera_session_context),
    db: Session = Depends(get_db),
) -> None:
    camera_session, _, _ = context
    camera_session.revoked_at = datetime.now(timezone.utc)
    db.commit()


@app.get("/api/duels/{duel_id}/cards", response_model=list[DuelCardResponse])
def list_duel_cards(
    duel_id: int,
    player: Player = Depends(get_current_player),
    db: Session = Depends(get_db),
) -> list[dict]:
    _duel_viewable(duel_id, player, db)
    cards = db.scalars(select(DuelCard).where(DuelCard.duel_id == duel_id).order_by(DuelCard.created_at)).all()
    return [_duel_card_response(card, player) for card in cards]


def _place_duel_card(
    duel_id: int,
    payload: DuelCardCreate,
    player: Player,
    db: Session,
    client_action_id: str | None = None,
) -> dict:
    duel = _duel_for_player(duel_id, player, db)
    if duel.status == "finished":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="No se pueden modificar las cartas de un duelo terminado")
    if client_action_id is not None:
        previous_action = db.scalar(select(DuelCard).where(DuelCard.client_action_id == client_action_id))
        if previous_action is not None:
            if previous_action.duel_id != duel.id or previous_action.player_id != player.id:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="El ID de captura ya fue utilizado")
            return _duel_card_response(previous_action, player)

    deck_id = duel.player1_deck_id if duel.player1_id == player.id else duel.player2_deck_id
    if deck_id is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Selecciona un deck para este duelo antes de registrar cartas")
    expected_section = {"main_deck": "main", "extra_deck": "extra", "side_deck": "side"}[payload.source_zone]
    deck_entry = db.scalar(select(DeckCard).where(
        DeckCard.deck_id == deck_id,
        DeckCard.card_id == payload.card_id,
        DeckCard.section == expected_section,
    ))
    if deck_entry is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La carta no pertenece a esa sección del deck seleccionado")
    placed_count = len(db.scalars(select(DuelCard.id).where(
        DuelCard.duel_id == duel.id,
        DuelCard.player_id == player.id,
        DuelCard.card_id == payload.card_id,
    )).all())
    if placed_count >= deck_entry.quantity:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ya registraste todas las copias de esta carta de tu deck")
    if payload.preferred_print_id is not None:
        preferred_print = db.get(CardPrint, payload.preferred_print_id)
        if preferred_print is None or preferred_print.card_id != payload.card_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La impresión seleccionada no pertenece a la carta")

    position = _resolve_duel_card_position(duel.id, player.id, payload.zone, payload.position, db)
    duel_card = DuelCard(
        duel_id=duel.id,
        card_id=payload.card_id,
        player_id=player.id,
        zone=payload.zone,
        position=position,
        face_down=payload.face_down,
        preferred_print_id=payload.preferred_print_id,
        created_by_player_id=player.id,
        updated_by_player_id=player.id,
        client_action_id=client_action_id,
    )
    db.add(duel_card)
    db.flush()
    event = DuelEvent(
        duel_id=duel.id,
        event_type="CARD_PLACED",
        payload={"position": position, "face_down": payload.face_down},
        actor_player_id=player.id,
        source_device=payload.source_device,
        card_id=payload.card_id,
        duel_card_id=duel_card.id,
        source_zone=payload.source_zone,
        target_zone=payload.zone,
    )
    db.add(event)
    _bump_duel_revision(duel, db)
    db.commit()
    db.refresh(duel_card)
    db.refresh(event)
    db.refresh(duel)
    _broadcast_duel_event(duel, event)
    return _duel_card_response(duel_card, player)


@app.post("/api/duels/{duel_id}/cards", response_model=DuelCardResponse, status_code=status.HTTP_201_CREATED)
def place_duel_card(
    duel_id: int,
    payload: DuelCardCreate,
    player: Player = Depends(get_current_player),
    db: Session = Depends(get_db),
) -> dict:
    return _place_duel_card(duel_id, payload, player, db)


@app.post("/api/camera-session/cards", response_model=DuelCardResponse, status_code=status.HTTP_201_CREATED)
def camera_place_duel_card(
    payload: CameraCardPlacement,
    context: tuple[DuelCameraSession, Duel, Player] = Depends(_camera_session_context),
    db: Session = Depends(get_db),
) -> dict:
    _, duel, player = context
    camera_payload = payload.model_copy(update={"source_device": "camera"})
    return _place_duel_card(duel.id, camera_payload, player, db, str(payload.client_action_id))


@app.put("/api/duels/{duel_id}/cards/{duel_card_id}", response_model=DuelCardResponse)
def move_duel_card(
    duel_id: int,
    duel_card_id: int,
    payload: DuelCardMove,
    player: Player = Depends(get_current_player),
    db: Session = Depends(get_db),
) -> dict:
    duel = _duel_for_player(duel_id, player, db)
    if duel.status == "finished":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="No se pueden modificar las cartas de un duelo terminado")
    duel_card = db.scalar(select(DuelCard).where(
        DuelCard.id == duel_card_id,
        DuelCard.duel_id == duel.id,
    ).with_for_update())
    if duel_card is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Carta del duelo no encontrada")
    if duel_card.player_id != player.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo puedes mover cartas de tu lado del tablero")

    source_zone = duel_card.zone
    position = _resolve_duel_card_position(
        duel.id, player.id, payload.zone, payload.position, db, exclude_card_id=duel_card.id
    )
    duel_card.zone = payload.zone
    duel_card.position = position
    duel_card.face_down = payload.face_down
    duel_card.updated_by_player_id = player.id
    duel_card.updated_at = datetime.now(timezone.utc)
    event = DuelEvent(
        duel_id=duel.id,
        event_type="CARD_MOVED",
        payload={"position": position, "face_down": payload.face_down},
        actor_player_id=player.id,
        source_device=payload.source_device,
        card_id=duel_card.card_id,
        duel_card_id=duel_card.id,
        source_zone=source_zone,
        target_zone=payload.zone,
    )
    db.add(event)
    _bump_duel_revision(duel, db)
    db.commit()
    db.refresh(duel_card)
    db.refresh(event)
    db.refresh(duel)
    _broadcast_duel_event(duel, event)
    return _duel_card_response(duel_card, player)


@app.get("/api/duels/{duel_id}/spectators", response_model=list[DuelSpectatorResponse])
def list_duel_spectators(
    duel_id: int,
    player: Player = Depends(get_current_player),
    db: Session = Depends(get_db),
) -> list[DuelSpectator]:
    duel = _duel_for_player(duel_id, player, db)
    if duel.status == "finished":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="El duelo está terminado")
    return _active_spectator_invites(duel_id, db)


@app.post("/api/duels/{duel_id}/spectators", response_model=DuelSpectatorResponse, status_code=status.HTTP_201_CREATED)
def invite_duel_spectator(
    duel_id: int,
    payload: DuelSpectatorCreate,
    player: Player = Depends(get_current_player),
    db: Session = Depends(get_db),
) -> DuelSpectator:
    duel = _duel_for_player(duel_id, player, db)
    if duel.status == "finished":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="No se pueden invitar espectadores a un duelo terminado")
    spectator = db.scalar(select(Player).where(Player.username == payload.username, Player.is_active.is_(True)))
    if spectator is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cuenta de espectador no encontrada")
    if spectator.id in (duel.player1_id, duel.player2_id):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Los jugadores ya tienen acceso al duelo")
    existing_invite = db.scalar(select(DuelSpectator).where(
        DuelSpectator.duel_id == duel.id,
        DuelSpectator.player_id == spectator.id,
    ))
    if existing_invite is not None and existing_invite.revoked_at is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Esta cuenta ya está invitada")

    if existing_invite is None:
        invite = DuelSpectator(duel_id=duel.id, player_id=spectator.id, invited_by_id=player.id)
        db.add(invite)
    else:
        invite = existing_invite
        invite.revoked_at = None
        invite.invited_by_id = player.id
        invite.created_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(invite)
    return invite


@app.delete("/api/duels/{duel_id}/spectators/{spectator_player_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_duel_spectator(
    duel_id: int,
    spectator_player_id: int,
    player: Player = Depends(get_current_player),
    db: Session = Depends(get_db),
) -> None:
    duel = _duel_for_player(duel_id, player, db)
    invite = db.scalar(select(DuelSpectator).where(
        DuelSpectator.duel_id == duel.id,
        DuelSpectator.player_id == spectator_player_id,
        DuelSpectator.revoked_at.is_(None),
    ).with_for_update())
    if invite is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invitación activa no encontrada")
    invite.revoked_at = datetime.now(timezone.utc)
    db.commit()
    ws_manager.close_player_connections_sync(duel.id, spectator_player_id)


@app.put("/api/duels/{duel_id}", response_model=DuelResponse)
def update_duel(duel_id: int, payload: DuelUpdate, player: Player = Depends(get_current_player), db: Session = Depends(get_db)) -> Duel:
    duel = _duel_for_player(duel_id, player, db)
    was_finished = duel.status == "finished"
    changes = payload.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(duel, field, value)
    if duel.status == "finished" and duel.finished_at is None:
        duel.finished_at = datetime.now(timezone.utc)
    if changes:
        _bump_duel_revision(duel, db)
    revoked_spectator_ids: list[int] = []
    if duel.status == "finished" and not was_finished:
        for invite in _active_spectator_invites(duel.id, db):
            invite.revoked_at = datetime.now(timezone.utc)
            revoked_spectator_ids.append(invite.player_id)
        for camera_session in db.scalars(select(DuelCameraSession).where(
            DuelCameraSession.duel_id == duel.id,
            DuelCameraSession.revoked_at.is_(None),
        )).all():
            camera_session.revoked_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(duel)

    ws_manager.broadcast_sync(duel.id, {
        "type": "DUEL_UPDATED",
        "revision": duel.revision,
        "duel": _duel_snapshot_data(duel),
    })
    for spectator_id in revoked_spectator_ids:
        ws_manager.close_player_connections_sync(duel.id, spectator_id)
    return duel


@app.delete("/api/duels/{duel_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_duel(duel_id: int, player: Player = Depends(get_current_player), db: Session = Depends(get_db)) -> None:
    duel = _duel_for_player(duel_id, player, db)
    db.delete(duel)
    db.commit()


@app.post("/api/duels/{duel_id}/events", response_model=DuelEventResponse, status_code=status.HTTP_201_CREATED)
def add_duel_event(duel_id: int, payload: DuelEventCreate, player: Player = Depends(get_current_player), db: Session = Depends(get_db)) -> DuelEvent:
    duel = _duel_for_player(duel_id, player, db)
    if duel.status == "finished":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="No se pueden registrar eventos en un duelo terminado")
    event = DuelEvent(
        duel_id=duel.id,
        event_type=payload.event_type,
        payload=payload.payload,
        actor_player_id=player.id,
        source_device=payload.source_device,
    )
    db.add(event)
    _bump_duel_revision(duel, db)
    db.commit()
    db.refresh(event)

    _broadcast_duel_event(duel, event)
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
    account = db.scalar(select(Player).where(Player.id == player_id, Player.is_active.is_(True))) if player_id else None
    is_player = account is not None and player_id in (duel.player1_id, duel.player2_id)
    invite = db.scalar(select(DuelSpectator.id).where(
        DuelSpectator.duel_id == duel_id,
        DuelSpectator.player_id == player_id,
        DuelSpectator.revoked_at.is_(None),
    )) if account is not None and not is_player and duel.status != "finished" else None
    if account is None or (not is_player and invite is None):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    role = "player" if is_player else "spectator"

    await ws_manager.connect(duel_id, websocket, player_id)

    await websocket.send_json({
        "type": "CONNECTED",
        "duel_id": duel_id,
        "role": role,
        "player_id": player_id,
    })
    db.expire(duel)
    db.refresh(duel)
    await websocket.send_json({
        "type": "DUEL_STATE",
        "revision": duel.revision,
        "duel": _duel_snapshot_data(duel, account),
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

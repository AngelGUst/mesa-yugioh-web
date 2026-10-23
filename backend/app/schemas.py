from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class PlayerCreate(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class PlayerLogin(BaseModel):
    username: str
    password: str


class PlayerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: EmailStr
    lp_wins: int
    lp_losses: int
    is_active: bool
    is_admin: bool
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class CardResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ygoprodeck_id: int
    name: str
    card_type: str | None
    description: str | None
    atk: int | None
    def_: int | None
    level: int | None
    race: str | None
    attribute: str | None
    human_readable_card_type: str | None
    frame_type: str | None
    archetype: str | None
    ygoprodeck_url: str | None
    image_url: str | None
    image_url_small: str | None
    image_url_cropped: str | None
    prints: list["CardPrintResponse"] = []


class CardPrintResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    set_name: str
    set_code: str
    language: str | None
    rarity: str | None
    rarity_code: str | None
    price: str | None


class DeckCardInput(BaseModel):
    card_id: int
    quantity: int = Field(default=1, ge=1, le=3)
    section: Literal["main", "extra", "side"] = "main"
    preferred_print_id: int | None = None


class DeckCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    cards: list[DeckCardInput] = Field(default_factory=list)


class DeckUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    cards: list[DeckCardInput] | None = None


class DeckImportRequest(BaseModel):
    name: str | None = Field(default=None, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    content: str = Field(min_length=5, description="Código YDKe, archivo .YDK o JSON")


class DeckCardResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    card_id: int
    quantity: int
    section: Literal["main", "extra", "side"]
    preferred_print_id: int | None
    card: CardResponse


class DeckResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    player_id: int
    created_at: datetime
    updated_at: datetime
    card_entries: list[DeckCardResponse] = []


class DuelCreate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    deck_id: int | None = None


class DuelJoin(BaseModel):
    duel_code: str = Field(min_length=4, max_length=20)
    deck_id: int | None = None


class DuelUpdate(BaseModel):
    player1_lp: int | None = Field(default=None, ge=0, le=99999)
    player2_lp: int | None = Field(default=None, ge=0, le=99999)
    status: str | None = Field(default=None, pattern="^(waiting|active|finished)$")
    turn: int | None = Field(default=None, ge=1)
    current_phase: str | None = Field(default=None, max_length=50)
    current_player: int | None = Field(default=None, ge=1, le=2)
    winner_id: int | None = None


class DuelEventCreate(BaseModel):
    event_type: str = Field(min_length=1, max_length=50)
    payload: dict | None = None
    source_device: Literal["web", "camera"] = "web"


class DuelEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    event_type: str
    payload: dict | None
    actor_player_id: int | None = None
    actor_username: str | None = None
    source_device: Literal["web", "camera"] = "web"
    card_id: int | None = None
    duel_card_id: int | None = None
    source_zone: str | None = None
    target_zone: str | None = None
    created_at: datetime


class DuelCardCreate(BaseModel):
    card_id: int
    zone: Literal[
        "main_deck", "extra_deck", "side_deck", "hand", "monster_zone", "spell_trap_zone",
        "field_spell", "pendulum", "extra_monster", "graveyard", "banished",
    ]
    source_zone: Literal["main_deck", "extra_deck", "side_deck"] = "main_deck"
    position: int | None = Field(default=None, ge=0, le=4)
    face_down: bool = False
    preferred_print_id: int | None = None
    source_device: Literal["web", "camera"] = "web"


class DuelCardMove(BaseModel):
    zone: Literal[
        "main_deck", "extra_deck", "side_deck", "hand", "monster_zone", "spell_trap_zone",
        "field_spell", "pendulum", "extra_monster", "graveyard", "banished",
    ]
    position: int | None = Field(default=None, ge=0, le=4)
    face_down: bool = False
    source_device: Literal["web", "camera"] = "web"


class CameraPairingRedeem(BaseModel):
    pairing_token: str = Field(min_length=32, max_length=128)


class CameraCardPlacement(DuelCardCreate):
    client_action_id: UUID


class CameraDeckCard(BaseModel):
    card_id: int
    name: str
    section: Literal["main", "extra", "side"]
    quantity: int
    preferred_print_id: int | None
    image_url_small: str | None
    passcode: int | None = None


class CameraSessionResponse(BaseModel):
    camera_token: str
    expires_at: datetime
    duel_id: int
    duel_code: str
    player_id: int
    player_username: str
    deck_cards: list[CameraDeckCard]


class CameraSessionInfo(BaseModel):
    expires_at: datetime
    duel_id: int
    duel_code: str
    player_id: int
    player_username: str
    deck_cards: list[CameraDeckCard]


class DuelCardResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    card_id: int | None
    card_name: str
    image_url: str | None
    player_id: int
    player_username: str
    zone: str
    position: int | None
    face_down: bool
    preferred_print_id: int | None
    hidden: bool = False
    hidden: bool = False
    updated_by_player_id: int
    updated_at: datetime


class DuelSpectatorCreate(BaseModel):
    username: str = Field(min_length=3, max_length=50)


class DuelSpectatorResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    player_id: int
    username: str
    invited_by_id: int
    created_at: datetime


class DuelResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    duel_code: str
    name: str | None
    player1_id: int
    player2_id: int | None
    player1_username: str
    player2_username: str | None
    player1_deck_id: int | None
    player2_deck_id: int | None
    player1_lp: int
    player2_lp: int
    status: str
    turn: int
    current_phase: str
    current_player: int
    revision: int
    winner_id: int | None
    viewer_role: Literal["player", "spectator"] = "player"
    created_at: datetime
    finished_at: datetime | None
    events: list[DuelEventResponse] = []

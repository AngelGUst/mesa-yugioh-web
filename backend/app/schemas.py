from datetime import datetime

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
    image_url: str | None


class DeckCardInput(BaseModel):
    card_id: int
    quantity: int = Field(default=1, ge=1, le=3)


class DeckCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    cards: list[DeckCardInput] = Field(default_factory=list)


class DeckUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    cards: list[DeckCardInput] | None = None


class DeckCardResponse(BaseModel):
    quantity: int
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
    player2_id: int | None = None


class DuelUpdate(BaseModel):
    player2_id: int | None = None
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


class DuelEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    event_type: str
    payload: dict | None
    created_at: datetime


class DuelResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    duel_code: str
    player1_id: int
    player2_id: int | None
    player1_lp: int
    player2_lp: int
    status: str
    turn: int
    current_phase: str
    current_player: int
    winner_id: int | None
    created_at: datetime
    finished_at: datetime | None
    events: list[DuelEventResponse] = []

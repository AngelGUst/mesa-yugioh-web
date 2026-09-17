from uuid import uuid4

from fastapi.testclient import TestClient

import main as main_module
from main import app


def test_health_and_auth_flow():
    with TestClient(app) as client:
        assert client.get("/health").json() == {"status": "healthy"}

        suffix = uuid4().hex[:10]
        payload = {
            "username": f"test_{suffix}",
            "email": f"test_{suffix}@example.com",
            "password": "password123",
        }
        register = client.post("/api/auth/register", json=payload)
        assert register.status_code == 201

        login = client.post("/api/auth/login", json=payload)
        assert login.status_code == 200
        token = login.json()["access_token"]

        profile = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert profile.status_code == 200
        assert profile.json()["username"] == payload["username"]


def test_cards_decks_and_duels_crud(monkeypatch):
    with TestClient(app) as client:
        suffix = uuid4().hex[:10]
        credentials = {
            "username": f"crud_{suffix}",
            "email": f"crud_{suffix}@example.com",
            "password": "password123",
        }
        client.post("/api/auth/register", json=credentials)
        token = client.post("/api/auth/login", json=credentials).json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        monkeypatch.setattr(
            main_module,
            "fetch_cards",
            lambda _: [{
                "id": 100000 + int(suffix[:6], 16),
                "name": "Blue-Eyes Test Dragon",
                "type": "Normal Monster",
                "desc": "Carta de prueba",
                "atk": 3000,
                "def": 2500,
                "level": 8,
                "race": "Dragon",
                "attribute": "LIGHT",
                "card_images": [{"image_url": "https://example.com/card.jpg"}],
            }],
        )
        imported = client.post("/api/cards/import", headers=headers)
        assert imported.status_code == 200
        card = client.get("/api/cards?search=Blue-Eyes").json()[0]

        created_deck = client.post(
            "/api/decks",
            headers=headers,
            json={"name": "Dragon test", "cards": [{"card_id": card["id"], "quantity": 2}]},
        )
        assert created_deck.status_code == 201
        deck_id = created_deck.json()["id"]
        updated_deck = client.put(f"/api/decks/{deck_id}", headers=headers, json={"name": "Dragon updated"})
        assert updated_deck.status_code == 200
        assert updated_deck.json()["name"] == "Dragon updated"

        created_duel = client.post("/api/duels", headers=headers, json={})
        assert created_duel.status_code == 201
        duel_id = created_duel.json()["id"]
        updated_duel = client.put(
            f"/api/duels/{duel_id}", headers=headers, json={"player1_lp": 7400, "current_phase": "MAIN_PHASE_1"}
        )
        assert updated_duel.status_code == 200
        assert updated_duel.json()["player1_lp"] == 7400

        assert client.delete(f"/api/decks/{deck_id}", headers=headers).status_code == 204
        assert client.delete(f"/api/duels/{duel_id}", headers=headers).status_code == 204

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
                "humanReadableCardType": "Normal Monster",
                "frameType": "normal",
                "desc": "Carta de prueba",
                "atk": 3000,
                "def": 2500,
                "level": 8,
                "race": "Dragon",
                "attribute": "LIGHT",
                "archetype": "Blue-Eyes",
                "ygoprodeck_url": "https://example.com/card",
                "card_images": [{
                    "image_url": "https://example.com/card.jpg",
                    "image_url_small": "https://example.com/card-small.jpg",
                    "image_url_cropped": "https://example.com/card-cropped.jpg",
                }],
                "card_sets": [{
                    "set_name": "Legend of Blue Eyes White Dragon",
                    "set_code": "LOB-EN001",
                    "set_rarity": "Ultra Rare",
                    "set_rarity_code": "(UR)",
                    "set_price": "10.00",
                }],
            }],
        )
        imported = client.post("/api/cards/import", headers=headers)
        assert imported.status_code == 200
        card = client.get("/api/cards?search=Blue-Eyes").json()[0]
        assert card["archetype"] == "Blue-Eyes"
        assert card["prints"] == [{
            "id": card["prints"][0]["id"],
            "set_name": "Legend of Blue Eyes White Dragon",
            "set_code": "LOB-EN001",
            "language": "EN",
            "rarity": "Ultra Rare",
            "rarity_code": "(UR)",
            "price": "10.00",
        }]
        print_id = card["prints"][0]["id"]

        created_deck = client.post(
            "/api/decks",
            headers=headers,
            json={
                "name": "Dragon test",
                "cards": [{
                    "card_id": card["id"],
                    "quantity": 2,
                    "section": "extra",
                    "preferred_print_id": print_id,
                }],
            },
        )
        assert created_deck.status_code == 201
        deck_id = created_deck.json()["id"]
        assert created_deck.json()["card_entries"][0]["section"] == "extra"
        assert created_deck.json()["card_entries"][0]["preferred_print_id"] == print_id
        updated_deck = client.put(f"/api/decks/{deck_id}", headers=headers, json={"name": "Dragon updated"})
        assert updated_deck.status_code == 200
        assert updated_deck.json()["name"] == "Dragon updated"

        created_duel = client.post(
            "/api/duels",
            headers=headers,
            json={"name": "Dragon room", "deck_id": deck_id},
        )
        assert created_duel.status_code == 201
        created_duel_payload = created_duel.json()
        duel_id = created_duel_payload["id"]
        assert created_duel_payload["name"] == "Dragon room"
        assert created_duel_payload["player1_deck_id"] == deck_id
        assert created_duel_payload["player1_username"] == credentials["username"]

        opponent_credentials = {
            "username": f"opponent_{suffix}",
            "email": f"opponent_{suffix}@example.com",
            "password": "password123",
        }
        assert client.post("/api/auth/register", json=opponent_credentials).status_code == 201
        opponent_token = client.post("/api/auth/login", json=opponent_credentials).json()["access_token"]
        joined_duel = client.post(
            "/api/duels/join",
            headers={"Authorization": f"Bearer {opponent_token}"},
            json={"duel_code": created_duel_payload["duel_code"]},
        )
        assert joined_duel.status_code == 200
        assert joined_duel.json()["status"] == "active"
        assert joined_duel.json()["player2_username"] == opponent_credentials["username"]
        assert client.post(
            "/api/duels/join",
            headers={"Authorization": f"Bearer {opponent_token}"},
            json={"duel_code": created_duel_payload["duel_code"]},
        ).status_code == 409

        updated_duel = client.put(
            f"/api/duels/{duel_id}", headers=headers, json={"player1_lp": 7400, "current_phase": "MAIN_PHASE_1"}
        )
        assert updated_duel.status_code == 200
        assert updated_duel.json()["player1_lp"] == 7400

        assert client.delete(f"/api/decks/{deck_id}", headers=headers).status_code == 204
        assert client.delete(f"/api/duels/{duel_id}", headers=headers).status_code == 204

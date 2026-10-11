from datetime import datetime, timedelta, timezone
from hashlib import sha256
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from starlette.websockets import WebSocketDisconnect

from app.db import SessionLocal
from app.models import Card, Deck, DeckCard, DuelCameraSession, DuelEvent, Player
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
                }, {
                    "set_name": "Legend of Blue Eyes White Dragon",
                    "set_code": "LOB-EN001",
                    "set_rarity": "Secret Rare",
                    "set_rarity_code": "(ScR)",
                    "set_price": "20.00",
                }],
            }],
        )
        imported = client.post("/api/cards/import", headers=headers)
        assert imported.status_code == 200
        ygoprodeck_id = 100000 + int(suffix[:6], 16)
        card = next(
            item for item in client.get("/api/cards?search=Blue-Eyes").json()
            if item["ygoprodeck_id"] == ygoprodeck_id
        )
        assert card["archetype"] == "Blue-Eyes"
        assert {(card_print["set_code"], card_print["rarity_code"]) for card_print in card["prints"]} == {
            ("LOB-EN001", "(UR)"),
            ("LOB-EN001", "(ScR)"),
        }
        print_id = next(card_print["id"] for card_print in card["prints"] if card_print["rarity_code"] == "(UR)")

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
        updated_deck = client.put(
            f"/api/decks/{deck_id}",
            headers=headers,
            json={
                "name": "Dragon updated",
                "cards": [{
                    "card_id": card["id"],
                    "quantity": 3,
                    "section": "main",
                    "preferred_print_id": print_id,
                }],
            },
        )
        assert updated_deck.status_code == 200
        assert updated_deck.json()["name"] == "Dragon updated"
        assert updated_deck.json()["card_entries"][0]["quantity"] == 3
        assert updated_deck.json()["card_entries"][0]["section"] == "main"

        created_duel = client.post(
            "/api/duels",
            headers=headers,
            json={"name": "Dragon room", "deck_id": deck_id},
        )
        assert created_duel.status_code == 201
        created_duel_payload = created_duel.json()
        duel_id = created_duel_payload["id"]
        assert created_duel_payload["name"] == "Dragon room"
        assert created_duel_payload["revision"] == 1
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
        assert joined_duel.json()["revision"] == 2
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

        placed_card = client.post(
            f"/api/duels/{duel_id}/cards",
            headers=headers,
            json={
                "card_id": card["id"],
                "source_zone": "main_deck",
                "zone": "monster_zone",
                "position": 0,
                "source_device": "camera",
            },
        )
        assert placed_card.status_code == 201
        assert placed_card.json()["card_name"] == "Blue-Eyes Test Dragon"
        assert placed_card.json()["player_id"] == created_duel.json()["player1_id"]
        assert client.get(f"/api/duels/{duel_id}/cards", headers=headers).json()[0]["zone"] == "monster_zone"
        assert client.put(
            f"/api/duels/{duel_id}/cards/{placed_card.json()['id']}",
            headers={"Authorization": f"Bearer {opponent_token}"},
            json={"zone": "graveyard"},
        ).status_code == 403

        spectator_credentials = {
            "username": f"board_viewer_{suffix}",
            "email": f"board_viewer_{suffix}@example.com",
            "password": "password123",
        }
        assert client.post("/api/auth/register", json=spectator_credentials).status_code == 201
        spectator_token = client.post("/api/auth/login", json=spectator_credentials).json()["access_token"]
        spectator_headers = {"Authorization": f"Bearer {spectator_token}"}
        assert client.post(
            f"/api/duels/{duel_id}/spectators",
            headers=headers,
            json={"username": spectator_credentials["username"]},
        ).status_code == 201
        visible_card = client.get(f"/api/duels/{duel_id}/cards", headers=spectator_headers).json()[0]
        assert visible_card["card_name"] == "Blue-Eyes Test Dragon"
        assert visible_card["hidden"] is False
        assert client.post(
            f"/api/duels/{duel_id}/cards",
            headers=headers,
            json={"card_id": card["id"], "zone": "monster_zone", "position": 0},
        ).status_code == 409

        with client.websocket_connect(f"/api/duels/{duel_id}/ws?token={spectator_token}") as spectator_socket:
            assert spectator_socket.receive_json()["role"] == "spectator"
            assert spectator_socket.receive_json()["type"] == "DUEL_STATE"
            moved_card = client.put(
                f"/api/duels/{duel_id}/cards/{placed_card.json()['id']}",
                headers=headers,
                json={"zone": "graveyard", "face_down": True, "source_device": "camera"},
            )
            assert moved_card.status_code == 200
            movement_message = spectator_socket.receive_json()
            assert movement_message["type"] == "DUEL_EVENT"
            assert movement_message["event"]["card_id"] is None
            assert movement_message["event"]["duel_card_id"] is None
            snapshot_card_events = [
                event for event in movement_message["duel"]["events"]
                if event["event_type"].startswith("CARD_")
            ]
            assert all(event["card_id"] is None for event in snapshot_card_events)
        assert moved_card.json()["zone"] == "graveyard"
        hidden_card = client.get(f"/api/duels/{duel_id}/cards", headers=spectator_headers).json()[0]
        assert hidden_card["card_name"] == "Carta oculta"
        assert hidden_card["card_id"] is None
        assert hidden_card["hidden"] is True
        spectator_duel = client.get(f"/api/duels/{duel_id}", headers=spectator_headers).json()
        hidden_events = [event for event in spectator_duel["events"] if event["event_type"].startswith("CARD_")]
        assert all(event["card_id"] is None and event["duel_card_id"] is None for event in hidden_events)
        with client.websocket_connect(f"/api/duels/{duel_id}/ws?token={spectator_token}") as spectator_socket:
            assert spectator_socket.receive_json()["role"] == "spectator"
            initial_state = spectator_socket.receive_json()
            assert initial_state["type"] == "DUEL_STATE"
            snapshot_events = [
                event for event in initial_state["duel"]["events"]
                if event["event_type"].startswith("CARD_")
            ]
            assert all(event["card_id"] is None and event["duel_card_id"] is None for event in snapshot_events)
        duel_after_card_moves = client.get(f"/api/duels/{duel_id}", headers=headers).json()
        card_events = [event for event in duel_after_card_moves["events"] if event["event_type"].startswith("CARD_")]
        assert [(event["source_zone"], event["target_zone"]) for event in card_events] == [
            ("main_deck", "monster_zone"),
            ("monster_zone", "graveyard"),
        ]
        assert all(event["actor_player_id"] == created_duel.json()["player1_id"] for event in card_events)
        assert all(event["source_device"] == "camera" for event in card_events)
        assert updated_duel.json()["revision"] == 3

        assert client.delete(f"/api/decks/{deck_id}", headers=headers).status_code == 409
        assert client.delete(f"/api/duels/{duel_id}", headers=headers).status_code == 204
        assert client.delete(f"/api/decks/{deck_id}", headers=headers).status_code == 204


def test_duel_websocket_sync():
    with TestClient(app) as client:
        # 1. Crear jugador 1 y duelo
        suffix = uuid4().hex[:10]
        p1_cred = {"username": f"ws_p1_{suffix}", "email": f"ws_p1_{suffix}@example.com", "password": "password123"}
        client.post("/api/auth/register", json=p1_cred)
        token1 = client.post("/api/auth/login", json=p1_cred).json()["access_token"]
        headers1 = {"Authorization": f"Bearer {token1}"}

        create_res = client.post("/api/duels", headers=headers1, json={"name": "WS Test Arena"})
        assert create_res.status_code == 201
        duel_id = create_res.json()["id"]

        spectator_credentials = {
            "username": f"ws_viewer_{suffix}",
            "email": f"ws_viewer_{suffix}@example.com",
            "password": "password123",
        }
        assert client.post("/api/auth/register", json=spectator_credentials).status_code == 201
        spectator_token = client.post("/api/auth/login", json=spectator_credentials).json()["access_token"]
        spectator_headers = {"Authorization": f"Bearer {spectator_token}"}
        assert client.post(
            f"/api/duels/{duel_id}/spectators",
            headers=headers1,
            json={"username": spectator_credentials["username"]},
        ).status_code == 201

        # 2. Conectar jugador al WebSocket
        with client.websocket_connect(f"/api/duels/{duel_id}/ws?token={token1}") as ws_player:
            welcome_player = ws_player.receive_json()
            assert welcome_player["type"] == "CONNECTED"
            assert welcome_player["role"] == "player"
            player_state = ws_player.receive_json()
            assert player_state["type"] == "DUEL_STATE"
            assert player_state["revision"] == 1

            # 3. Conectar espectador al WebSocket
            with client.websocket_connect(f"/api/duels/{duel_id}/ws?token={spectator_token}") as ws_spectator:
                welcome_spectator = ws_spectator.receive_json()
                assert welcome_spectator["type"] == "CONNECTED"
                assert welcome_spectator["role"] == "spectator"
                spectator_state = ws_spectator.receive_json()
                assert spectator_state["type"] == "DUEL_STATE"
                assert spectator_state["duel"]["revision"] == 1

                # 4. Probar PING / PONG
                ws_spectator.send_json({"action": "PING"})
                pong = ws_spectator.receive_json()
                assert pong["type"] == "PONG"

                # 5. Modificar estado vía REST y verificar broadcast en tiempo real a ambos sockets
                update_res = client.put(f"/api/duels/{duel_id}", headers=headers1, json={"player1_lp": 6000, "current_phase": "BATTLE_PHASE"})
                assert update_res.status_code == 200
                assert update_res.json()["revision"] == 2

                player_broadcast = ws_player.receive_json()
                assert player_broadcast["type"] == "DUEL_UPDATED"
                assert player_broadcast["revision"] == 2
                assert player_broadcast["duel"]["player1_lp"] == 6000
                assert player_broadcast["duel"]["current_phase"] == "BATTLE_PHASE"

                spectator_broadcast = ws_spectator.receive_json()
                assert spectator_broadcast["type"] == "DUEL_UPDATED"
                assert spectator_broadcast["duel"]["player1_lp"] == 6000

                # 6. Registrar evento y verificar broadcast de evento
                event_res = client.post(
                    f"/api/duels/{duel_id}/events",
                    headers=headers1,
                    json={"event_type": "ATTACK", "payload": {"target": "direct", "damage": 2000}},
                )
                assert event_res.status_code == 201

                event_msg_player = ws_player.receive_json()
                assert event_msg_player["type"] == "DUEL_EVENT"
                assert event_msg_player["revision"] == 3
                assert event_msg_player["event"]["event_type"] == "ATTACK"
                assert event_msg_player["duel"]["revision"] == 3

                event_msg_spectator = ws_spectator.receive_json()
                assert event_msg_spectator["type"] == "DUEL_EVENT"
                assert event_msg_spectator["event"]["event_type"] == "ATTACK"

                # Reconnecting clients receive the latest authoritative snapshot.
                ws_player.close()
                with client.websocket_connect(f"/api/duels/{duel_id}/ws?token={token1}") as ws_reconnected:
                    assert ws_reconnected.receive_json()["type"] == "CONNECTED"
                    reconnected_state = ws_reconnected.receive_json()
                    assert reconnected_state["type"] == "DUEL_STATE"
                    assert reconnected_state["revision"] == 3
                    assert reconnected_state["duel"]["player1_lp"] == 6000


def test_camera_pairing_is_one_time_scoped_and_expires_with_duel():
    with TestClient(app) as client:
        suffix = uuid4().hex[:10]
        credentials = {
            "username": f"camera_owner_{suffix}",
            "email": f"camera_owner_{suffix}@example.com",
            "password": "password123",
        }
        client.post("/api/auth/register", json=credentials)
        token = client.post("/api/auth/login", json=credentials).json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        with SessionLocal() as db:
            owner = db.scalar(select(Player).where(Player.username == credentials["username"]))
            card = Card(ygoprodeck_id=300000 + int(suffix[:6], 16), name="Camera Test Card")
            second_card = Card(ygoprodeck_id=400000 + int(suffix[:6], 16), name="Second Camera Test Card")
            db.add(card)
            db.add(second_card)
            db.flush()
            deck = Deck(name="Camera deck", player_id=owner.id)
            db.add(deck)
            db.flush()
            db.add(DeckCard(deck_id=deck.id, card_id=card.id, quantity=1, section="main"))
            db.add(DeckCard(deck_id=deck.id, card_id=second_card.id, quantity=1, section="main"))
            db.commit()
            deck_id = deck.id
            card_id = card.id
            second_card_id = second_card.id

        duel = client.post("/api/duels", headers=headers, json={"name": "Camera room", "deck_id": deck_id}).json()
        duel_id = duel["id"]
        pairing = client.post(f"/api/duels/{duel_id}/camera-pairings", headers=headers)
        assert pairing.status_code == 200
        pairing_data = pairing.json()
        assert datetime.fromisoformat(pairing_data["expires_at"]) > datetime.now(timezone.utc)

        redeemed = client.post("/api/camera-pairings/redeem", json={"pairing_token": pairing_data["pairing_token"]})
        assert redeemed.status_code == 200
        camera_session = redeemed.json()
        assert camera_session["duel_id"] == duel_id
        assert camera_session["player_username"] == credentials["username"]
        assert camera_session["deck_cards"][0]["card_id"] == card_id
        camera_headers = {"Authorization": f"Bearer {camera_session['camera_token']}"}

        assert client.post("/api/camera-pairings/redeem", json={"pairing_token": pairing_data["pairing_token"]}).status_code == 404
        assert client.put(f"/api/duels/{duel_id}", headers=camera_headers, json={"player1_lp": 10}).status_code == 401
        assert client.get("/api/camera-session", headers=camera_headers).status_code == 200

        capture_id = str(uuid4())
        camera_action = {
            "client_action_id": capture_id,
            "card_id": card_id,
            "source_zone": "main_deck",
            "zone": "monster_zone",
            "position": 0,
        }
        placed = client.post(
            "/api/camera-session/cards",
            headers=camera_headers,
            json=camera_action,
        )
        assert placed.status_code == 201
        retried_placement = client.post("/api/camera-session/cards", headers=camera_headers, json=camera_action)
        assert retried_placement.status_code == 201
        assert retried_placement.json()["id"] == placed.json()["id"]
        duel_after_placement = client.get(f"/api/duels/{duel_id}", headers=headers).json()
        placement_event = next(event for event in duel_after_placement["events"] if event["event_type"] == "CARD_PLACED")
        assert placement_event["source_device"] == "camera"
        assert placement_event["actor_username"] == credentials["username"]
        assert len([event for event in duel_after_placement["events"] if event["event_type"] == "CARD_PLACED"]) == 1
        camera_board = client.get("/api/camera-session/cards", headers=camera_headers)
        assert camera_board.status_code == 200
        assert camera_board.json()[0]["position"] == 0
        occupied_slot = client.post(
            "/api/camera-session/cards",
            headers=camera_headers,
            json={
                "client_action_id": str(uuid4()),
                "card_id": second_card_id,
                "source_zone": "main_deck",
                "zone": "monster_zone",
                "position": 0,
            },
        )
        assert occupied_slot.status_code == 409

        second_pairing = client.post(f"/api/duels/{duel_id}/camera-pairings", headers=headers).json()
        with SessionLocal() as db:
            stored_pairing = db.scalar(select(DuelCameraSession).where(
                DuelCameraSession.pairing_token_hash == sha256(second_pairing["pairing_token"].encode()).hexdigest()
            ))
            stored_pairing.pairing_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
            db.commit()
        expired = client.post("/api/camera-pairings/redeem", json={"pairing_token": second_pairing["pairing_token"]})
        assert expired.status_code == 410

        assert client.put(f"/api/duels/{duel_id}", headers=headers, json={"status": "finished"}).status_code == 200
        assert client.get("/api/camera-session", headers=camera_headers).status_code == 401


def test_duel_spectator_access_is_invited_read_only_and_revocable():
    with TestClient(app) as client:
        suffix = uuid4().hex[:10]
        owner_credentials = {
            "username": f"owner_{suffix}",
            "email": f"owner_{suffix}@example.com",
            "password": "password123",
        }
        spectator_credentials = {
            "username": f"viewer_{suffix}",
            "email": f"viewer_{suffix}@example.com",
            "password": "password123",
        }
        owner_id = client.post("/api/auth/register", json=owner_credentials).json()["id"]
        client.post("/api/auth/register", json=spectator_credentials)
        owner_token = client.post("/api/auth/login", json=owner_credentials).json()["access_token"]
        spectator_token = client.post("/api/auth/login", json=spectator_credentials).json()["access_token"]
        owner_headers = {"Authorization": f"Bearer {owner_token}"}
        spectator_headers = {"Authorization": f"Bearer {spectator_token}"}
        duel = client.post("/api/duels", headers=owner_headers, json={"name": "Private room"}).json()
        duel_id = duel["id"]

        assert client.get(f"/api/duels/{duel_id}", headers=spectator_headers).status_code == 404
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect(f"/api/duels/{duel_id}/ws?token={spectator_token}"):
                pass

        invite_response = client.post(
            f"/api/duels/{duel_id}/spectators",
            headers=owner_headers,
            json={"username": spectator_credentials["username"]},
        )
        assert invite_response.status_code == 201
        assert invite_response.json()["invited_by_id"] == owner_id
        assert client.get(f"/api/duels/{duel_id}", headers=spectator_headers).json()["viewer_role"] == "spectator"
        assert any(item["id"] == duel_id for item in client.get("/api/duels", headers=spectator_headers).json())
        assert client.put(
            f"/api/duels/{duel_id}",
            headers=spectator_headers,
            json={"player1_lp": 1000},
        ).status_code == 403
        assert client.post(
            f"/api/duels/{duel_id}/events",
            headers=spectator_headers,
            json={"event_type": "ATTACK"},
        ).status_code == 403

        with client.websocket_connect(f"/api/duels/{duel_id}/ws?token={spectator_token}") as spectator_socket:
            assert spectator_socket.receive_json()["role"] == "spectator"
            assert spectator_socket.receive_json()["type"] == "DUEL_STATE"
            assert client.delete(
                f"/api/duels/{duel_id}/spectators/{invite_response.json()['player_id']}",
                headers=owner_headers,
            ).status_code == 204
            with pytest.raises(WebSocketDisconnect):
                spectator_socket.receive_json()

        assert client.get(f"/api/duels/{duel_id}", headers=spectator_headers).status_code == 404

        reinvite = client.post(
            f"/api/duels/{duel_id}/spectators",
            headers=owner_headers,
            json={"username": spectator_credentials["username"]},
        )
        assert reinvite.status_code == 201
        assert client.put(
            f"/api/duels/{duel_id}",
            headers=owner_headers,
            json={"status": "finished"},
        ).status_code == 200
        assert client.get(f"/api/duels/{duel_id}", headers=spectator_headers).status_code == 404
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect(f"/api/duels/{duel_id}/ws?token={spectator_token}"):
                pass


import asyncio
import json
import logging
from typing import Any
from fastapi import WebSocket

logger = logging.getLogger("duel_assistant.ws")


class WebSocketManager:
    """Manages active WebSocket connections grouped by duel room."""

    def __init__(self) -> None:
        self.rooms: dict[int, set[WebSocket]] = {}
        self.loop: asyncio.AbstractEventLoop | None = None

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self.loop = loop

    async def connect(self, duel_id: int, websocket: WebSocket) -> None:
        await websocket.accept()
        if duel_id not in self.rooms:
            self.rooms[duel_id] = set()
        self.rooms[duel_id].add(websocket)
        logger.info(f"WebSocket client connected to duel {duel_id}. Total: {len(self.rooms[duel_id])}")

    def disconnect(self, duel_id: int, websocket: WebSocket) -> None:
        if duel_id in self.rooms:
            self.rooms[duel_id].discard(websocket)
            if not self.rooms[duel_id]:
                del self.rooms[duel_id]
        logger.info(f"WebSocket client disconnected from duel {duel_id}")

    async def broadcast(self, duel_id: int, message: dict[str, Any]) -> None:
        if duel_id not in self.rooms:
            return

        dead_connections: set[WebSocket] = set()
        text_data = json.dumps(message)

        for connection in list(self.rooms[duel_id]):
            try:
                await connection.send_text(text_data)
            except Exception as exc:
                logger.warning(f"Error broadcasting to client in duel {duel_id}: {exc}")
                dead_connections.add(connection)

        for dead in dead_connections:
            self.disconnect(duel_id, dead)

    def broadcast_sync(self, duel_id: int, message: dict[str, Any]) -> None:
        """Thread-safe broadcast trigger from synchronous FastAPI route handlers."""
        if duel_id not in self.rooms:
            return

        if self.loop and self.loop.is_running():
            asyncio.run_coroutine_threadsafe(self.broadcast(duel_id, message), self.loop)
            return

        try:
            running_loop = asyncio.get_running_loop()
            running_loop.create_task(self.broadcast(duel_id, message))
        except RuntimeError:
            logger.warning(f"No running event loop available to broadcast for duel {duel_id}")


ws_manager = WebSocketManager()

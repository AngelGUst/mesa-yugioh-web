# Duel Assistant — Plan de implementación vigente

**Proyecto:** asistente digital para duelos físicos de Yu-Gi-Oh!
**Stack implementado:** FastAPI, SQLAlchemy, PostgreSQL, SvelteKit, TypeScript y Docker Compose.
**Actualizado:** octubre de 2026.

> Este documento reemplaza el plan inicial de scaffolding. La estructura real del repositorio es más compacta que la propuesta original: los endpoints se concentran en `backend/main.py`, los modelos y contratos viven en `backend/app/`, y las rutas SvelteKit están en `frontend/src/routes/`.

## Arquitectura actual

```text
Navegador SvelteKit
  ├── REST autenticado con JWT ─┐
  └── WebSocket versionado ─────┴── FastAPI
                  ├── SQLAlchemy
                  ├── revisión persistida del duelo
                  ├── YGOProDeck (solo importación)
                  └── PostgreSQL o SQLite local
```

Docker Compose inicia:

- `postgres`: PostgreSQL 16 con volumen persistente y health check.
- `backend`: FastAPI en el puerto `8000`.
- `frontend`: SvelteKit en el puerto `5173` del host (`3000` dentro del contenedor).

PostgreSQL no publica puertos al host. Las credenciales se obtienen de un `.env` local ignorado por Git.

## Fases completadas

### 1. Base de la aplicación

- Configuración Docker Compose y health checks.
- CORS para el frontend local.
- Endpoint `GET /health`.
- Configuración tipada mediante `pydantic-settings`.
- Creación y actualización compatible del esquema al arrancar.

### 2. Autenticación

- Registro: `POST /api/auth/register`.
- Login JWT: `POST /api/auth/login`.
- Perfil de sesión: `GET /api/auth/me`.
- Contraseñas protegidas con bcrypt.
- Seed de administrador idempotente.
- Cliente SvelteKit centralizado para enviar `Authorization: Bearer <JWT>` y gestionar sesión inválida.

### 3. Catálogo y modelado de cartas

- Catálogo local: `GET /api/cards?search=...`.
- Importación autenticada: `POST /api/cards/import?search=...&limit=...`.
- Sincronización por `ygoprodeck_id`.
- Consultas parciales al proveedor con `fname`.
- Separación entre:
  - **Carta canónica:** datos de juego usados por decks y futuros eventos.
  - **Impresión física:** set, idioma, rareza, código de rareza y precio.
- Migración de unicidad de impresiones para permitir variantes con el mismo código de set y rarezas diferentes.

### 4. Gestión de decks

- CRUD protegido bajo `/api/decks`.
- Entradas con cantidad, Main Deck, Extra Deck o Side Deck.
- Impresión física preferida opcional.
- Validación de pertenencia entre impresión y carta.
- Bloqueo controlado al eliminar un deck referenciado por un duelo.
- Interfaz `/decks` con búsqueda local, importación por demanda, edición y persistencia.
- Deduplicación de resultados e identificación estable del render para impedir errores `each_key_duplicate`.

### 5. Salas de duelo

- Crear sala: `POST /api/duels`.
- Unirse por código: `POST /api/duels/join`.
- Listar, consultar, actualizar y eliminar: `/api/duels` y `/api/duels/{id}`.
- Deck opcional por participante.
- Estado persistido: LP, turno, fase, estado, ganador y fecha de finalización.
- Eventos persistidos: `POST /api/duels/{id}/events`.

### 6. Tablero conectado y sincronización fiable

- La ruta `duel/[id]` carga un duelo persistido y permite actualizar LP, turno, fase y resultado.
- El endpoint WebSocket `/api/duels/{id}/ws` envía `CONNECTED` seguido de `DUEL_STATE` con el snapshot más reciente.
- La columna `duels.revision` empieza en `1` y aumenta atómicamente al cambiar estado, unirse un participante o registrar un evento.
- `DUEL_UPDATED` y `DUEL_EVENT` transportan la revisión; los eventos incluyen también un snapshot para reconciliar el estado con la revisión.
- Al reconectar, el servidor reenvía el snapshot. El cliente aplica snapshots no antiguos y descarta broadcasts con una revisión ya procesada.
- `ensure_schema()` añade `revision` a bases SQLite/PostgreSQL existentes. Alembic sigue pendiente como solución formal.
- Los tests cubren snapshots al conectar y reconectar, incrementos de revisión, ping/pong y difusión.
- Las salas son privadas: REST y WebSocket requieren ser jugador o tener una invitación activa asociada a una cuenta.
- Los espectadores invitados son de solo lectura; los jugadores pueden listar, invitar y revocar accesos. Revocar cierra el WebSocket y finalizar el duelo invalida invitaciones.
- `duel_spectators` registra invitador, fecha y revocación; una invitación revocada puede reactivarse.

### 7. Estado de tablero e historial de cartas

- `duel_cards` conserva cada copia física registrada: carta, jugador, zona, posición, estado boca abajo e impresión elegida.
- `GET/POST /api/duels/{id}/cards` lista y coloca copias; `PUT /api/duels/{id}/cards/{card_id}` mueve una copia existente.
- Solo se colocan cartas del deck asignado al jugador y no se puede superar su cantidad. Los slots ocupados se rechazan.
- `duel_events` registra actor, username, fuente (`web`/`camera`), carta y zonas de origen/destino.
- El tablero permite elegir carta del deck y zona, mover cartas propias y ver el estado actual; las cartas privadas o boca abajo se ocultan a otros usuarios, incluso en el historial.
- El test CRUD valida colocación, movimiento, límites, auditoría y privacidad de cartas ocultas.

### 8. Cámara móvil y escaneo confirmado

- `POST /api/duels/{id}/camera-pairings` genera un QR de un solo uso que vence en cinco minutos.
- `POST /api/camera-pairings/redeem` canjea el QR por un token de cámara limitado al jugador/duelo; la sesión dura hasta 12 horas como máximo y se revoca al terminar la partida.
- La ruta `/scanner` abre la cámara trasera solo en contexto HTTPS y puede reanudar una sesión previamente emparejada.
- AprilTagJS local/WASM detecta los IDs `0`, `1`, `2` y `4` de la familia `tagStandard41h12`; con sus centros calcula una homografía y dibuja la superposición de zonas.
- Una captura usa Tesseract.js en el navegador para proponer nombres del deck autorizado. El jugador selecciona o corrige la carta, elige zona/posición y confirma; no se escribe nada antes de esa confirmación.
- `POST /api/camera-session/cards` valida deck, cantidad y slot; registra `source_device=camera` en una transacción y exige `client_action_id` para que un reintento no duplique la acción.
- Si la cámara pierde permiso, se detiene o faltan marcadores, la confirmación se bloquea. Si falla la red, se conserva la captura y puede reintentarse con el mismo ID.
- AprilTagJS se distribuye localmente con su licencia/NOTICE BSD-2-Clause. El modelo OCR inglés se descarga en el primer uso; si no carga, queda disponible la selección manual del deck.
- Falta validar manualmente la nitidez/distancia de los marcadores impresos y el flujo completo en Android/iOS; las pruebas automatizadas cubren pairing, expiración, permisos, auditoría e idempotencia de API.

## API disponible

| Recurso | Endpoints principales |
|---|---|
| Salud | `GET /`, `GET /health` |
| Autenticación | `POST /api/auth/register`, `POST /api/auth/login`, `GET /api/auth/me` |
| Cartas | `GET /api/cards`, `POST /api/cards/import` |
| Decks | `GET/POST /api/decks`, `GET/PUT/DELETE /api/decks/{id}` |
| Duelos | `GET/POST /api/duels`, `GET/PUT/DELETE /api/duels/{id}`, `POST /api/duels/join`, `POST /api/duels/{id}/events` |
| Cartas en duelo | `GET/POST /api/duels/{id}/cards`, `PUT /api/duels/{id}/cards/{card_id}` |
| Espectadores | `GET/POST /api/duels/{id}/spectators`, `DELETE /api/duels/{id}/spectators/{player_id}` |
| Cámara | `POST /api/duels/{id}/camera-pairings`, `POST /api/camera-pairings/redeem`, `GET /api/camera-session`, `POST /api/camera-session/cards`, `POST /api/camera-session/revoke` |
| Tiempo real | `WS /api/duels/{id}/ws` (`DUEL_STATE`, `DUEL_UPDATED`, `DUEL_EVENT`) |

Los recursos de cartas, decks y duelos exigen una sesión JWT cuando corresponda. Los contratos navegables están disponibles en `http://localhost:8000/docs` cuando la API está activa.

## Ejecución y comprobación

1. Defina `SECRET_KEY` y `POSTGRES_PASSWORD` en `.env` de la raíz.
2. Inicie el stack:

   ```powershell
   docker compose up -d --build
   docker compose ps
   ```

3. Verifique la API:

   ```powershell
   curl.exe --fail http://localhost:8000/health
   ```

4. Ejecute las pruebas del backend:

   ```powershell
   docker compose exec -T backend sh -c "PYTHONPATH=/app pytest -q"
   ```

5. Compile el frontend:

   ```powershell
   Set-Location frontend
   npm run build
   ```

## Fases pendientes

### 9. Validación de cámara en dispositivos físicos y E2E

1. Instalar `.certs/rootCA.pem` en el teléfono de pruebas y abrir el scanner desde `https://<IP-LAN>`.
2. Probar la cámara trasera, permisos, pérdida/reconexión de red y liberación del stream en Android/iOS.
3. Probar cada AprilTag impreso en el tapete y confirmar calibración/overlay con distinta iluminación y distancias.
4. Medir la precisión práctica de OCR y ajustar el flujo de corrección manual, sin permitir cambios antes de confirmar.
5. Añadir pruebas end-to-end con dos jugadores y un teléfono emparejado.
6. Para pruebas físicas, usar [`docs/marcadores/hoja_marcadores_A4.svg`](marcadores/hoja_marcadores_A4.svg); los PNG originales son de 9 x 9 px y no se imprimen directamente.

### 10. Robustez y evolución

- Sustituir las migraciones de arranque por Alembic.
- Añadir pruebas end-to-end para autenticación, constructor y salas.
- Añadir observabilidad de errores del proveedor YGOProDeck.
- Implementar reglas, efectos y cadenas de manera gradual; no forma parte del MVP actual.

# Duel Assistant — Plan de implementación vigente

**Proyecto:** asistente digital para duelos físicos de Yu-Gi-Oh!
**Stack implementado:** FastAPI, SQLAlchemy, PostgreSQL, SvelteKit, TypeScript y Docker Compose.
**Actualizado:** septiembre de 2026.

> Este documento reemplaza el plan inicial de scaffolding. La estructura real del repositorio es más compacta que la propuesta original: los endpoints se concentran en `backend/main.py`, los modelos y contratos viven en `backend/app/`, y las rutas SvelteKit están en `frontend/src/routes/`.

## Arquitectura actual

```text
Navegador SvelteKit
  └── REST autenticado con JWT
        └── FastAPI
              ├── SQLAlchemy
              ├── YGOProDeck (solo importación de catálogo)
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

## API disponible

| Recurso | Endpoints principales |
|---|---|
| Salud | `GET /`, `GET /health` |
| Autenticación | `POST /api/auth/register`, `POST /api/auth/login`, `GET /api/auth/me` |
| Cartas | `GET /api/cards`, `POST /api/cards/import` |
| Decks | `GET/POST /api/decks`, `GET/PUT/DELETE /api/decks/{id}` |
| Duelos | `GET/POST /api/duels`, `GET/PUT/DELETE /api/duels/{id}`, `POST /api/duels/join`, `POST /api/duels/{id}/events` |

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

### 6. Tablero de duelo conectado

1. Crear la ruta dinámica `duel/[id]`.
2. Cargar el estado real y los eventos del duelo.
3. Persistir modificaciones de LP, turno, fase y resultado.
4. Reemplazar el tablero de demostración.

### 7. Sincronización en tiempo real

1. Añadir WebSockets autenticados.
2. Publicar cambios de estado y eventos tras persistirlos.
3. Implementar reconexión, rehidratación y control de versiones del estado.
4. Definir permisos de jugador y espectador a nivel de sala.

### 8. Cámara móvil y escaneo confirmado

1. Crear la ruta móvil `/scanner`.
2. Vincular el teléfono mediante QR y un token temporal de un solo uso.
3. Abrir la cámara trasera con `getUserMedia` y liberarla correctamente al cerrar.
4. Calibrar el tapete con cuatro marcadores ArUco o AprilTags.
5. Implementar captura puntual, reconocimiento asistido y confirmación humana.
6. Registrar la acción aprobada como evento de duelo.

### 9. Robustez y evolución

- Sustituir las migraciones de arranque por Alembic.
- Añadir pruebas end-to-end para autenticación, constructor y salas.
- Añadir observabilidad de errores del proveedor YGOProDeck.
- Implementar reglas, efectos y cadenas de manera gradual; no forma parte del MVP actual.

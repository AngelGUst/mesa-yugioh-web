# Duel Assistant - Progreso del Proyecto

## Descripción

Duel Assistant es una aplicación para asistir duelos físicos de Yu-Gi-Oh!, registrando jugadores, cartas, decks, puntos de vida, turnos, fases y eventos.

## Stack

- Backend: FastAPI, SQLAlchemy, JWT y bcrypt.
- Frontend: SvelteKit, TypeScript y CSS responsive.
- Base de datos: PostgreSQL.
- Infraestructura: Docker Compose.
- Cartas: API de YGOProDeck.
- CLI: Node.js, pnpm, Inquirer, Chalk y Figlet.

## Backend Implementado

### Autenticación

- Registro de usuarios.
- Login con usuario y contraseña.
- Hashing de contraseñas con bcrypt.
- Tokens JWT.
- Endpoint `/api/auth/me`.
- Campo `is_admin` en `Player`.
- Seed idempotente para el administrador.

Ejecutar la seed:

```powershell
docker compose exec -T backend python seed.py
```

### Modelos

- `Player`
- `Card`
- `Deck`
- `DeckCard` con sección Main, Extra o Side Deck e impresión física preferida opcional.
- `CardPrint`
- `Duel`
- `DuelEvent`

### Cartas

```text
GET  /api/cards
POST /api/cards/import
```

La importación desde YGOProDeck guarda nombre, tipo, descripción, ATK, DEF, nivel, raza, atributo, arquetipo, imágenes y datos de presentación. Es idempotente mediante `ygoprodeck_id`; además sincroniza las impresiones físicas por código de set, idioma, rareza y precio.

Ejemplo:

```text
POST /api/cards/import?search=Dark%20Magician&limit=1
```

### Decks

CRUD protegido por autenticación:

```text
GET    /api/decks
POST   /api/decks
GET    /api/decks/{id}
PUT    /api/decks/{id}
DELETE /api/decks/{id}
```

Cada deck pertenece a un jugador y puede contener cartas canónicas con cantidades, sección Main/Extra/Side y una impresión física preferida opcional.

### Duelos

CRUD protegido:

```text
GET    /api/duels
POST   /api/duels
GET    /api/duels/{id}
PUT    /api/duels/{id}
DELETE /api/duels/{id}
POST   /api/duels/{id}/events
POST   /api/duels/join
```

Los duelos manejan nombre, código de sala, jugadores, decks seleccionados, LP, estado, turno, fase, ganador y eventos. Un segundo jugador puede unirse mediante código mientras la sala esté disponible.

## Frontend Implementado

Rutas del MVP:

```text
/login
/
/decks
/duel/new
/duel/demo
/result/demo
```

### Login y navegación

- Login y registro conectados al backend.
- JWT guardado tras autenticar y validado por `/api/auth/me`.
- Redirección al login si la sesión no existe, expira o es inválida.
- Home alimentado por perfil, decks y duelos reales.
- Sidebar responsive.

### Home

- Duelos activos.
- Salas en espera.
- Códigos de sala.
- Estadísticas.
- Acceso a decks y nuevos duelos.

### Decks y salas

- Constructor de decks conectado al CRUD real.
- Búsqueda en catálogo local e importación bajo demanda desde YGOProDeck.
- Selección de Main/Extra/Side Deck e impresión física preferida.
- Creación de salas con deck opcional y unión por código de sala.

### Sala de duelo

- LP de ambos jugadores.
- Turno y fase actuales.
- Modificación visual de LP.
- Fin de turno.
- Conceder duelo.
- Historial de acciones.
- Pantalla de resultado.

## Tablero de Duelo

El tablero visual contiene las zonas solicitadas:

- Removed Cards / Banish Pile.
- Extra Monster Zone.
- Field Spell Zone.
- Main Monster Zone con cinco casillas.
- Graveyard.
- Extra Deck.
- Spell & Trap Zone con cinco casillas.
- Main Deck.
- Player's Hand.
- Campo del oponente invertido y en modo visual.

La zona de cartas removidas está encima de Extra Monster Zone. En el campo del jugador incluye cartas retiradas de ejemplo y el botón de escaneo.

## Escaneo de Cartas

Actualmente existe la interfaz visual de la zona `Removed Cards` y el botón `Escanear carta`.

El escaneo continuo real todavía está pendiente. El flujo planeado es:

```text
Abrir cámara trasera
	-> guía cenital
	-> captura continua
	-> envío de imagen al backend
	-> OCR/reconocimiento de carta
	-> confirmación
	-> agregar carta a Removed Cards
```

Pendiente:

- `getUserMedia` para cámara trasera.
- Captura continua.
- Endpoint `/api/cards/scan`.
- OCR o reconocimiento visual.
- Confirmación de carta detectada.
- Liberación de cámara al cerrar.

## Docker y PostgreSQL

Servicios:

```text
postgres
backend
frontend
```

Puertos actuales:

```text
Frontend:   http://localhost:5173
Backend:    http://localhost:8000
PostgreSQL: localhost:5433
```

Iniciar:

```powershell
docker compose up -d --build
```

Comprobar:

```powershell
docker compose ps
```

No usar `docker compose down -v` salvo que se quieran borrar los datos persistentes.

### DataGrip

Usar los valores de `POSTGRES_*` configurados en el entorno local. No guardar credenciales en este documento ni en el repositorio.

Tablas principales:

```text
players
cards
card_prints
decks
deck_cards
duels
duel_events
```

## CLI DUEL

Se creó el proyecto independiente `dev-cli/`.

Incluye:

- Banner `DUEL`.
- Selección interactiva de servicios.
- Backend obligatorio.
- Frontend opcional.
- PostgreSQL opcional con Docker.
- Logs con colores y prefijos.
- Apagado con `Ctrl+C`.
- Modo `--dry`.

Uso:

```powershell
cd dev-cli
pnpm install
pnpm dev
```

Vista previa:

```powershell
pnpm dev --dry
```

## Validaciones Realizadas

- Registro y login.
- JWT y `/api/auth/me`.
- Seed del administrador.
- Importación real de cartas desde YGOProDeck.
- CRUD de decks.
- CRUD de duelos.
- Eventos de duelo.
- Conexión PostgreSQL con SQLAlchemy.
- Conexión externa desde DataGrip.
- Build de SvelteKit.
- Rutas frontend con HTTP 200.
- Build y ejecución de Docker Compose.
- Sintaxis del CLI DUEL.

Tests backend actuales:

```text
2 passed
```

## Estado Actual

### Completado

- Backend FastAPI base.
- Autenticación JWT.
- Administrador seed.
- Modelos y tablas de cartas, decks, duelos y eventos.
- CRUD de decks y duelos.
- Importación YGOProDeck.
- Constructor de decks conectado al catálogo local y a YGOProDeck.
- Salas reales con creación, deck seleccionado y unión por código.
- Impresiones físicas por set, idioma y rareza.
- PostgreSQL con Docker.
- Configuración para DataGrip.
- CLI DUEL.
- Mockups navegables del MVP.
- Tablero con las zonas reales.
- Zona de cartas removidas.
- Diseño responsive.
- Pruebas backend básicas.

### Pendiente

- Cargar el tablero de un duelo real en lugar del demo visual.
- WebSockets para tiempo real.
- Estado de duelo compartido.
- Motor de reglas y validación de acciones.
- Escaneo continuo con cámara/OCR.
- Chat y espectadores.
- Replay e historial completo.
- Rangos y estadísticas avanzadas.
- Migraciones formales con Alembic.
- Tests end-to-end.

## Próximo Objetivo

Construir la sala de duelo real en `duel/[id]`:

1. Cargar el duelo, participantes, LP, turno, fase y eventos desde la API.
2. Persistir las acciones del tablero mediante `PUT /api/duels/{id}` y `POST /api/duels/{id}/events`.
3. Sustituir el demo visual por el estado del duelo creado o unido.
4. Después, incorporar WebSockets para sincronizar ambas sesiones sin recargar.

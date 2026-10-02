# Duel Assistant — Progreso del proyecto

**Actualizado:** octubre de 2026
**Estado general:** MVP de gestión de jugadores, cartas, decks y salas funcional. El tablero compartido en tiempo real y el escaneo móvil aún no están implementados.

## Resumen del MVP actual

| Área | Estado | Implementación actual |
|---|---|---|
| Infraestructura | Funcional | Docker Compose levanta PostgreSQL 16, backend FastAPI y frontend SvelteKit con health checks. |
| Autenticación | Funcional | Registro, login, hash bcrypt, JWT, `/api/auth/me`, guardas de sesión y seed administrativo. |
| Home | Funcional | Carga perfil, decks, duelos y estadísticas mediante JWT. |
| Catálogo | Funcional | Consulta local, importación idempotente YGOProDeck, metadatos e imágenes. |
| Impresiones físicas | Funcional | `card_prints` conserva set, código, idioma, rareza, código de rareza y precio. |
| Decks backend | Funcional | CRUD protegido, secciones Main/Extra/Side e impresión preferida validada. |
| Decks frontend | Funcional | Búsqueda local, importación bajo demanda, edición, guardado y borrado controlado. |
| Salas y duelos backend | Funcional | Crear, unirse con código, seleccionar deck, actualizar LP/turno/fase y persistir eventos. |
| Tablero real | Funcional | Ruta dinámica `duel/[id]` conectada a duelos persistidos, layout oficial de 7 columnas (Regla Maestra) y acceso directo desde el inicio. |
| PWA y Caché | Funcional | Service Worker nativo con precarga en segundo plano, caché offline de cartas YGOProDeck y manifiesto instalable. |
| Tiempo real | Funcional | WebSocket autenticado para jugadores, sincronización de LP/fase/turno y eventos, ping periódico y reconexión automática. |
| Cámara y escaneo | Pendiente | No hay ruta móvil, QR, `getUserMedia`, calibración ni OCR. |

## Entregables completados

### Autenticación y experiencia de cuenta

- Registro de usuarios con validación de duplicados.
- Inicio de sesión y almacenamiento del JWT como `duel_session`.
- Validación de sesión y redirección al login cuando el token no existe o no es válido.
- Cierre de sesión desde el shell de la aplicación.
- Usuario administrador inicial mediante `backend/seed.py`.

### Catálogo de cartas e impresiones

- `POST /api/cards/import` importa cartas desde YGOProDeck y actualiza registros ya existentes por `ygoprodeck_id`.
- La importación usa `fname`, que admite búsquedas parciales como `GRAPHA`, en vez del parámetro de nombre exacto.
- Una respuesta `400` de YGOProDeck causada por una consulta sin coincidencias se interpreta como resultado vacío; los fallos reales del proveedor se devuelven como `502`.
- Las cartas incluyen tipo, descripción, ATK, DEF, nivel, raza, atributo, arquetipo, URL de YGOProDeck e imágenes.
- Las impresiones físicas se distinguen por carta, código de set, código de rareza y rareza. Esto conserva variantes que comparten `set_code`.
- El esquema aplica migraciones de arranque para bases SQLite y PostgreSQL existentes. Alembic sigue pendiente como solución formal de migraciones.

### Decks

- `GET`, `POST`, `GET /{id}`, `PUT /{id}` y `DELETE /{id}` en `/api/decks`.
- Un deck pertenece al jugador autenticado.
- Cada entrada usa una carta canónica, cantidad, sección (`main`, `extra` o `side`) e impresión preferida opcional.
- El backend comprueba que la impresión preferida pertenezca a la carta elegida.
- No se permite repetir la misma carta como entradas diferentes.
- No se permite borrar un deck que esté seleccionado por un duelo; la API devuelve `409` y solicita eliminar primero el duelo.
- El constructor de `/decks` reemplazó los datos de ejemplo por consultas autenticadas reales.
- El render de resultados e impresiones es tolerante a respuestas repetidas para evitar el error de Svelte `each_key_duplicate`.

### Salas y duelos

- `POST /api/duels` crea una sala con nombre opcional y deck del creador opcional.
- El código de sala se genera en el servidor.
- `POST /api/duels/join` permite que un segundo jugador se una con el código e indique su deck opcional.
- Solo se puede unir un segundo jugador; intentos repetidos o salas ya activas responden con conflicto.
- Los participantes pueden consultar, actualizar y borrar sus duelos.
- Se persisten LP de ambos jugadores, turno, fase, estado, ganador, fecha de finalización y eventos.
- `POST /api/duels/{id}/events` almacena eventos asociados al duelo.

### Sincronización en tiempo real

- `/api/duels/{id}/ws` admite jugadores autenticados y espectadores; envía el rol al conectar y responde a `PING` con `PONG`.
- Los cambios de sala y eventos se difunden como `DUEL_UPDATED` y `DUEL_EVENT` a todos los clientes conectados.
- La pantalla `duel/[id]` conecta el WebSocket con el JWT de la sesión, actualiza el estado compartido y muestra el estado de conexión.
- El cliente envía pings periódicos y reintenta la conexión cuando se interrumpe.
- Los tests del backend verifican conexión de jugador/espectador, ping/pong y difusión de actualizaciones y eventos.

## Frontend disponible

| Ruta | Uso |
|---|---|
| `/login` | Inicio de sesión real. |
| `/register` | Registro y posterior autenticación. |
| `/` | Inicio autenticado con información del perfil, decks y duelos. |
| `/decks` | Constructor y administrador de decks conectado a la API. |
| `/duel/new` | Creación de sala o unión por código. |
| `/duel/demo` | Tablero visual de demostración, no conectado a un duelo persistido. |
| `/result/demo` | Pantalla visual de resultado de demostración. |

## Operación y configuración

- Docker requiere `SECRET_KEY` y `POSTGRES_PASSWORD` no vacíos en el `.env` de raíz.
- PostgreSQL se mantiene en la red de Docker y no se publica en el host.
- El backend y frontend publicados por Docker usan `http://localhost:8000` y `http://localhost:5173`.
- El CLI local genera una `SECRET_KEY` temporal si falta; esa clave invalida los JWT anteriores al reiniciar.
- Para evitar conflictos de puertos, se debe elegir Docker o el CLI/local como modo de ejecución activo.

## Validaciones realizadas

- Flujos de registro, login y consulta de perfil.
- Importación de cartas con metadatos y múltiples impresiones para un mismo código de set.
- CRUD de deck, secciones e impresión preferida.
- Creación de sala, unión del segundo jugador y conflictos de unión.
- Protección al eliminar decks utilizados por duelos.
- Actualización de LP y fase de duelo.
- WebSocket de duelo: conexión de jugador y espectador, ping/pong y difusión de cambios/eventos.
- Suite backend: `7 passed`.
- Compilación de SvelteKit.
- Build, health checks y respuesta HTTP del stack Docker.

Pruebas de backend:

```powershell
docker compose exec -T backend sh -c "PYTHONPATH=/app pytest -q"
```

## Próximo objetivo

Implementar el flujo móvil de cámara y escaneo: ruta adaptable, emparejamiento por QR, acceso a `getUserMedia`, calibración y confirmación de cartas detectadas.

# Duel Assistant — Progreso del proyecto

**Actualizado:** octubre de 2026
**Estado general:** Fases 1–8 implementadas funcionalmente. El escáner móvil está conectado al duelo; la validación física en Android/iOS y pruebas end-to-end siguen pendientes.

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
| Tablero real | Funcional | Ruta dinámica `duel/[id]` conecta el duelo persistido, registra copias de cartas por zona/posición y muestra estado y movimientos. |
| PWA y Caché | Funcional | Service Worker nativo con precarga en segundo plano, caché offline de cartas YGOProDeck y manifiesto instalable. |
| Tiempo real | Funcional | Snapshot versionado al conectar/reconectar; solo jugadores e invitados activos pueden leer; espectadores son solo lectura, revocables y pierden acceso al terminar. |
| Cámara y escaneo | Implementado; validación de hardware pendiente | Pairing QR temporal, sesión acotada, `/scanner`, cámara trasera, AprilTag `tagStandard41h12`, homografía, OCR como sugerencia y confirmación humana. |

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
- Solo los participantes y las cuentas invitadas pueden consultar salas; otros usuarios reciben `404`.
- Los participantes pueden invitar cuentas existentes como espectadores y revocar su acceso; las invitaciones revocadas se conservan y pueden reactivarse.
- Los espectadores solo pueden leer el duelo activo; no pueden modificarlo ni registrar eventos, y su WebSocket se cierra al revocarlos o finalizar la partida.
- Se persisten LP de ambos jugadores, turno, fase, estado, ganador, fecha de finalización y eventos.
- `POST /api/duels/{id}/events` almacena eventos asociados al duelo.
- `GET/POST /api/duels/{id}/cards` lista y registra copias físicas de cartas dentro de las zonas del duelo; `PUT /api/duels/{id}/cards/{card_id}` las mueve.
- Cada carta registrada debe estar en el deck asignado al jugador y respeta la cantidad configurada. Las posiciones ocupadas no se pueden duplicar.
- Las copias en deck, mano o boca abajo ocultan su identidad a otros jugadores y espectadores; el propietario puede verlas.
- Los movimientos crean eventos con actor, username, origen del dispositivo, carta, zona anterior y zona destino.
- La migración de arranque añade `duels.revision` con valor inicial `1` a bases existentes.

### Cámara compañera

- Un jugador genera un QR de un solo uso con vigencia de 5 minutos. El teléfono lo canjea por un token limitado a ese jugador/duelo, con máximo de 12 horas; se revoca al finalizar la partida.
- `/scanner` elimina el token de pairing de la URL tras canjearlo y conserva el token camera separado del JWT normal.
- La vista abre la cámara trasera en HTTPS y usa el worker/WASM local AprilTagJS para detectar `tagStandard41h12` IDs `0`, `1`, `2` y `4`.
- La calibración usa los centros de los cuatro tags para calcular homografía y dibujar la grilla. Si se pierde cámara o calibración, el botón de confirmar se deshabilita.
- Tesseract.js propone hasta cinco cartas del deck del jugador; el usuario puede corregir la sugerencia o seleccionar manualmente y confirmar antes del POST.
- El endpoint de cámara solo permite colocar cartas del deck asociado, registra `source_device=camera` y usa `client_action_id` para que reintentar no duplique una acción.
- El OCR inglés descarga sus datos de idioma en el primer uso; si falla, se conserva el selector manual del deck.
- Validación pendiente: nitidez/distancia de tags y flujo completo en los teléfonos físicos, incluyendo permisos de cámara y desconexión de red.

### Sincronización en tiempo real

- `/api/duels/{id}/ws` admite solo jugadores y espectadores invitados con cuenta activa; envía el rol al conectar y responde a `PING` con `PONG`.
- Los cambios de sala y eventos se difunden como `DUEL_UPDATED` y `DUEL_EVENT` a todos los clientes conectados.
- Cada conexión recibe `DUEL_STATE` con el snapshot persistido más reciente.
- Cada duelo tiene una revisión persistida que aumenta al cambiar estado, participantes o eventos; los broadcasts incluyen esa revisión.
- Los eventos REST y de tablero guardan actor, origen `web`/`camera`, carta e información de zona cuando aplica.
- La pantalla `duel/[id]` carga el estado por REST, conecta el WebSocket con el JWT de sesión y vuelve a hidratarse con el snapshot después de reconectar.
- El cliente descarta mensajes con una revisión ya aplicada, envía pings periódicos y reintenta la conexión.
- Los tests verifican snapshots iniciales, revisiones crecientes, ping/pong, difusión y recuperación del LP tras reconectar.
- Los tests cubren colocación/movimiento de copias, límites del deck, colisiones de slot y ocultación de cartas privadas en tablero e historial.
- `GET /api/duels/{id}` y el WebSocket niegan acceso a cuentas no invitadas. Las escrituras siguen siendo exclusivas de jugadores.
- `POST /api/duels/{id}/spectators` invita por username; `GET` lista invitaciones activas y `DELETE /{player_id}` revoca y cierra la conexión en vivo.
- La migración de arranque añade `duel_spectators.revoked_at` si la tabla ya existía.

## Frontend disponible

| Ruta | Uso |
|---|---|
| `/login` | Inicio de sesión real. |
| `/register` | Registro y posterior autenticación. |
| `/` | Inicio autenticado con información del perfil, decks y duelos. |
| `/decks` | Constructor y administrador de decks conectado a la API. |
| `/duel/new` | Creación de sala o unión por código. |
| `/duel/[id]` | Tablero persistido con sincronización WebSocket. |
| `/scanner` | Teléfono vinculado por QR; calibración AprilTag, captura OCR sugerida y confirmación. |
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
- Colocación/movimiento desde el deck asignado, validación de cantidad/slot y auditoría de actor, dispositivo y zonas.
- Ocultación de identidad de cartas del deck, mano o boca abajo en API, historial y snapshots WebSocket.
- WebSocket de duelo: conexión de jugador y espectador, ping/pong y difusión de cambios/eventos.
- Snapshot al conectar y reconectar, revisión persistida y rechazo de actualizaciones atrasadas.
- Pairing QR one-use, expiración, sesión de cámara limitada, source camera e idempotencia de capturas.
- Suite backend: `9 passed`.
- Compilación de SvelteKit.
- Build, health checks y respuesta HTTP del stack Docker.
- El build del frontend aún informa advertencias de accesibilidad en `/decks`; no son errores de compilación.

Pruebas de backend:

```powershell
docker compose exec -T backend sh -c "PYTHONPATH=/app pytest -q"
```

## Próximo objetivo

Siguiente bloque del MVP: probar manualmente HTTPS/cámara, tamaño y detección de marcadores, calibración, calidad OCR y recuperación ante desconexión en Android/iOS; después añadir pruebas end-to-end de PC y móvil.

# Duel Assistant

Aplicación web para asistir duelos físicos de Yu-Gi-Oh!. Actualmente permite gestionar cuentas, catálogo de cartas, impresiones físicas, decks y salas de duelo. Está construida con FastAPI, SvelteKit, PostgreSQL y Docker Compose.

La visión completa del producto —PC como tablero principal y celular como cámara vinculada— está documentada en [MVP_DUEL_ASSISTANT_ACTUALIZADO.md](docs/MVP_DUEL_ASSISTANT_ACTUALIZADO.md). El estado de implementación está en [progreso_proyecto.md](docs/progreso_proyecto.md), el plan técnico en [DUEL_ASSISTANT_PLAN_IMPLEMENTACION.md](docs/DUEL_ASSISTANT_PLAN_IMPLEMENTACION.md) y la integración PWA en [PWA_PLAN_INTEGRACION.md](docs/PWA_PLAN_INTEGRACION.md).

## Funcionalidad disponible

- Registro, inicio de sesión y cierre de sesión con JWT.
- Validación de sesión con `GET /api/auth/me`.
- Home con perfil, estadísticas, decks y duelos del usuario autenticado.
- Catálogo local de cartas e importación idempotente desde YGOProDeck.
- Búsquedas parciales de cartas mediante YGOProDeck (`fname`).
- Impresiones físicas por carta: set, código, idioma, rareza y precio.
- CRUD de decks con Main Deck, Extra Deck, Side Deck y una impresión preferida opcional.
- Creación de salas, selección de deck al crear o unirse y unión mediante código.
- Persistencia de LP, turno, fase, estado, ganador y eventos de duelo.
- Tablero persistido por duelo y sincronización WebSocket entre sesiones con snapshot versionado al conectar o reconectar.
- Registro y movimiento manual de copias del deck por zona, con historial de actor, dispositivo y zonas de origen/destino.
- El backend valida la sección/cantidad del deck, evita slots ocupados y protege la identidad de cartas privadas o boca abajo.
- Pairing de cámara por QR one-use, ruta `/scanner`, AprilTag `tagStandard41h12`, calibración geométrica del tapete (homografía con los 4 marcadores en las esquinas) y OCR del deck como sugerencia con confirmación antes de registrar.
- Salas privadas con espectadores invitados por cuenta: solo lectura, revocables y expirados al finalizar el duelo.
- PWA instalable con caché de recursos estáticos e imágenes de cartas; las APIs requieren conexión y no se cachean.
- Protección contra borrar un deck que está seleccionado en un duelo.

El flujo de cámara funciona como prototipo del MVP; falta validarlo físicamente en Android/iOS con el tapete impreso y realizar pruebas end-to-end entre PC y teléfono. El OCR solo propone una carta y siempre requiere confirmación humana. El tapete soportado es el de media mitad (fila de monstruos + fila de mágicas/trampas); para el tapete completo ajusta `MAT_ROWS` y `MAT_LAYOUT` en `frontend/src/lib/config/board.ts`.

## Ejecutar con Docker

1. Cree un archivo `.env` en la raíz con valores privados, aleatorios y no versionados:

   ```powershell
   $secret = py -c "import secrets; print(secrets.token_urlsafe(48))"
   $databasePassword = py -c "import secrets; print(secrets.token_urlsafe(32))"
   @"
   SECRET_KEY=$secret
   POSTGRES_PASSWORD=$databasePassword
   "@ | Set-Content .env
   ```

2. Construya e inicie los servicios:

   ```powershell
   docker compose up -d --build
   docker compose ps
   ```

3. Abra:

   - Frontend: `http://localhost:5173`
   - API y Swagger: `http://localhost:8000/docs`
   - Salud de la API: `http://localhost:8000/health`
   - HTTPS local con Caddy: `https://<ip-lan>` (ver [HTTPS_DESARROLLO_LOCAL.md](docs/HTTPS_DESARROLLO_LOCAL.md))
   - Marcadores del escáner: [docs/marcadores/INSTRUCCIONES.md](docs/marcadores/INSTRUCCIONES.md)

Docker publica PostgreSQL únicamente en el puerto `5433` del host para desarrollo; en producción/LAN debe convivir con la app detrás de Caddy.

> No use `docker compose down -v` salvo que quiera eliminar todos los datos de PostgreSQL del proyecto.

## Desarrollo local

### Backend

```powershell
Set-Location backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
# Configure un SECRET_KEY persistente y seguro en backend\.env.
uvicorn main:app --reload --port 8000
```

La configuración de `backend\.env` puede usar SQLite para desarrollo local. La API estará en `http://localhost:8000`.

Para probar la PWA y la cámara desde un teléfono, configura HTTPS local con Caddy y mkcert siguiendo [HTTPS_DESARROLLO_LOCAL.md](docs/HTTPS_DESARROLLO_LOCAL.md).

### Frontend

```powershell
Set-Location frontend
npm install
npm run dev -- --host 0.0.0.0 --port 5173
```

No ejecute a la vez Docker y el modo local si ambos intentan utilizar los puertos `8000` y `5173`.

## CLI de desarrollo

El panel `dev-cli` inicia el backend obligatorio, permite seleccionar el frontend y puede iniciar PostgreSQL con Docker.

```powershell
Set-Location dev-cli
pnpm install
pnpm dev
```

Si no existe `SECRET_KEY`, el CLI genera una clave temporal para esa ejecución. Al reiniciarlo, los JWT existentes dejan de ser válidos; use `backend\.env` para una clave persistente.

Para revisar el plan de arranque sin crear procesos:

```powershell
pnpm dev --dry
```

## Validación

Ejecute las pruebas del backend dentro del stack Docker:

```powershell
docker compose exec -T backend sh -c "PYTHONPATH=/app pytest -q"
```

Para compilar el frontend:

```powershell
Set-Location frontend
npm run build
```

La suite del backend verifica el snapshot WebSocket inicial, el incremento de revisiones y la recuperación del estado tras reconectar. Las pruebas end-to-end de navegador y el flujo completo entre dos dispositivos siguen pendientes.

# Duel Assistant

Base funcional para asistencia digital de duelos fisicos de Yu-Gi-Oh! con FastAPI y SvelteKit.

## Desarrollo local

### Backend

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

La API queda disponible en `http://localhost:8000/docs`. Por defecto usa SQLite para poder arrancar sin servicios externos.

Para crear el usuario administrador de desarrollo:

```powershell
cd backend
.\.venv\Scripts\python.exe seed.py
```

Credenciales: usuario `Mr_Ganzo`, contraseña `adminGanzo`.

### Frontend

```powershell
cd frontend
npm install
npm run dev -- --open
```

La interfaz queda disponible en `http://localhost:5173`.

PostgreSQL queda publicado para herramientas externas como DataGrip en `localhost:5433`.

## Docker

```powershell
docker compose up --build
```

Esto inicia PostgreSQL, backend y frontend.

## CLI de desarrollo

El panel interactivo vive en `dev-cli/` y muestra el banner DUEL. Permite levantar el backend obligatorio, elegir el frontend y arrancar PostgreSQL con Docker.

```powershell
cd dev-cli
pnpm install
pnpm dev
```

Para revisar el plan sin lanzar procesos:

```powershell
pnpm dev --dry
```

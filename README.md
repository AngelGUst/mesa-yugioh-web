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

## Docker

```powershell
$env:SECRET_KEY = py -c "import secrets; print(secrets.token_urlsafe(32))"
$env:POSTGRES_PASSWORD = py -c "import secrets; print(secrets.token_urlsafe(32))"
docker compose up --build
```

Esto inicia PostgreSQL, backend y frontend. `SECRET_KEY` y `POSTGRES_PASSWORD` son obligatorias: use valores diferentes, aleatorios y de al menos 32 caracteres. Puede copiar `.env.example` a `.env` para documentar la configuración, pero debe completar ambos valores antes de iniciar los contenedores. PostgreSQL no expone un puerto al host; backend se conecta mediante la red interna de Docker.

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

# DUEL ASSISTANT - Plan de Implementación Completo

**Proyecto:** Sistema de asistencia digital para duelos físicos de Yu-Gi-Oh!
**Fecha:** Septiembre 2026
**Presupuesto:** $0 MXN
**Stack:** FastAPI + SvelteKit + PostgreSQL + Docker

---

## TABLA DE CONTENIDOS

1. [Requisitos previos](#requisitos-previos)
2. [Estructura de carpetas](#estructura-de-carpetas)
3. [Fase 1: Preparación de entornos](#fase-1-preparación-de-entornos)
4. [Fase 2: Backend (FastAPI)](#fase-2-backend-fastapi)
5. [Fase 3: Frontend (SvelteKit)](#fase-3-frontend-sveltekit)
6. [Fase 4: Base de datos (PostgreSQL)](#fase-4-base-de-datos-postgresql)
7. [Fase 5: Docker](#fase-5-docker)
8. [Fase 6: Integración y pruebas](#fase-6-integración-y-pruebas)
9. [Cronograma de desarrollo](#cronograma-de-desarrollo)
10. [Troubleshooting](#troubleshooting)

---

## REQUISITOS PREVIOS

### Hardware

- **PC vieja:** Procesador mínimo 2 GHz, 4GB RAM
- **Celular:** Android o iOS con cámara trasera

### Software requerido

```bash
# Verifica que tengas estas herramientas instaladas:
python --version          # Python 3.10+
node --version            # Node.js 18+
npm --version             # npm 8+
docker --version          # Docker 20.10+
docker-compose --version  # Docker Compose 2.0+
git --version             # Git 2.30+
```

### Instalación de requisitos

**En Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install -y python3.10 python3-pip python3-venv
sudo apt install -y nodejs npm
sudo apt install -y docker.io docker-compose
sudo apt install -y git curl
```

**En Windows:**
- Descarga Python desde python.org
- Descarga Node.js desde nodejs.org
- Descarga Docker Desktop desde docker.com
- Descarga Git desde git-scm.com

**En macOS:**
```bash
brew install python3 node docker
```

---

## ESTRUCTURA DE CARPETAS

```
duel-assistant/
│
├── README.md
├── docker-compose.yml
├── .env
├── .gitignore
│
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── .env
│   ├── main.py
│   ├── config.py
│   │
│   ├── app/
│   │   ├── __init__.py
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── auth.py
│   │   │   ├── cards.py
│   │   │   ├── decks.py
│   │   │   ├── duels.py
│   │   │   ├── players.py
│   │   │   └── recognition.py
│   │   │
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── card.py
│   │   │   ├── deck.py
│   │   │   ├── duel.py
│   │   │   ├── player.py
│   │   │   └── event.py
│   │   │
│   │   ├── schemas/
│   │   │   ├── __init__.py
│   │   │   ├── card.py
│   │   │   ├── deck.py
│   │   │   ├── duel.py
│   │   │   └── player.py
│   │   │
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── auth_service.py
│   │   │   ├── card_service.py
│   │   │   ├── recognition_service.py
│   │   │   ├── ygoprodeck_service.py
│   │   │   └── cache_service.py
│   │   │
│   │   ├── game_engine/
│   │   │   ├── __init__.py
│   │   │   ├── state.py
│   │   │   ├── rules.py
│   │   │   ├── effects.py
│   │   │   ├── chains.py
│   │   │   ├── actions.py
│   │   │   └── validators.py
│   │   │
│   │   ├── websockets/
│   │   │   ├── __init__.py
│   │   │   ├── manager.py
│   │   │   └── handlers.py
│   │   │
│   │   ├── db/
│   │   │   ├── __init__.py
│   │   │   ├── database.py
│   │   │   └── session.py
│   │   │
│   │   └── utils/
│   │       ├── __init__.py
│   │       └── logger.py
│   │
│   ├── storage/
│   │   └── cards/  (Imágenes de cartas)
│   │
│   └── tests/
│       ├── __init__.py
│       ├── test_auth.py
│       ├── test_cards.py
│       └── test_game.py
│
├── frontend/
│   ├── Dockerfile
│   ├── package.json
│   ├── svelte.config.js
│   ├── vite.config.js
│   ├── tsconfig.json
│   │
│   ├── src/
│   │   ├── app.html
│   │   ├── app.css
│   │   ├── routes/
│   │   │   ├── +page.svelte          (Home)
│   │   │   ├── +layout.svelte
│   │   │   ├── login/
│   │   │   │   └── +page.svelte
│   │   │   ├── register/
│   │   │   │   └── +page.svelte
│   │   │   ├── profile/
│   │   │   │   └── +page.svelte
│   │   │   ├── decks/
│   │   │   │   ├── +page.svelte
│   │   │   │   └── [id]/
│   │   │   │       └── +page.svelte
│   │   │   ├── duel/
│   │   │   │   └── [id]/
│   │   │   │       └── +page.svelte
│   │   │   └── spectate/
│   │   │       └── [id]/
│   │   │           └── +page.svelte
│   │   │
│   │   ├── lib/
│   │   │   ├── components/
│   │   │   │   ├── Header.svelte
│   │   │   │   ├── Navigation.svelte
│   │   │   │   ├── DuelBoard.svelte
│   │   │   │   ├── Card.svelte
│   │   │   │   ├── CameraScanner.svelte
│   │   │   │   └── ChatPanel.svelte
│   │   │   │
│   │   │   ├── services/
│   │   │   │   ├── api.ts
│   │   │   │   ├── websocket.ts
│   │   │   │   ├── auth.ts
│   │   │   │   └── storage.ts
│   │   │   │
│   │   │   ├── stores/
│   │   │   │   ├── auth.ts
│   │   │   │   ├── duel.ts
│   │   │   │   ├── camera.ts
│   │   │   │   └── ui.ts
│   │   │   │
│   │   │   └── utils/
│   │   │       ├── helpers.ts
│   │   │       └── validators.ts
│   │   │
│   │   └── styles/
│   │       └── global.css
│   │
│   ├── static/
│   │   └── favicon.png
│   │
│   └── tests/
│       ├── auth.test.ts
│       └── components.test.ts
│
└── docs/
    ├── API.md
    ├── DATABASE.md
    └── ARCHITECTURE.md
```

---

## FASE 1: PREPARACIÓN DE ENTORNOS

### Paso 1.1: Crear carpeta del proyecto

```bash
mkdir duel-assistant
cd duel-assistant
git init
```

### Paso 1.2: Crear .gitignore

```bash
cat > .gitignore << 'EOF'
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
venv/
env/
*.egg-info/
.env
.env.local

# Node
node_modules/
npm-debug.log
yarn-error.log
build/
dist/

# IDE
.vscode/
.idea/
*.swp
*.swo
*~

# OS
.DS_Store
Thumbs.db

# Docker
.dockerignore

# Database
*.db
*.sqlite

# Logs
logs/
*.log
EOF
```

### Paso 1.3: Crear .env principal

```bash
cat > .env << 'EOF'
# ============= BACKEND =============
FASTAPI_ENV=development
FASTAPI_DEBUG=true
SECRET_KEY=tu-clave-secreta-cambiar-en-produccion
ALGORITHM=HS256

# ============= DATABASE =============
DB_HOST=postgres
DB_PORT=5432
DB_NAME=duel_assistant
DB_USER=duel_user
DB_PASSWORD=tu_contrasena_segura_123
DATABASE_URL=postgresql://duel_user:tu_contrasena_segura_123@postgres:5432/duel_assistant

# ============= FRONTEND =============
VITE_API_URL=http://localhost:8000
VITE_WS_URL=ws://localhost:8000

# ============= GENERAL =============
CORS_ORIGINS=http://localhost:3000,http://localhost:5173

# ============= YGOPRODECK API =============
YGOPRODECK_API_URL=https://ygoprodeck.com/api
EOF
```

### Paso 1.4: Crear estructura base

```bash
# Backend
mkdir -p backend/app/{api,models,schemas,services,game_engine,websockets,db,utils}
mkdir -p backend/storage/cards
mkdir -p backend/tests

# Frontend
mkdir -p frontend/src/{routes,lib/{components,services,stores,utils},styles}
mkdir -p frontend/static
mkdir -p frontend/tests

# Docs
mkdir -p docs
```

---

## FASE 2: BACKEND (FASTAPI)

### Paso 2.1: Crear entorno virtual y requirements

```bash
cd backend
python3 -m venv venv

# Activar entorno
source venv/bin/activate  # Linux/macOS
# o
venv\Scripts\activate  # Windows
```

### Paso 2.2: Crear requirements.txt

```bash
cat > requirements.txt << 'EOF'
# Web Framework
fastapi==0.104.1
uvicorn==0.24.0
python-multipart==0.0.6

# Database
sqlalchemy==2.0.23
psycopg2-binary==2.9.9
alembic==1.13.0

# Authentication
python-jose==3.3.0
passlib==1.7.4
python-dotenv==1.0.0

# Validation
pydantic==2.5.0
pydantic-settings==2.1.0

# CORS
fastapi-cors==0.0.6

# WebSockets
websockets==12.0
python-socketio==5.10.0

# Image Processing
opencv-python==4.8.1.78
pillow==10.1.0

# OCR
paddleocr==2.7.0.3

# API Client
requests==2.31.0
aiohttp==3.9.1

# Async
asyncio==3.4.3

# Logging
python-json-logger==2.0.7

# Testing
pytest==7.4.3
pytest-asyncio==0.21.1
httpx==0.25.2
EOF

pip install -r requirements.txt
```

### Paso 2.3: Crear main.py

```bash
cat > main.py << 'EOF'
"""
DUEL ASSISTANT - Backend Principal
FastAPI + SQLAlchemy + PostgreSQL
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import os
from dotenv import load_dotenv
import logging

# Cargar variables de entorno
load_dotenv()

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Importar rutas y configuración
from app.api import auth, cards, decks, duels, players
from app.db.database import init_db, engine, get_db
from app.websockets.manager import ConnectionManager

# Inicialización de base de datos
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Iniciando Duel Assistant...")
    init_db()
    logger.info("Base de datos inicializada")
    yield
    # Shutdown
    logger.info("Cerrando Duel Assistant...")

# Crear aplicación FastAPI
app = FastAPI(
    title="Duel Assistant API",
    description="Sistema de asistencia digital para duelos de Yu-Gi-Oh!",
    version="0.1.0",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Incluir routers
app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
app.include_router(cards.router, prefix="/api/cards", tags=["Cards"])
app.include_router(decks.router, prefix="/api/decks", tags=["Decks"])
app.include_router(duels.router, prefix="/api/duels", tags=["Duels"])
app.include_router(players.router, prefix="/api/players", tags=["Players"])

@app.get("/")
async def root():
    return {
        "message": "Duel Assistant API",
        "version": "0.1.0",
        "status": "online"
    }

@app.get("/health")
async def health():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
EOF
```

### Paso 2.4: Crear config.py

```bash
cat > config.py << 'EOF'
"""Configuración global de la aplicación"""

from pydantic_settings import BaseSettings
import os

class Settings(BaseSettings):
    # Base
    APP_NAME: str = "Duel Assistant"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = os.getenv("FASTAPI_DEBUG", "true").lower() == "true"
    
    # Database
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_PORT: int = int(os.getenv("DB_PORT", "5432"))
    DB_NAME: str = os.getenv("DB_NAME", "duel_assistant")
    DB_USER: str = os.getenv("DB_USER", "duel_user")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "password")
    
    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
    
    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", "tu-clave-secreta-cambiar-en-produccion")
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # API
    CORS_ORIGINS: list = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
    
    # External APIs
    YGOPRODECK_API_URL: str = os.getenv("YGOPRODECK_API_URL", "https://ygoprodeck.com/api")
    
    class Config:
        env_file = ".env"

settings = Settings()
EOF
```

### Paso 2.5: Crear base de datos (app/db/database.py)

```bash
cat > app/db/database.py << 'EOF'
"""Configuración de base de datos con SQLAlchemy"""

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import StaticPool
from config import settings
import logging

logger = logging.getLogger(__name__)

# URL de conexión
SQLALCHEMY_DATABASE_URL = settings.DATABASE_URL

# Crear engine
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={},
    poolclass=None,
)

# Crear SessionLocal
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base para modelos
Base = declarative_base()

def init_db():
    """Crear todas las tablas"""
    Base.metadata.create_all(bind=engine)
    logger.info("Tablas creadas exitosamente")

def get_db():
    """Dependencia para obtener sesión de BD"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
EOF
```

### Paso 2.6: Crear primer modelo (app/models/player.py)

```bash
cat > app/models/player.py << 'EOF'
"""Modelo de Jugador"""

from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from app.db.database import Base

class Player(Base):
    __tablename__ = "players"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True)
    email = Column(String(100), unique=True, index=True)
    password_hash = Column(String(255))
    lp_wins = Column(Integer, default=0)
    lp_losses = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    # Relaciones
    decks = relationship("Deck", back_populates="player")
    duels_as_p1 = relationship("Duel", foreign_keys="Duel.player1_id", back_populates="player1")
    duels_as_p2 = relationship("Duel", foreign_keys="Duel.player2_id", back_populates="player2")
EOF
```

### Paso 2.7: Crear esquemas (app/schemas/player.py)

```bash
cat > app/schemas/player.py << 'EOF'
"""Esquemas Pydantic para jugadores"""

from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime

class PlayerBase(BaseModel):
    username: str
    email: EmailStr

class PlayerCreate(PlayerBase):
    password: str

class PlayerLogin(BaseModel):
    username: str
    password: str

class Player(PlayerBase):
    id: int
    lp_wins: int
    lp_losses: int
    created_at: datetime
    is_active: bool
    
    class Config:
        from_attributes = True

class PlayerResponse(Player):
    pass

class Token(BaseModel):
    access_token: str
    token_type: str
EOF
```

### Paso 2.8: Crear router de autenticación (app/api/auth.py)

```bash
cat > app/api/auth.py << 'EOF'
"""Router de autenticación"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.models.player import Player
from app.schemas.player import PlayerCreate, PlayerLogin, Token, Player as PlayerSchema
from app.services.auth_service import AuthService
import logging

logger = logging.getLogger(__name__)
router = APIRouter()
auth_service = AuthService()

@router.post("/register", response_model=PlayerSchema)
async def register(player: PlayerCreate, db: Session = Depends(get_db)):
    """Registrar nuevo jugador"""
    
    # Verificar si el usuario ya existe
    existing_player = db.query(Player).filter(
        (Player.username == player.username) | (Player.email == player.email)
    ).first()
    
    if existing_player:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Usuario o email ya existe"
        )
    
    # Crear nuevo jugador
    password_hash = auth_service.get_password_hash(player.password)
    new_player = Player(
        username=player.username,
        email=player.email,
        password_hash=password_hash
    )
    
    db.add(new_player)
    db.commit()
    db.refresh(new_player)
    
    logger.info(f"Nuevo jugador registrado: {player.username}")
    return new_player

@router.post("/login", response_model=Token)
async def login(credentials: PlayerLogin, db: Session = Depends(get_db)):
    """Login de jugador"""
    
    player = db.query(Player).filter(Player.username == credentials.username).first()
    
    if not player or not auth_service.verify_password(credentials.password, player.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales inválidas"
        )
    
    access_token = auth_service.create_access_token(player.id)
    
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/me", response_model=PlayerSchema)
async def get_me(current_player: Player = Depends(auth_service.get_current_player)):
    """Obtener datos del jugador actual"""
    return current_player
EOF
```

### Paso 2.9: Crear servicio de autenticación (app/services/auth_service.py)

```bash
cat > app/services/auth_service.py << 'EOF'
"""Servicio de autenticación"""

from passlib.context import CryptContext
from datetime import datetime, timedelta
from jose import JWTError, jwt
from config import settings
from sqlalchemy.orm import Session
from app.db.database import get_db
from fastapi import Depends, HTTPException, status

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class AuthService:
    def get_password_hash(self, password: str) -> str:
        """Hashear contraseña"""
        return pwd_context.hash(password)
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verificar contraseña"""
        return pwd_context.verify(plain_password, hashed_password)
    
    def create_access_token(self, player_id: int, expires_delta: timedelta = None) -> str:
        """Crear token JWT"""
        if expires_delta is None:
            expires_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        
        expire = datetime.utcnow() + expires_delta
        to_encode = {"sub": str(player_id), "exp": expire}
        encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
        
        return encoded_jwt
    
    async def get_current_player(self, token: str = None, db: Session = Depends(get_db)):
        """Obtener jugador actual del token"""
        from app.models.player import Player
        from fastapi import Header
        
        if not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="No autorizado"
            )
        
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            player_id: str = payload.get("sub")
            if player_id is None:
                raise HTTPException(status_code=401, detail="Token inválido")
        except JWTError:
            raise HTTPException(status_code=401, detail="Token inválido")
        
        player = db.query(Player).filter(Player.id == int(player_id)).first()
        if player is None:
            raise HTTPException(status_code=404, detail="Jugador no encontrado")
        
        return player
EOF
```

### Paso 2.10: Crear otros routers (vacíos por ahora)

```bash
# Cards
cat > app/api/cards.py << 'EOF'
from fastapi import APIRouter

router = APIRouter()

@router.get("/")
async def get_cards():
    return {"message": "Cards endpoint"}
EOF

# Decks
cat > app/api/decks.py << 'EOF'
from fastapi import APIRouter

router = APIRouter()

@router.get("/")
async def get_decks():
    return {"message": "Decks endpoint"}
EOF

# Duels
cat > app/api/duels.py << 'EOF'
from fastapi import APIRouter

router = APIRouter()

@router.get("/")
async def get_duels():
    return {"message": "Duels endpoint"}
EOF

# Players
cat > app/api/players.py << 'EOF'
from fastapi import APIRouter

router = APIRouter()

@router.get("/")
async def get_players():
    return {"message": "Players endpoint"}
EOF

# Recognition
cat > app/api/recognition.py << 'EOF'
from fastapi import APIRouter

router = APIRouter()

@router.post("/scan")
async def scan_card():
    return {"message": "Recognition endpoint"}
EOF
```

### Paso 2.11: Crear __init__.py files

```bash
touch app/__init__.py
touch app/api/__init__.py
touch app/models/__init__.py
touch app/schemas/__init__.py
touch app/services/__init__.py
touch app/game_engine/__init__.py
touch app/websockets/__init__.py
touch app/db/__init__.py
touch app/utils/__init__.py
touch app/tests/__init__.py
```

### Paso 2.12: Prueba rápida del backend

```bash
# Aún en la carpeta backend/
python main.py
```

Debería mostrar:
```
INFO:     Uvicorn running on http://0.0.0.0:8000
```

Visita http://localhost:8000/docs para ver Swagger UI

---

## FASE 3: FRONTEND (SVELTEKIT)

### Paso 3.1: Crear proyecto SvelteKit

```bash
cd ..  # Vuelve a duel-assistant/

npm create svelte@latest frontend -- --template minimal --typescript --tailwindcss

cd frontend
npm install
```

### Paso 3.2: Instalar dependencias necesarias

```bash
npm install -D vite svelte
npm install axios pinia svelte-spa-router
npm install -D typescript
npm install -D tailwindcss postcss autoprefixer
npm install @testing-library/svelte -D vitest
```

### Paso 3.3: Configurar svelte.config.js

```bash
cat > svelte.config.js << 'EOF'
import adapter from '@sveltejs/adapter-auto';

export default {
  kit: {
    adapter: adapter(),
    alias: {
      $lib: 'src/lib',
      $components: 'src/lib/components',
      $stores: 'src/lib/stores',
      $services: 'src/lib/services'
    }
  }
};
EOF
```

### Paso 3.4: Configurar vite.config.js

```bash
cat > vite.config.js << 'EOF'
import { defineConfig } from 'vite';
import svelte from 'vite-plugin-svelte';

export default defineConfig({
  plugins: [svelte()],
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      }
    }
  }
});
EOF
```

### Paso 3.5: Crear estructura de componentes

```bash
# Crear componentes principales
mkdir -p src/lib/components
mkdir -p src/lib/services
mkdir -p src/lib/stores
mkdir -p src/lib/utils
mkdir -p src/routes

# Header
cat > src/lib/components/Header.svelte << 'EOF'
<header>
    <div class="navbar">
        <h1>Duel Assistant</h1>
        <nav>
            <a href="/">Home</a>
            <a href="/profile">Perfil</a>
            <a href="/decks">Decks</a>
        </nav>
    </div>
</header>

<style>
    header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 1rem 2rem;
    }
    
    .navbar {
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    
    h1 {
        margin: 0;
    }
    
    nav {
        display: flex;
        gap: 2rem;
    }
    
    a {
        color: white;
        text-decoration: none;
    }
    
    a:hover {
        text-decoration: underline;
    }
</style>
EOF

# DuelBoard
cat > src/lib/components/DuelBoard.svelte << 'EOF'
<div class="duel-board">
    <div class="player player-1">
        <h2>Jugador 1</h2>
        <div class="lp">6500 LP</div>
    </div>
    
    <div class="field">
        <div class="zone">Campo de juego</div>
    </div>
    
    <div class="player player-2">
        <h2>Jugador 2</h2>
        <div class="lp">7200 LP</div>
    </div>
</div>

<style>
    .duel-board {
        display: grid;
        grid-template-rows: 1fr 2fr 1fr;
        gap: 1rem;
        height: 100vh;
    }
    
    .player {
        background: #f0f0f0;
        padding: 1rem;
        border-radius: 8px;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    
    .lp {
        font-size: 2rem;
        font-weight: bold;
    }
    
    .field {
        background: #e0e0e0;
        padding: 2rem;
        border-radius: 8px;
        display: grid;
        grid-template-columns: repeat(5, 1fr);
        gap: 1rem;
    }
    
    .zone {
        background: white;
        border: 2px dashed #999;
        border-radius: 4px;
        min-height: 200px;
        display: flex;
        align-items: center;
        justify-content: center;
    }
</style>
EOF

# Card component
cat > src/lib/components/Card.svelte << 'EOF'
<script>
    export let card = {
        name: 'Unknown Card',
        atk: 0,
        def: 0,
        image: ''
    };
</script>

<div class="card">
    {#if card.image}
        <img src={card.image} alt={card.name} />
    {:else}
        <div class="placeholder">?</div>
    {/if}
    <p>{card.name}</p>
    <span>{card.atk}/{card.def}</span>
</div>

<style>
    .card {
        width: 100px;
        height: 140px;
        border: 1px solid #ccc;
        border-radius: 4px;
        background: white;
        cursor: pointer;
        transition: transform 0.2s;
    }
    
    .card:hover {
        transform: scale(1.05);
    }
    
    img {
        width: 100%;
        height: 100%;
        object-fit: cover;
    }
    
    .placeholder {
        display: flex;
        align-items: center;
        justify-content: center;
        width: 100%;
        height: 100%;
        background: #ddd;
        font-weight: bold;
    }
    
    p {
        margin: 0;
        font-size: 0.7rem;
        text-align: center;
    }
    
    span {
        display: block;
        font-size: 0.6rem;
        text-align: center;
    }
</style>
EOF
```

### Paso 3.6: Crear servicio API

```bash
cat > src/lib/services/api.ts << 'EOF'
import axios from 'axios';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const api = axios.create({
    baseURL: `${API_URL}/api`,
    headers: {
        'Content-Type': 'application/json'
    }
});

// Interceptor para agregar token
api.interceptors.request.use((config) => {
    const token = localStorage.getItem('token');
    if (token) {
        config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
});

// Auth
export const authAPI = {
    register: (data: any) => api.post('/auth/register', data),
    login: (data: any) => api.post('/auth/login', data),
    getMe: () => api.get('/auth/me')
};

// Players
export const playersAPI = {
    getAll: () => api.get('/players'),
    getById: (id: number) => api.get(`/players/${id}`)
};

// Cards
export const cardsAPI = {
    search: (query: string) => api.get(`/cards?search=${query}`),
    getById: (id: number) => api.get(`/cards/${id}`)
};

// Decks
export const decksAPI = {
    getAll: () => api.get('/decks'),
    create: (data: any) => api.post('/decks', data),
    update: (id: number, data: any) => api.put(`/decks/${id}`, data),
    delete: (id: number) => api.delete(`/decks/${id}`)
};

// Duels
export const duelsAPI = {
    getAll: () => api.get('/duels'),
    create: (data: any) => api.post('/duels', data),
    getById: (id: number) => api.get(`/duels/${id}`),
    update: (id: number, data: any) => api.put(`/duels/${id}`, data)
};

export default api;
EOF
```

### Paso 3.7: Crear stores (Pinia)

```bash
cat > src/lib/stores/auth.ts << 'EOF'
import { writable } from 'svelte/store';

export interface User {
    id: number;
    username: string;
    email: string;
    lp_wins: number;
    lp_losses: number;
}

interface AuthState {
    user: User | null;
    token: string | null;
    isLoading: boolean;
    error: string | null;
}

const initialState: AuthState = {
    user: null,
    token: localStorage.getItem('token'),
    isLoading: false,
    error: null
};

function createAuthStore() {
    const { subscribe, set, update } = writable<AuthState>(initialState);
    
    return {
        subscribe,
        
        setUser: (user: User) => update(state => ({ ...state, user })),
        setToken: (token: string) => {
            localStorage.setItem('token', token);
            update(state => ({ ...state, token }));
        },
        logout: () => {
            localStorage.removeItem('token');
            set(initialState);
        },
        setLoading: (isLoading: boolean) => update(state => ({ ...state, isLoading })),
        setError: (error: string | null) => update(state => ({ ...state, error }))
    };
}

export const auth = createAuthStore();
EOF

cat > src/lib/stores/duel.ts << 'EOF'
import { writable } from 'svelte/store';

export interface DuelState {
    duelId: string | null;
    player1LP: number;
    player2LP: number;
    currentPlayer: 1 | 2;
    currentPhase: string;
    turn: number;
    field: any[];
    hand: any[];
}

const initialState: DuelState = {
    duelId: null,
    player1LP: 8000,
    player2LP: 8000,
    currentPlayer: 1,
    currentPhase: 'DRAW_PHASE',
    turn: 1,
    field: [],
    hand: []
};

function createDuelStore() {
    const { subscribe, set, update } = writable<DuelState>(initialState);
    
    return {
        subscribe,
        
        setDuelId: (duelId: string) => update(state => ({ ...state, duelId })),
        updateLP: (player: 1 | 2, lp: number) => update(state => {
            if (player === 1) {
                return { ...state, player1LP: lp };
            } else {
                return { ...state, player2LP: lp };
            }
        }),
        updatePhase: (phase: string) => update(state => ({ ...state, currentPhase: phase })),
        nextTurn: () => update(state => ({
            ...state,
            turn: state.turn + 1,
            currentPlayer: state.currentPlayer === 1 ? 2 : 1
        })),
        reset: () => set(initialState)
    };
}

export const duel = createDuelStore();
EOF
```

### Paso 3.8: Crear páginas principales

```bash
# Home page
cat > src/routes/+page.svelte << 'EOF'
<script lang="ts">
    import Header from '$lib/components/Header.svelte';
    
    let duels = [
        { id: 1, opponent: 'player123', lp: 6500 },
        { id: 2, opponent: 'pro_duelist', lp: 4200 }
    ];
</script>

<Header />

<main>
    <h2>Tus duelos activos</h2>
    {#each duels as duel (duel.id)}
        <div class="duel-card">
            <p>vs {duel.opponent}</p>
            <p>LP: {duel.lp}</p>
            <a href="/duel/{duel.id}">Continuar</a>
        </div>
    {/each}
    
    <a href="/duel/new" class="btn-create">Crear nuevo duelo</a>
</main>

<style>
    main {
        padding: 2rem;
    }
    
    .duel-card {
        background: white;
        border: 1px solid #ddd;
        padding: 1rem;
        margin: 1rem 0;
        border-radius: 8px;
    }
    
    .btn-create {
        display: inline-block;
        background: #667eea;
        color: white;
        padding: 1rem 2rem;
        border-radius: 8px;
        text-decoration: none;
        margin-top: 2rem;
    }
</style>
EOF

# Layout
cat > src/routes/+layout.svelte << 'EOF'
<script>
    import '../styles/global.css';
</script>

<slot />
EOF
```

### Paso 3.9: Crear estilos globales

```bash
mkdir -p src/styles

cat > src/styles/global.css << 'EOF'
* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
    background: #f5f5f5;
    color: #333;
}

a {
    color: #667eea;
    text-decoration: none;
}

a:hover {
    text-decoration: underline;
}

button {
    cursor: pointer;
    border: none;
    padding: 0.5rem 1rem;
    border-radius: 4px;
    background: #667eea;
    color: white;
}

button:hover {
    background: #764ba2;
}

input, textarea, select {
    padding: 0.5rem;
    border: 1px solid #ddd;
    border-radius: 4px;
    font-family: inherit;
}

input:focus, textarea:focus, select:focus {
    outline: none;
    border-color: #667eea;
}
EOF
```

### Paso 3.10: Prueba del frontend

```bash
npm run dev
```

Visita http://localhost:5173

---

## FASE 4: BASE DE DATOS (POSTGRESQL)

### Paso 4.1: Instalar PostgreSQL (Si no usas Docker)

**Ubuntu/Debian:**
```bash
sudo apt install postgresql postgresql-contrib
sudo systemctl start postgresql
sudo -u postgres createuser duel_user -P
sudo -u postgres createdb -O duel_user duel_assistant
```

**Windows:**
Descargar desde postgresql.org e instalar

**macOS:**
```bash
brew install postgresql@15
brew services start postgresql@15
createuser duel_user -P
createdb -O duel_user duel_assistant
```

### Paso 4.2: Inicializar BD en el backend

En `backend/main.py` ya está la línea:
```python
init_db()
```

Que crea automáticamente las tablas

### Paso 4.3: Crear modelos de base de datos

Completar `backend/app/models/` con:
- card.py
- deck.py
- duel.py
- event.py

```bash
cat > backend/app/models/card.py << 'EOF'
from sqlalchemy import Column, Integer, String, Text, Float, DateTime
from datetime import datetime
from app.db.database import Base

class Card(Base):
    __tablename__ = "cards"
    
    id = Column(Integer, primary_key=True, index=True)
    ygoprodeck_id = Column(Integer, unique=True, index=True)
    name = Column(String(255), index=True)
    card_type = Column(String(50))
    description = Column(Text)
    atk = Column(Integer, nullable=True)
    def_ = Column(Integer, nullable=True)
    level = Column(Integer, nullable=True)
    race = Column(String(100), nullable=True)
    attribute = Column(String(20), nullable=True)
    image_url = Column(String(500))
    image_local_path = Column(String(255), nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
EOF

cat > backend/app/models/deck.py << 'EOF'
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Table
from sqlalchemy.orm import relationship
from datetime import datetime
from app.db.database import Base

# Tabla asociativa para Many-to-Many
deck_cards_association = Table(
    'deck_cards',
    Base.metadata,
    Column('deck_id', Integer, ForeignKey('decks.id')),
    Column('card_id', Integer, ForeignKey('cards.id')),
    Column('quantity', Integer, default=1)
)

class Deck(Base):
    __tablename__ = "decks"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255))
    player_id = Column(Integer, ForeignKey('players.id'))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relaciones
    player = relationship("Player", back_populates="decks")
    cards = relationship("Card", secondary=deck_cards_association)
EOF

cat > backend/app/models/duel.py << 'EOF'
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from app.db.database import Base

class Duel(Base):
    __tablename__ = "duels"
    
    id = Column(Integer, primary_key=True, index=True)
    duel_code = Column(String(20), unique=True, index=True)
    player1_id = Column(Integer, ForeignKey('players.id'))
    player2_id = Column(Integer, ForeignKey('players.id'), nullable=True)
    player1_lp = Column(Integer, default=8000)
    player2_lp = Column(Integer, default=8000)
    status = Column(String(20), default='waiting')  # waiting, active, finished
    turn = Column(Integer, default=1)
    current_phase = Column(String(50), default='DRAW_PHASE')
    current_player = Column(Integer, default=1)
    winner_id = Column(Integer, ForeignKey('players.id'), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    finished_at = Column(DateTime, nullable=True)
    
    # Relaciones
    player1 = relationship("Player", foreign_keys=[player1_id], back_populates="duels_as_p1")
    player2 = relationship("Player", foreign_keys=[player2_id], back_populates="duels_as_p2")
    events = relationship("DuelEvent", back_populates="duel")

class DuelEvent(Base):
    __tablename__ = "duel_events"
    
    id = Column(Integer, primary_key=True, index=True)
    duel_id = Column(Integer, ForeignKey('duels.id'))
    event_type = Column(String(50))
    payload = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relaciones
    duel = relationship("Duel", back_populates="events")
EOF
```

---

## FASE 5: DOCKER

### Paso 5.1: Crear Dockerfile del Backend

```bash
cat > backend/Dockerfile << 'EOF'
FROM python:3.11-slim

WORKDIR /app

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y \
    postgresql-client \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements
COPY requirements.txt .

# Instalar dependencias Python
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código
COPY . .

# Crear carpeta de storage
RUN mkdir -p storage/cards

# Exponer puerto
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health')" || exit 1

# Comando
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
EOF
```

### Paso 5.2: Crear Dockerfile del Frontend

```bash
cat > frontend/Dockerfile << 'EOF'
FROM node:18-alpine

WORKDIR /app

# Copiar package.json
COPY package*.json ./

# Instalar dependencias
RUN npm ci

# Copiar código
COPY . .

# Build
RUN npm run build

# Exponer puerto
EXPOSE 5173

# Comando
CMD ["npm", "run", "preview", "--", "--host"]
EOF
```

### Paso 5.3: Crear docker-compose.yml (Raíz del proyecto)

```bash
cat > docker-compose.yml << 'EOF'
version: '3.8'

services:
  # PostgreSQL Database
  postgres:
    image: postgres:15-alpine
    container_name: duel_db
    environment:
      POSTGRES_DB: ${DB_NAME}
      POSTGRES_USER: ${DB_USER}
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${DB_USER}"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - duel_network

  # Backend FastAPI
  backend:
    build: ./backend
    container_name: duel_backend
    command: uvicorn main:app --host 0.0.0.0 --port 8000 --reload
    ports:
      - "8000:8000"
    environment:
      FASTAPI_ENV: ${FASTAPI_ENV}
      FASTAPI_DEBUG: ${FASTAPI_DEBUG}
      SECRET_KEY: ${SECRET_KEY}
      ALGORITHM: ${ALGORITHM}
      DB_HOST: postgres
      DB_PORT: 5432
      DB_NAME: ${DB_NAME}
      DB_USER: ${DB_USER}
      DB_PASSWORD: ${DB_PASSWORD}
      DATABASE_URL: postgresql://${DB_USER}:${DB_PASSWORD}@postgres:5432/${DB_NAME}
      CORS_ORIGINS: ${CORS_ORIGINS}
    volumes:
      - ./backend:/app
      - storage_cards:/app/storage/cards
    depends_on:
      postgres:
        condition: service_healthy
    networks:
      - duel_network
    restart: unless-stopped

  # Frontend SvelteKit
  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    container_name: duel_frontend
    ports:
      - "5173:5173"
    environment:
      VITE_API_URL: http://backend:8000
      VITE_WS_URL: ws://backend:8000
    volumes:
      - ./frontend/src:/app/src
      - ./frontend/public:/app/public
      - /app/node_modules
    depends_on:
      - backend
    networks:
      - duel_network
    restart: unless-stopped

volumes:
  postgres_data:
    driver: local
  storage_cards:
    driver: local

networks:
  duel_network:
    driver: bridge
EOF
```

### Paso 5.4: Crear .dockerignore en ambas carpetas

```bash
# Backend
cat > backend/.dockerignore << 'EOF'
__pycache__
.venv
venv
.git
.gitignore
.env
*.pyc
.pytest_cache
EOF

# Frontend
cat > frontend/.dockerignore << 'EOF'
node_modules
.git
.gitignore
npm-debug.log
.env
.DS_Store
build
dist
EOF
```

### Paso 5.5: Comandos Docker

```bash
# Desde la raíz del proyecto (duel-assistant/)

# Construir y levantar todos los servicios
docker-compose up --build

# Levantar sin rebuild
docker-compose up

# En background
docker-compose up -d

# Ver logs
docker-compose logs -f

# Logs de un servicio específico
docker-compose logs -f backend
docker-compose logs -f frontend
docker-compose logs -f postgres

# Parar todos los servicios
docker-compose down

# Parar y eliminar volúmenes (resetear BD)
docker-compose down -v

# Ejecutar comando en contenedor
docker-compose exec backend python main.py shell

# Acceder a bash del backend
docker-compose exec backend bash

# Ver servicios corriendo
docker-compose ps
```

---

## FASE 6: INTEGRACIÓN Y PRUEBAS

### Paso 6.1: Actualizar cors en backend

En `backend/app/db/database.py`, el CORS ya está configurado.

Verificar en `.env`:
```
CORS_ORIGINS=http://localhost:3000,http://localhost:5173
```

### Paso 6.2: Conectar Frontend con Backend

En `frontend/src/lib/services/api.ts` ya está la conexión configurada.

Verificar `.env`:
```
VITE_API_URL=http://localhost:8000
```

### Paso 6.3: Test del flujo completo

1. Iniciar Docker:
```bash
cd duel-assistant/
docker-compose up --build
```

2. Abrir navegador:
```
Frontend: http://localhost:5173
Backend API: http://localhost:8000/docs
```

3. Probar registro:
```bash
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "email": "test@example.com",
    "password": "password123"
  }'
```

4. Probar login:
```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "password": "password123"
  }'
```

### Paso 6.4: Crear pruebas (tests)

Backend test:
```bash
cat > backend/tests/test_auth.py << 'EOF'
import pytest
from httpx import AsyncClient
from main import app

@pytest.mark.asyncio
async def test_register():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.post("/api/auth/register", json={
            "username": "testuser",
            "email": "test@example.com",
            "password": "password123"
        })
        assert response.status_code == 200

@pytest.mark.asyncio
async def test_login():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.post("/api/auth/login", json={
            "username": "testuser",
            "password": "password123"
        })
        assert response.status_code == 200
        assert "access_token" in response.json()
EOF

# Ejecutar tests
cd backend
pytest tests/
```

---

## CRONOGRAMA DE DESARROLLO

### Semana 1: Setup
- Día 1-2: Preparación de entornos y estructura
- Día 3-4: Setup de Docker
- Día 5: Testing básico

### Semana 2: Autenticación
- Día 1-2: Backend auth
- Día 3-4: Frontend login/register
- Día 5: Testing integrado

### Semana 3: Game State
- Día 1-2: Modelos de BD
- Día 3-4: Endpoints duelos
- Día 5: WebSockets básico

### Semana 4: Frontend duels
- Día 1-3: UI de duelo
- Día 4-5: Integración con backend

### Semana 5: Reconocimiento
- Día 1-2: OpenCV básico
- Día 3-4: OCR
- Día 5: Testing

### Semana 6: Motor de reglas
- Día 1-3: Lógica de reglas
- Día 4-5: Efectos básicos

### Semana 7-8: Pulir y expandir

---

## TROUBLESHOOTING

### Docker no inicia
```bash
# Ver errores
docker-compose logs

# Rebuildar
docker-compose down -v
docker-compose up --build
```

### Puerto en uso
```bash
# Cambiar puerto en docker-compose.yml
# O matar proceso:
lsof -i :8000
kill -9 <PID>
```

### BD no conecta
```bash
# Verificar variables en .env
# Esperar a que postgres esté listo
docker-compose logs postgres
```

### Frontend no carga
```bash
# Limpiar node_modules
rm -rf frontend/node_modules
rm frontend/package-lock.json
docker-compose down -v
docker-compose up --build
```

### Token inválido
```
Verificar SECRET_KEY en .env
Limpiar localStorage en navegador
```

---

## SIGUIENTE PASO

Después de completar estas 6 fases:

1. Completar endpoints de cartas (importación de YGOPRODeck)
2. Implementar sistema de decks
3. Agregar reconocimiento de cartas con cámara
4. Implementar motor de reglas completo
5. Agregar efectos de cartas
6. Sistema de cadenas (chains)
7. Deploy a producción

---

**¡Buena suerte con tu proyecto Duel Assistant!**
EOF
```

Ahora crearemos el archivo para descarga:
<function_calls>
<invoke name="present_files">
<parameter name="filepaths">["/mnt/user-data/outputs/DUEL_ASSISTANT_PLAN_IMPLEMENTACION.md"]
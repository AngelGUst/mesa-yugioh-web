import os
import secrets


os.environ.setdefault("SECRET_KEY", secrets.token_urlsafe(32))

"""Dependency d'authentification par clé API Bearer.

Si API_KEY n'est pas définie dans les settings, l'auth est désactivée (mode dev).
En production, définir API_KEY dans les variables d'environnement Railway.
"""
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings

_bearer = HTTPBearer(auto_error=False)


async def verify_api_key(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> None:
    if not settings.api_key:
        return  # auth désactivée si API_KEY non définie
    if not credentials or credentials.credentials != settings.api_key:
        raise HTTPException(status_code=401, detail="Unauthorized")

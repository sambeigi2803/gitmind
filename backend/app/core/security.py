# app/core/security.py
"""
Authentication for the FastAPI backend.

The Next.js frontend issues a JWT (Auth.js, JWT strategy) signed with
AUTH_SECRET. The backend verifies that same token - there is no second
login system. This keeps a single source of truth for identity while
letting the Python services authorize requests independently.

Also holds the AES-256-GCM decryption for GitHub tokens, mirroring
src/lib/encryption.ts on the frontend so both sides interoperate.
"""

import base64

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel

from app.core.config import settings

_IV_LENGTH = 12
_AUTH_TAG_LENGTH = 16

bearer_scheme = HTTPBearer(auto_error=False)


class CurrentUser(BaseModel):
    """Identity extracted from a verified JWT."""

    id: str
    username: str | None = None
    plan: str = "free"


def decrypt_token(payload: str) -> str:
    """
    Decrypt a GitHub access token stored by the frontend.

    Layout matches src/lib/encryption.ts: base64([iv][authTag][ciphertext]).
    Note that Python's AESGCM expects the tag appended to the ciphertext,
    so we reorder before decrypting.
    """
    raw = base64.b64decode(payload)
    iv = raw[:_IV_LENGTH]
    auth_tag = raw[_IV_LENGTH : _IV_LENGTH + _AUTH_TAG_LENGTH]
    ciphertext = raw[_IV_LENGTH + _AUTH_TAG_LENGTH :]

    aesgcm = AESGCM(bytes.fromhex(settings.ENCRYPTION_KEY))
    plaintext = aesgcm.decrypt(iv, ciphertext + auth_tag, None)
    return plaintext.decode("utf-8")


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> CurrentUser:
    """
    FastAPI dependency that verifies the bearer JWT and returns the caller.

    Raises 401 for a missing, malformed, expired, or badly-signed token.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        claims = jwt.decode(
            credentials.credentials,
            settings.AUTH_SECRET,
            algorithms=["HS256"],
        )
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    user_id = claims.get("id") or claims.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing subject claim",
        )

    return CurrentUser(
        id=user_id,
        username=claims.get("username"),
        plan=claims.get("plan", "free"),
    )

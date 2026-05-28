import base64
import binascii
import hashlib
import hmac
import json
import time
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings

from .schemas import AdminLoginRequest, AdminLoginResponse

TOKEN_TTL_SECONDS = 60 * 60 * 12
bearer_scheme = HTTPBearer(auto_error=False)


def _admin_password() -> str:
    return settings.admin_password.get_secret_value()


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64decode(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def _sign(payload: str) -> str:
    signature = hmac.new(
        _admin_password().encode("utf-8"),
        payload.encode("ascii"),
        hashlib.sha256,
    ).digest()
    return _b64encode(signature)


def _create_access_token() -> str:
    now = int(time.time())
    payload = _b64encode(
        json.dumps(
            {
                "sub": "admin",
                "iat": now,
                "exp": now + TOKEN_TTL_SECONDS,
            },
            separators=(",", ":"),
        ).encode("utf-8")
    )
    return f"{payload}.{_sign(payload)}"


def login_admin(payload: AdminLoginRequest) -> AdminLoginResponse:
    login_valid = hmac.compare_digest(payload.login, settings.admin_login)
    password_valid = hmac.compare_digest(payload.password, _admin_password())

    if not login_valid or not password_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный логин или пароль",
        )

    return AdminLoginResponse(access_token=_create_access_token())


async def verify_admin_token(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> None:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Требуется access_token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload, signature = credentials.credentials.split(".", 1)
        if not hmac.compare_digest(signature, _sign(payload)):
            raise ValueError

        data = json.loads(_b64decode(payload).decode("utf-8"))
        if not isinstance(data, dict):
            raise ValueError
        if data.get("sub") != "admin" or int(data.get("exp", 0)) < int(time.time()):
            raise ValueError
    except (binascii.Error, ValueError, json.JSONDecodeError, UnicodeDecodeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Некорректный access_token",
            headers={"WWW-Authenticate": "Bearer"},
        )


AdminTokenDep = Annotated[None, Depends(verify_admin_token)]

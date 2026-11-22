"""Minimal login: scrypt password hash + random session token in an httpOnly cookie.

Standard library only. The frontend proxies /api to this server, so the cookie is same-site.
"""

import hashlib
import hmac
import secrets

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import AuthSession, User

COOKIE = "lw_session"


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.scrypt(password.encode(), salt=salt.encode(), n=2**14, r=8, p=1).hex()
    return f"{salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    salt, digest = stored.split("$")
    check = hashlib.scrypt(password.encode(), salt=salt.encode(), n=2**14, r=8, p=1).hex()
    return hmac.compare_digest(check, digest)


def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get(COOKIE)
    session = db.get(AuthSession, token) if token else None
    if not session:
        raise HTTPException(status_code=401, detail="Not logged in")
    return db.get(User, session.user_id)

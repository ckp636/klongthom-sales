import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Annotated

import httpx
import jwt
from fastapi import Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models.personnel import Personnel
from app.repositories import personnel_repo

Database = Annotated[Session, Depends(get_db, scope="function")]
COOKIE_NAME = "klongthom_session"
_ISSUER = "klongthom-sales"
logger = logging.getLogger(__name__)


def _session_key() -> str:
    if len(settings.SESSION_SECRET) < 32:
        logger.error("SESSION_SECRET must contain at least 32 characters")
        raise HTTPException(503, "Session configuration is unavailable")
    if os.getenv("VERCEL") and not settings.SESSION_COOKIE_SECURE:
        logger.error("Secure session cookies are required on Vercel")
        raise HTTPException(503, "Session configuration is unavailable")
    return settings.SESSION_SECRET


def issue_session(response: Response, pid: int) -> None:
    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {"sub": str(pid), "iss": _ISSUER, "iat": now,
         "exp": now + timedelta(seconds=settings.SESSION_SECONDS)},
        _session_key(), algorithm="HS256",
    )
    response.set_cookie(
        COOKIE_NAME, token, max_age=settings.SESSION_SECONDS, httponly=True,
        secure=settings.SESSION_COOKIE_SECURE, samesite="lax", path="/api",
    )


def clear_session(response: Response) -> None:
    response.delete_cookie(
        COOKIE_NAME, path="/api", secure=settings.SESSION_COOKIE_SECURE,
        httponly=True, samesite="lax",
    )


def current_person(request: Request, db: Database) -> Personnel:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(401, "กรุณาเข้าสู่ระบบ")
    try:
        claims = jwt.decode(
            token, _session_key(), algorithms=["HS256"], issuer=_ISSUER,
            options={"require": ["sub", "exp", "iat", "iss"]},
        )
        pid = int(claims["sub"])
    except (jwt.InvalidTokenError, ValueError, TypeError):
        raise HTTPException(401, "หมดเวลาเข้าสู่ระบบ กรุณาเข้าสู่ระบบใหม่")
    person = personnel_repo.get_by_id(db, pid)
    if not person or not person.p7Status:
        raise HTTPException(401, "บัญชีนี้ไม่พร้อมใช้งาน")
    return person


CurrentPerson = Annotated[Personnel, Depends(current_person)]


def require_admin(person: CurrentPerson) -> Personnel:
    if person.p7Role != "admin":
        raise HTTPException(403, "ต้องเป็นผู้ดูแลระบบ")
    return person


AdminPerson = Annotated[Personnel, Depends(require_admin)]


def verify_line_token(id_token: str) -> str:
    if not settings.LINE_CHANNEL_ID:
        logger.error("LINE_CHANNEL_ID is not configured")
        raise HTTPException(503, "LINE login is not configured")
    try:
        result = httpx.post(
            "https://api.line.me/oauth2/v2.1/verify",
            data={"id_token": id_token, "client_id": settings.LINE_CHANNEL_ID},
            timeout=10,
        )
    except httpx.RequestError:
        logger.exception("LINE token verification request failed")
        raise HTTPException(503, "เชื่อมต่อ LINE ไม่ได้ กรุณาลองใหม่")
    if result.status_code in (400, 401):
        raise HTTPException(401, "LINE token ไม่ถูกต้องหรือหมดอายุ")
    if result.status_code != 200:
        logger.error("LINE verification returned HTTP %s", result.status_code)
        raise HTTPException(503, "LINE verification is unavailable")
    try:
        claims = result.json()
        if (claims["iss"] != "https://access.line.me"
                or claims["aud"] != settings.LINE_CHANNEL_ID
                or not isinstance(claims["sub"], str) or not claims["sub"]
                or float(claims["exp"]) <= datetime.now(timezone.utc).timestamp()):
            raise ValueError("Invalid verified LINE claims")
        return claims["sub"]
    except (ValueError, KeyError, TypeError):
        logger.warning("LINE verification returned invalid claims")
        raise HTTPException(401, "LINE token ไม่ถูกต้องหรือหมดอายุ")

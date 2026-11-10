import base64
import hashlib
import hmac
import logging
import os
import secrets

from app.core.config import settings
from fastapi import HTTPException

# ── passwords (stdlib scrypt, no extra dependency) ──────────────────────
_N, _R, _P = 2**14, 8, 1


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=_N, r=_R, p=_P, dklen=32)
    b64 = lambda b: base64.b64encode(b).decode()  # noqa: E731
    return f"scrypt${_N}${_R}${_P}${b64(salt)}${b64(digest)}"


def verify_password(password: str, stored: str | None) -> bool:
    try:
        algo, n, r, p, salt, digest = (stored or "").split("$")
        if algo != "scrypt":
            return False
        expected = base64.b64decode(digest)
        actual = hashlib.scrypt(password.encode(), salt=base64.b64decode(salt),
                                n=int(n), r=int(r), p=int(p), dklen=len(expected))
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


# ── store QR signatures ────────────────────────────────────────────────
# QR payload: ?shop=<s7Code>&sig=<qr_sig(s7Code, s7QrVer)>
# Bumping s7QrVer invalidates every QR printed for that store.

def qr_checks_enabled() -> bool:
    return bool(settings.QR_HMAC_SECRET)


def qr_sig(store_code: str, qr_ver: int) -> str:
    msg = f"{store_code}:{qr_ver}".encode()
    return hmac.new(settings.QR_HMAC_SECRET.encode(), msg, hashlib.sha256).hexdigest()[:32]


def verify_qr(store_code: str, qr_ver: int, sig: str | None) -> bool:
    if not qr_checks_enabled():
        if os.getenv("VERCEL"):
            logging.getLogger(__name__).error("QR_HMAC_SECRET is required on Vercel")
            raise HTTPException(503, "QR verification is not configured")
        return True
    return bool(sig) and hmac.compare_digest(qr_sig(store_code, qr_ver).encode(), sig.encode())

"""OAuth 2.1 bearer-token verification for the remote transport (SP8).

A minimal HS256 JWT verifier (stdlib only): validates signature + expiry and extracts the
tenant id (``sub``) and scopes. Scopes gate read vs write. For production, swap in your IdP's
JWKS / asymmetric verification — the claims shape keeps the server decoupled from the mechanism.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from dataclasses import dataclass


class TokenError(ValueError):
    pass


@dataclass(frozen=True)
class TokenClaims:
    tenant_id: str
    scopes: frozenset[str]

    def allows_write(self) -> bool:
        return "ads:write" in self.scopes or "write" in self.scopes


def _b64url_decode(segment: str) -> bytes:
    return base64.urlsafe_b64decode(segment + "=" * (-len(segment) % 4))


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def sign_hs256(payload: dict[str, object], secret: str) -> str:
    """Mint an HS256 JWT (for local issuance / tests)."""
    header = _b64url_encode(b'{"alg":"HS256","typ":"JWT"}')
    body = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode())
    signing_input = f"{header}.{body}".encode()
    sig = hmac.new(secret.encode(), signing_input, hashlib.sha256).digest()
    return f"{header}.{body}.{_b64url_encode(sig)}"


def verify_hs256(token: str, secret: str, now: int) -> TokenClaims:
    """Verify an HS256 bearer token; raise TokenError on any failure."""
    parts = token.split(".")
    if len(parts) != 3:
        raise TokenError("malformed token")
    header, body, signature = parts
    signing_input = f"{header}.{body}".encode()
    expected = hmac.new(secret.encode(), signing_input, hashlib.sha256).digest()
    if not hmac.compare_digest(expected, _b64url_decode(signature)):
        raise TokenError("bad signature")
    payload = json.loads(_b64url_decode(body))
    exp = payload.get("exp")
    if isinstance(exp, int) and now >= exp:
        raise TokenError("token expired")
    sub = payload.get("sub")
    if not isinstance(sub, str) or not sub:
        raise TokenError("missing sub (tenant)")
    scope_raw = payload.get("scope", "")
    scopes = frozenset(scope_raw.split()) if isinstance(scope_raw, str) else frozenset()
    return TokenClaims(tenant_id=sub, scopes=scopes)

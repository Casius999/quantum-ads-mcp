"""Local token issuer: an Ed25519 key pair and short-lived access tokens for self-hosting.

An agency that has no identity provider can still serve over HTTP with real OAuth 2.1 bearer
tokens: ``quantum-ads-mcp keygen`` writes a key pair, the server verifies with the public key,
and ``quantum-ads-mcp token --tenant acme`` mints a signed JWT (alg ``Ed25519``, RFC 9864) with
issuer, audience, expiry, tenant and scopes. With an IdP, skip this and point the server at its
JWKS instead (see ``core.remote.http``).
"""

from __future__ import annotations

import os
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from joserfc import jwk, jwt

LOCAL_ISSUER = "urn:quantum-ads:local-issuer"
ALGORITHM = "Ed25519"
PRIVATE_KEY_NAME = "issuer_ed25519.pem"
PUBLIC_KEY_NAME = "issuer_ed25519.pub.pem"


@dataclass(frozen=True)
class IssuerKeys:
    private_key: Path
    public_key: Path


def keygen(directory: Path) -> IssuerKeys:
    """Create the issuer key pair in ``directory``; refuse to overwrite an existing key."""
    directory.mkdir(parents=True, exist_ok=True)
    private_path, public_path = directory / PRIVATE_KEY_NAME, directory / PUBLIC_KEY_NAME
    if private_path.exists():
        raise FileExistsError(f"{private_path} already exists; refusing to overwrite it")
    key = Ed25519PrivateKey.generate()
    pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    fd = os.open(private_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as handle:
        handle.write(pem)
    public_path.write_bytes(
        key.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        )
    )
    return IssuerKeys(private_key=private_path, public_key=public_path)


def mint_token(
    private_key: Path,
    *,
    tenant: str,
    audience: str,
    scopes: list[str],
    subject: str | None = None,
    ttl_seconds: int = 3600,
    issuer: str = LOCAL_ISSUER,
    now: int | None = None,
) -> str:
    """Sign an access token for ``tenant`` valid for ``ttl_seconds``."""
    if ttl_seconds <= 0:
        raise ValueError("ttl_seconds must be positive")
    issued = int(time.time()) if now is None else now
    claims: dict[str, object] = {
        "iss": issuer,
        "sub": subject or tenant,
        "aud": audience,
        "iat": issued,
        "nbf": issued,
        "exp": issued + ttl_seconds,
        "jti": uuid.uuid4().hex,
        "tenant": tenant,
        "scope": " ".join(scopes),
    }
    key = jwk.import_key(private_key.read_bytes(), "OKP")
    return jwt.encode({"alg": ALGORITHM, "typ": "at+jwt"}, claims, key, algorithms=[ALGORITHM])

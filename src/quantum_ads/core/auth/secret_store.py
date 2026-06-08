"""Tenant credentials + secret stores.

SP0 ships a single-tenant env-backed store. A multi-tenant store (per-client OAuth +
Secret Manager) arrives in SP8. Credentials never appear in ``repr`` or logs.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol

_REQUIRED = (
    "GOOGLE_ADS_DEVELOPER_TOKEN",
    "GOOGLE_ADS_CLIENT_ID",
    "GOOGLE_ADS_CLIENT_SECRET",
    "GOOGLE_ADS_REFRESH_TOKEN",
)


@dataclass
class TenantCredentials:
    """Google Ads OAuth credentials for one tenant. Secret fields are redacted in repr."""

    developer_token: str
    client_id: str
    client_secret: str
    refresh_token: str
    login_customer_id: str | None = None
    use_proto_plus: bool = True

    def __repr__(self) -> str:  # never leak secrets in tracebacks/logs
        return f"TenantCredentials(login_customer_id={self.login_customer_id!r}, redacted=True)"

    def to_google_ads_dict(self) -> dict[str, object]:
        """Shape expected by ``GoogleAdsClient.load_from_dict``."""
        data: dict[str, object] = {
            "developer_token": self.developer_token,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": self.refresh_token,
            "use_proto_plus": self.use_proto_plus,
        }
        if self.login_customer_id:
            data["login_customer_id"] = self.login_customer_id
        return data


class SecretStore(Protocol):
    def get(self, tenant_id: str) -> TenantCredentials: ...


class EnvSecretStore:
    """Single-tenant store backed by an environment mapping."""

    def __init__(self, env: Mapping[str, str]):
        self._env = env

    def get(self, tenant_id: str) -> TenantCredentials:
        missing = [k for k in _REQUIRED if not self._env.get(k)]
        if missing:
            raise KeyError(f"missing required credential env vars: {missing}")
        use_proto_plus = str(self._env.get("GOOGLE_ADS_USE_PROTO_PLUS", "True")).lower() == "true"
        return TenantCredentials(
            developer_token=self._env["GOOGLE_ADS_DEVELOPER_TOKEN"],
            client_id=self._env["GOOGLE_ADS_CLIENT_ID"],
            client_secret=self._env["GOOGLE_ADS_CLIENT_SECRET"],
            refresh_token=self._env["GOOGLE_ADS_REFRESH_TOKEN"],
            login_customer_id=self._env.get("GOOGLE_ADS_LOGIN_CUSTOMER_ID") or None,
            use_proto_plus=use_proto_plus,
        )

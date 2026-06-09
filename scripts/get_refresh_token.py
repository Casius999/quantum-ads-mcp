"""Mint a broad-scope Google OAuth refresh token for live connector validation.

Opens your browser ONCE for consent, then writes GOOGLE_OAUTH_* to the gitignored .env.
Reuses the OAuth client_id/secret already in .env (GOOGLE_ADS_CLIENT_ID/SECRET or
GOOGLE_OAUTH_CLIENT_ID/SECRET). This is the one step only you can do (a human "Allow" click).

Run:  uv run python scripts/get_refresh_token.py
If your OAuth client is "Web" type, add  http://localhost:8765/  to its authorized redirect
URIs in Cloud Console first. "Desktop" clients need nothing. (Fallback: OAuth Playground.)
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]

# Everything the live connector suite can reach. adwords kept so the same token also runs Ads.
SCOPES = [
    "https://www.googleapis.com/auth/adwords",
    "https://www.googleapis.com/auth/analytics.readonly",
    "https://www.googleapis.com/auth/analytics.edit",
    "https://www.googleapis.com/auth/tagmanager.readonly",
    "https://www.googleapis.com/auth/content",
    "https://www.googleapis.com/auth/webmasters.readonly",
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/cloud-platform",
]


def _load_env() -> None:
    env = _ROOT / ".env"
    if not env.exists():
        return
    for raw in env.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def _write_env(client_id: str, client_secret: str, refresh_token: str) -> None:
    env = _ROOT / ".env"
    keep: list[str] = []
    drop = ("GOOGLE_OAUTH_CLIENT_ID=", "GOOGLE_OAUTH_CLIENT_SECRET=", "GOOGLE_OAUTH_REFRESH_TOKEN=")
    if env.exists():
        keep = [
            ln for ln in env.read_text(encoding="utf-8").splitlines() if not ln.startswith(drop)
        ]
    keep += [
        f"GOOGLE_OAUTH_CLIENT_ID={client_id}",
        f"GOOGLE_OAUTH_CLIENT_SECRET={client_secret}",
        f"GOOGLE_OAUTH_REFRESH_TOKEN={refresh_token}",
    ]
    env.write_text("\n".join(keep) + "\n", encoding="utf-8")


def main() -> None:
    _load_env()
    from google_auth_oauthlib.flow import InstalledAppFlow

    cid = os.environ.get("GOOGLE_OAUTH_CLIENT_ID") or os.environ.get("GOOGLE_ADS_CLIENT_ID")
    sec = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET") or os.environ.get("GOOGLE_ADS_CLIENT_SECRET")
    if not (cid and sec):
        sys.exit("Set GOOGLE_ADS_CLIENT_ID and GOOGLE_ADS_CLIENT_SECRET in .env first.")

    config = {
        "installed": {
            "client_id": cid,
            "client_secret": sec,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost:8765/"],
        }
    }
    flow = InstalledAppFlow.from_client_config(config, scopes=SCOPES)
    creds = flow.run_local_server(port=8765, access_type="offline", prompt="consent")
    if not creds.refresh_token:
        sys.exit("No refresh token returned. Revoke the prior grant and retry (prompt=consent).")

    _write_env(str(creds.client_id), str(creds.client_secret), str(creds.refresh_token))
    granted = " ".join(creds.scopes or SCOPES)
    print("OK — wrote GOOGLE_OAUTH_* to .env (gitignored).")
    print("Granted scopes:", granted)


if __name__ == "__main__":
    main()

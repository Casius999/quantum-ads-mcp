"""Mint a broad-scope Google OAuth refresh token for live connector validation.

With ``--ads``: mint only the Google Ads refresh token, for the GOOGLE_ADS_* client (the GCP
project that holds Google Ads API access), activating the GOOGLE_ADS_* lines in .env.

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
    # Google Ads
    "https://www.googleapis.com/auth/adwords",
    # GA4 (read + admin edit)
    "https://www.googleapis.com/auth/analytics.readonly",
    "https://www.googleapis.com/auth/analytics.edit",
    # Tag Manager (read + edit/publish)
    "https://www.googleapis.com/auth/tagmanager.readonly",
    "https://www.googleapis.com/auth/tagmanager.edit.containers",
    # Merchant / Shopping content
    "https://www.googleapis.com/auth/content",
    # Search Console
    "https://www.googleapis.com/auth/webmasters.readonly",
    # YouTube Data + Analytics/Reporting
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
    # Display & Video 360
    "https://www.googleapis.com/auth/display-video",
    # Campaign Manager 360
    "https://www.googleapis.com/auth/dfatrafficking",
    "https://www.googleapis.com/auth/dfareporting",
    "https://www.googleapis.com/auth/ddmconversions",
    # Search Ads 360
    "https://www.googleapis.com/auth/doubleclicksearch",
    # Google Business Profile
    "https://www.googleapis.com/auth/business.manage",
    # Ads Data Hub
    "https://www.googleapis.com/auth/adsdatahub",
    # GCP umbrella: BigQuery, Vertex, Translation, Natural Language, reCAPTCHA, Service Usage
    "https://www.googleapis.com/auth/cloud-platform",
]
# NOTE: Workspace Admin SDK scopes are intentionally omitted — a personal @gmail account cannot
# grant them (they require a Google Workspace org). Looker is not a Google-OAuth surface (it uses
# its own API3 client_id/secret against a Looker instance), so it is not represented here either.


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


ADS_SCOPES = ["https://www.googleapis.com/auth/adwords"]
_ADS_KEYS = (
    "GOOGLE_ADS_DEVELOPER_TOKEN",
    "GOOGLE_ADS_CLIENT_ID",
    "GOOGLE_ADS_CLIENT_SECRET",
    "GOOGLE_ADS_LOGIN_CUSTOMER_ID",
)


def _ads_values() -> dict[str, str]:
    """GOOGLE_ADS_* values from .env, including lines left commented out."""
    values: dict[str, str] = {}
    env = _ROOT / ".env"
    for raw in env.read_text(encoding="utf-8").splitlines() if env.exists() else []:
        body = raw.strip().lstrip("#").strip()
        key, sep, value = body.partition("=")
        if sep and key.strip() in _ADS_KEYS:
            values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _write_ads_env(values: dict[str, str], refresh_token: str) -> None:
    """Activate the GOOGLE_ADS_* lines and set GOOGLE_ADS_REFRESH_TOKEN; leave everything else."""
    env = _ROOT / ".env"
    managed = (*_ADS_KEYS, "GOOGLE_ADS_REFRESH_TOKEN")
    keep = [
        ln
        for ln in env.read_text(encoding="utf-8").splitlines()
        if ln.strip().lstrip("#").strip().partition("=")[0].strip() not in managed
    ]
    keep += [f"{k}={values[k]}" for k in _ADS_KEYS if values.get(k)]
    keep.append(f"GOOGLE_ADS_REFRESH_TOKEN={refresh_token}")
    env.write_text("\n".join(keep) + "\n", encoding="utf-8")


def _flow(cid: str, sec: str, scopes: list[str]):  # type: ignore[no-untyped-def]
    from google_auth_oauthlib.flow import InstalledAppFlow

    config = {
        "installed": {
            "client_id": cid,
            "client_secret": sec,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost:8765/"],
        }
    }
    return InstalledAppFlow.from_client_config(config, scopes=scopes)


def main_ads() -> None:
    """--ads: refresh token for the Google Ads client whose GCP project holds API access."""
    values = _ads_values()
    if not (values.get("GOOGLE_ADS_CLIENT_ID") and values.get("GOOGLE_ADS_CLIENT_SECRET")):
        sys.exit("GOOGLE_ADS_CLIENT_ID / GOOGLE_ADS_CLIENT_SECRET not found in .env.")
    flow = _flow(values["GOOGLE_ADS_CLIENT_ID"], values["GOOGLE_ADS_CLIENT_SECRET"], ADS_SCOPES)
    creds = flow.run_local_server(port=8765, access_type="offline", prompt="consent")
    if not creds.refresh_token:
        sys.exit("No refresh token returned. Revoke the prior grant and retry.")
    _write_ads_env(values, str(creds.refresh_token))
    print("OK — GOOGLE_ADS_* active in .env (gitignored); GOOGLE_OAUTH_* untouched.")


def main() -> None:
    if "--ads" in sys.argv[1:]:
        main_ads()
        return
    _load_env()

    cid = os.environ.get("GOOGLE_OAUTH_CLIENT_ID") or os.environ.get("GOOGLE_ADS_CLIENT_ID")
    sec = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET") or os.environ.get("GOOGLE_ADS_CLIENT_SECRET")
    if not (cid and sec):
        sys.exit("Set GOOGLE_ADS_CLIENT_ID and GOOGLE_ADS_CLIENT_SECRET in .env first.")

    flow = _flow(cid, sec, SCOPES)
    creds = flow.run_local_server(port=8765, access_type="offline", prompt="consent")
    if not creds.refresh_token:
        sys.exit("No refresh token returned. Revoke the prior grant and retry (prompt=consent).")

    _write_env(str(creds.client_id), str(creds.client_secret), str(creds.refresh_token))
    granted = " ".join(creds.scopes or SCOPES)
    print("OK — wrote GOOGLE_OAUTH_* to .env (gitignored).")
    print("Granted scopes:", granted)


if __name__ == "__main__":
    main()

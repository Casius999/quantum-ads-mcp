"""Exact structural delta between two Google Ads API versions, computed from the installed SDK.

The curated ``deltas_2026`` catalog explains *why* things changed; this module answers *what*
changed, exhaustively and version-exactly: resources, services, enums and common types added or
removed between two versions, read straight from the protobuf packages ``google-ads`` ships. It
needs no developer token and no network, so an agent can plan an API upgrade before touching an
account.
"""

from __future__ import annotations

import importlib
import pkgutil

_KINDS: dict[str, str] = {
    "resources": "resources.types",
    "enums": "enums.types",
    "common": "common.types",
    "services": "services.services",
}


def _members(version: str, package: str) -> set[str]:
    module = importlib.import_module(f"google.ads.googleads.{version}.{package}")
    return {info.name for info in pkgutil.iter_modules(module.__path__)}


def supported_versions() -> list[str]:
    """API versions the installed google-ads SDK can talk to, oldest first."""
    root = importlib.import_module("google.ads.googleads")
    found = [
        info.name
        for info in pkgutil.iter_modules(root.__path__)
        if info.name.startswith("v") and info.name[1:].isdigit()
    ]
    return sorted(found, key=lambda name: int(name[1:]))


def compute_version_delta(from_version: str, to_version: str) -> dict[str, object]:
    """Return what ``to_version`` adds and removes relative to ``from_version``."""
    available = supported_versions()
    missing = [v for v in (from_version, to_version) if v not in available]
    if missing:
        return {
            "error": {
                "code": "UNSUPPORTED_VERSION",
                "message": f"not in the installed SDK: {missing}; available: {available}",
            }
        }
    delta: dict[str, object] = {"from": from_version, "to": to_version}
    for kind, package in _KINDS.items():
        old, new = _members(from_version, package), _members(to_version, package)
        delta[kind] = {"added": sorted(new - old), "removed": sorted(old - new)}
    return delta

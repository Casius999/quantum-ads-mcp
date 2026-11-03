"""Distribution metadata stays in step with the package (registry entry, MCP bundle, image)."""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VERSION = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]


def test_registry_entry_matches_the_package():
    server = json.loads((ROOT / "server.json").read_text(encoding="utf-8"))
    assert server["version"] == server["packages"][0]["version"] == VERSION
    assert server["packages"][0]["identifier"] == "quantum-ads-mcp"
    assert len(server["description"]) <= 100  # registry schema limit
    # PyPI ownership proof the MCP Registry looks for in the package description.
    assert f"mcp-name: {server['name']}" in (ROOT / "README.md").read_text(encoding="utf-8")


def test_bundle_manifest_matches_the_package_and_wires_every_setting():
    manifest = json.loads((ROOT / "packaging/mcpb/manifest.json").read_text(encoding="utf-8"))
    assert manifest["version"] == VERSION and manifest["server"]["type"] == "uv"
    env = manifest["server"]["mcp_config"]["env"]
    referenced = {v.removeprefix("${user_config.").removesuffix("}") for v in env.values()}
    assert referenced == set(manifest["user_config"])
    secrets = {k for k, v in manifest["user_config"].items() if v.get("sensitive")}
    assert secrets == {"developer_token", "client_secret", "refresh_token"}


def test_release_please_bumps_every_versioned_file():
    config = json.loads((ROOT / "release-please-config.json").read_text(encoding="utf-8"))
    paths = {f["path"] for f in config["packages"]["."]["extra-files"]}
    assert paths == {"server.json", "packaging/mcpb/manifest.json"}

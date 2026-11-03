#!/usr/bin/env sh
# Assemble and pack the one-click MCP bundle (.mcpb): manifest + entry point + the uv project.
set -eu
root=$(cd "$(dirname "$0")/../.." && pwd)
out=${1:-"$root/dist"}
stage=$(mktemp -d)
cp "$root/packaging/mcpb/manifest.json" "$root/packaging/mcpb/server.py" "$stage/"
cp "$root/pyproject.toml" "$root/uv.lock" "$root/.python-version" "$root/README.md" "$root/LICENSE" "$stage/"
cp -R "$root/src" "$stage/src"
printf '.venv\nserver/lib\n__pycache__\n' > "$stage/.mcpbignore"
mkdir -p "$out"
npx -y @anthropic-ai/mcpb@2.1.2 validate "$stage/manifest.json"
npx -y @anthropic-ai/mcpb@2.1.2 pack "$stage" "$out/quantum-ads-mcp.mcpb"

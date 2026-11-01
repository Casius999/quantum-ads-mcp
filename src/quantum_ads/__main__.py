"""Command-line entrypoint: serve over stdio (default) or Streamable HTTP, manage local tokens.

quantum-ads-mcp                         stdio MCP server (what MCP clients launch)
quantum-ads-mcp serve --transport http  OAuth 2.1-protected multi-tenant HTTP server
quantum-ads-mcp keygen                  create the local token issuer's Ed25519 key pair
quantum-ads-mcp token --tenant acme     mint an access token signed by the local issuer
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from .backends import build_backends
from .connectors.google_ads.sdk import default_mutate_factory, default_stream_factory
from .core.observability.recorder import CallRecorder
from .core.observability.tracing import configure_tracing
from .core.remote.http import (
    RemoteConfig,
    build_auth,
    default_audience,
    remote_config_from_env,
    remote_middleware,
)
from .core.remote.issuer import PRIVATE_KEY_NAME, keygen, mint_token
from .core.remote.secrets import load_tenants
from .core.tenancy import SCOPE_READ
from .server import DEFAULT_CONNECTORS, AssembledServer, build_server

# The shipped server keeps its signed audit ledger across restarts unless told otherwise.
DEFAULT_AUDIT_DIR = Path.home() / ".quantum-ads" / "audit"
DEFAULT_ISSUER_DIR = Path.home() / ".quantum-ads" / "issuer"


def runtime_env(environ: Mapping[str, str]) -> dict[str, str]:
    """Process env, defaulting QUANTUM_ADS_AUDIT_DIR (set it empty to keep the ledger in memory)."""
    return {"QUANTUM_ADS_AUDIT_DIR": str(DEFAULT_AUDIT_DIR), **environ}


def call_log_sink(env: Mapping[str, str]) -> Callable[[str], None] | None:
    """One JSON line per tool call on stderr (stdout carries the stdio protocol), unless disabled."""
    if (env.get("QUANTUM_ADS_LOG_CALLS") or "true").lower() == "false":
        return None
    logger = logging.getLogger("quantum_ads.calls")
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    return logger.info


def assemble(env: Mapping[str, str], remote: RemoteConfig | None = None) -> AssembledServer:
    """The production server: every backend wired, observed; auth + tenancy when remote."""
    configure_tracing(env)
    common: dict[str, Any] = {
        "env": env,
        "stream_factory": default_stream_factory,
        "connectors": DEFAULT_CONNECTORS,
        "mutate_factory": default_mutate_factory,
        "backends": build_backends(env),
        "recorder": CallRecorder(sink=call_log_sink(env)),
    }
    if remote is None:
        return build_server(**common)
    tenants = load_tenants(env, build_backends)
    return build_server(
        **common,
        auth=build_auth(remote),
        middleware=remote_middleware(remote, tenants),
        tenants=tenants,
    )


def _serve(args: argparse.Namespace, env: dict[str, str]) -> None:
    if args.transport == "stdio":
        assemble(env).app.run()
        return
    remote = remote_config_from_env(env, host=args.host, port=args.port)
    assemble(env, remote).app.run(
        transport="http",
        host=remote.host,
        port=remote.port,
        path=remote.path,
        allowed_hosts=list(remote.allowed_hosts) or None,
        allowed_origins=list(remote.allowed_origins) or None,
    )


def _keygen(args: argparse.Namespace) -> None:
    keys = keygen(Path(args.dir).expanduser())
    print(f"private key: {keys.private_key}  (keep secret; used by `quantum-ads-mcp token`)")
    print(f"public key:  {keys.public_key}")
    print(f"set on the server: QUANTUM_ADS_OAUTH_PUBLIC_KEY_FILE={keys.public_key}")


def _token(args: argparse.Namespace, env: dict[str, str]) -> None:
    print(
        mint_token(
            Path(args.key).expanduser(),
            tenant=args.tenant,
            subject=args.subject,
            scopes=args.scope.split(),
            audience=args.audience or default_audience(env),
            ttl_seconds=args.ttl,
        )
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="quantum-ads-mcp", description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command")
    serve = sub.add_parser("serve", help="run the MCP server")
    serve.add_argument(
        "--transport",
        choices=["stdio", "http"],
        default=os.environ.get("QUANTUM_ADS_TRANSPORT", "stdio"),
    )
    serve.add_argument("--host", help="HTTP bind host (default QUANTUM_ADS_HTTP_HOST or 127.0.0.1)")
    serve.add_argument("--port", type=int, help="HTTP port (default QUANTUM_ADS_HTTP_PORT or 8000)")
    gen = sub.add_parser("keygen", help="create the local token issuer key pair")
    gen.add_argument("--dir", default=str(DEFAULT_ISSUER_DIR))
    tok = sub.add_parser("token", help="mint an access token with the local issuer key")
    tok.add_argument("--tenant", required=True)
    tok.add_argument(
        "--scope", default=SCOPE_READ, help='space-separated, e.g. "ads:read ads:write"'
    )
    tok.add_argument("--subject", help="token subject (default: the tenant id)")
    tok.add_argument("--ttl", type=int, default=3600, help="lifetime in seconds")
    tok.add_argument("--audience", help="default: QUANTUM_ADS_OAUTH_AUDIENCE or the resource URL")
    tok.add_argument("--key", default=str(DEFAULT_ISSUER_DIR / PRIVATE_KEY_NAME))
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    args = _parser().parse_args(sys.argv[1:] if argv is None else argv)
    env = runtime_env(os.environ)
    if args.command == "keygen":
        _keygen(args)
    elif args.command == "token":
        _token(args, env)
    else:
        if args.command is None:
            args.transport = env.get("QUANTUM_ADS_TRANSPORT", "stdio")
            args.host = args.port = None
        _serve(args, env)


if __name__ == "__main__":
    main()

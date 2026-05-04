#!/usr/bin/env python3
"""
GRC Proxy - Standalone HTTP proxy for LLM request interception (Claude Code).

This is a SEPARATE distribution mode from the SDK package (zgrc.init()).
It runs as a standalone proxy server using mitmproxy to intercept HTTP/HTTPS
traffic and enforce GRC policies on LLM requests without requiring code changes.

**PRIMARY USE CASE: LLM cost tracking and quota enforcement for Claude Code CLI running in terminal**

DISTRIBUTION:
    - Built with PyInstaller into standalone executables
    - No Python installation required for end users
    - Runs independently of the zgrc Python package

USAGE:
    As executable: zgrc-proxy --api-key=grc_xxx [--port 8080] [--verbose]

ARCHITECTURE:
    - mitmproxy handles HTTPS interception and certificate management
    - Certificates auto-generated in ~/.mitmproxy/ on first run
    - ProxyAddon orchestrates request/response lifecycle
    - RequestHandler validates quota BEFORE LLM requests
    - ResponseHandler extracts token usage AFTER responses

CLIENT SETUP (Claude Code):
    Set these environment variables before running LLM applications:
    - HTTPS_PROXY=http://localhost:PORT or where the Executable is deployed!
    - NODE_EXTRA_CA_CERTS=~/.mitmproxy/mitmproxy-ca-cert.pem (Node.js only)

TARGET:
    - AWS Bedrock requests (specifically for Claude models)
    - **Designed specifically for tracking Claude Code CLI usage and costs in terminal sessions**
"""

# CRITICAL: Disable logfire before any imports that use Pydantic
# This prevents "OSError: could not get source code" in PyInstaller executables
import os

os.environ["LOGFIRE_IGNORE_NO_CONFIG"] = "1"
os.environ["LOGFIRE_SEND_TO_LOGFIRE"] = "false"

import argparse
import asyncio
import logging
import sys

from mitmproxy import options
from mitmproxy.tools import dump

from zgrc.proxy import ProxyAddon
from zgrc.proxy.script import Manager, Process
from zgrc.auth import AuthToken
from zgrc.context import auth_ctx

logger = logging.getLogger(__name__)


async def run_proxy(api_key, port, verbose):
    """Run proxy server"""
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="[%(asctime)s] [%(name)s] %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    auth = AuthToken.decode(api_key)
    auth_ctx.set(auth)

    addon = ProxyAddon()
    logger.info(f"GRC Proxy running on PORT:{port}")

    opts = options.Options(listen_host="127.0.0.1", listen_port=port)
    master = dump.DumpMaster(opts, with_termlog=False, with_dumper=False)
    master.addons.add(addon)
    await master.run()


def main():
    parser = argparse.ArgumentParser(prog="z-grc-proxy", description="GRC Proxy Server")
    parser.add_argument("--api-key", help="GRC API key")
    parser.add_argument("--port", type=int, help="Proxy port (default: auto-detect)")
    parser.add_argument("--verbose", action="store_true", help="Verbose logging")
    parser.add_argument(
        "-d",
        "--background",
        action="store_true",
        help="Run in background (use with eval)",
    )
    parser.add_argument("--status", action="store_true", help="Show active sessions")
    parser.add_argument("--kill-all", action="store_true", help="Kill all servers")
    parser.add_argument("--detach", action="store_true", help=argparse.SUPPRESS)

    args = parser.parse_args()
    mgr = Manager()

    if args.detach:
        if not args.api_key or not args.port:
            return 1
        asyncio.run(run_proxy(args.api_key, args.port, args.verbose))
        return 0

    if args.status:
        sessions = mgr.status()
        if not sessions:
            print("No active servers", file=sys.stderr)
            return 0
        for i, s in enumerate(sessions, 1):
            print(f"[{i}] Port:{s['port']} PID:{s['pid']}", file=sys.stderr)
        return 0

    if args.kill_all:
        print(f"Killed {mgr.kill_all()} server(s)", file=sys.stderr)
        return 0

    if not args.api_key:
        parser.error("--api-key required")

    # Background mode: spawn detached + output env vars
    if args.background:
        try:
            port, pid, is_new = mgr.start(args.api_key, args.port, args.verbose)
            print(
                f"# {'Started' if is_new else 'Reusing'} port {port}", file=sys.stderr
            )
            # Where needed to store the creds in current terminal session, so getting the printing the creds and using
            # eval to run the command in terminal.
            for k, v in mgr.env(port).items():
                if sys.platform == "win32":
                    # PowerShell syntax for Windows
                    print(f"$env:{k}='{v}'")
                else:
                    # Unix/Linux/Mac bash syntax
                    print(f"export {k}='{v}'")
            return 0
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

    # Default: Foreground mode - run proxy directly
    # Check for existing session with same API key
    existing = mgr.session.get(args.api_key)
    if existing:
        print(
            f"Error: Server already running on port {existing['port']} (PID:{existing['pid']})",
            file=sys.stderr,
        )
        print("Use --kill-all to stop existing servers", file=sys.stderr)
        return 1

    # Determine port
    port = args.port if args.port else Process.find_port()
    if not port:
        print("Error: No available port", file=sys.stderr)
        return 1

    # Check if port is already in use by another session
    for session in mgr.session.all():
        if session["port"] == port:
            print(
                f"Error: Port {port} already in use by another server (PID:{session['pid']})",
                file=sys.stderr,
            )
            print(
                "Use a different port or --kill-all to stop existing servers",
                file=sys.stderr,
            )
            return 1

    print(f"Starting proxy on port {port}...", file=sys.stderr)
    asyncio.run(run_proxy(args.api_key, port, args.verbose))
    return 0


if __name__ == "__main__":
    sys.exit(main())

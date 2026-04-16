"""
GRC Proxy - Standalone HTTP proxy for LLM request interception (Claude Code).

This is a SEPARATE distribution mode from the SDK package (grc.init()).
It runs as a standalone proxy server using mitmproxy to intercept HTTP/HTTPS
traffic and enforce GRC policies on LLM requests without requiring code changes.

**PRIMARY USE CASE: LLM cost tracking and quota enforcement for Claude Code CLI running in terminal**

DISTRIBUTION:
    - Built with PyInstaller into standalone executables
    - No Python installation required for end users
    - Runs independently of the grc Python package

USAGE:
    As executable: grc-proxy --api-key=grc_xxx [--port 8080] [--verbose]

ARCHITECTURE:
    - mitmproxy handles HTTPS interception and certificate management
    - Certificates auto-generated in ~/.mitmproxy/ on first run
    - ProxyAddon orchestrates request/response lifecycle
    - RequestHandler validates quota BEFORE LLM requests
    - ResponseHandler extracts token usage AFTER responses

CLIENT SETUP (Claude Code):
    Set these environment variables before running LLM applications:
    - HTTPS_PROXY=http://localhost:8080 or where the Executable is deployed!
    - NODE_EXTRA_CA_CERTS=~/.mitmproxy/mitmproxy-ca-cert.pem (Node.js only)

TARGET:
    - AWS Bedrock requests (specifically for Claude models)
    - **Designed specifically for tracking Claude Code CLI usage and costs in terminal sessions**
"""

import argparse
import asyncio
import logging

from mitmproxy import options
from mitmproxy.tools import dump

from grc.proxy import ProxyAddon
from grc.auth import AuthToken
from grc.context import auth_ctx

logger = logging.getLogger(__name__)


async def main():

    parser = argparse.ArgumentParser(
        prog="grc-proxy",
        description="GRC Proxy Server - For Claude Code",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument("--api-key", required=True, help="GRC API key")
    parser.add_argument(
        "--port", type=int, default=8080, help="Proxy port (default: 8080)"
    )
    parser.add_argument("--verbose", action="store_true", help="Verbose logging")

    args = parser.parse_args()

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="[%(asctime)s] [%(name)s] %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    auth = AuthToken.decode(args.api_key)
    auth_ctx.set(auth)

    addon = ProxyAddon()

    logger.info(f"GRC Proxy running on PORT:{args.port}")

    opts = options.Options(listen_host="127.0.0.1", listen_port=args.port)
    master = dump.DumpMaster(opts, with_termlog=False, with_dumper=False)
    master.addons.add(addon)
    await master.run()


if __name__ == "__main__":
    asyncio.run(main())

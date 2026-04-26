"""
StandIn frontend dev server.

Serves static files from this directory AND proxies API calls to backend agents,
adding CORS headers so the browser never blocks cross-origin requests.

Usage:
    python frontend/serve.py          # from project root
    # then open http://localhost:3000

Routes proxied:
    /api/perform/*  →  http://localhost:8008/*   (Perform Action agent)
    /api/status/*   →  http://localhost:8007/*   (Status Agent)
    /api/history/*  →  http://localhost:8009/*   (Historical Agent)
"""
import json
import mimetypes
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

try:
    from aiohttp import web, ClientSession, ClientConnectorError, ClientTimeout
except ImportError:
    print("aiohttp not installed — run: pip install aiohttp")
    sys.exit(1)

ROOT = Path(__file__).parent
PORT = int(os.getenv("STANDIN_PORT", "3000"))

# All agents share the Bureau on port 8000; route via x-uagents-address header.
BUREAU_URL = "http://localhost:8000"

PROXY_ROUTES = {
    "/api/perform/": (BUREAU_URL + "/", "agent1qf83fffdv22j2etuqarww9nwqcenq5zavvekh7k2utflqaxx08j4x38e69v"),
    "/api/status/":  (BUREAU_URL + "/", "agent1q2l8xf3dvwvmarl2dpxwtv5ym7pvge53szhstykukmrwuhm93z6k68tphgh"),
    "/api/history/": (BUREAU_URL + "/", "agent1qf60yzmr9reyjnduq8qneum5nf03zzaw60cl6yny9l7la676unf7jdfdtrv"),
}

# Long-running POST routes (agent pipeline can take up to 60s)
SLOW_ROUTES = {
    "/api/status/brief",
    "/api/history/ask",
    "/api/perform/conversations/start",
    "/api/perform/conversations/get",
}
FAST_TIMEOUT = 8
SLOW_TIMEOUT = 60

CORS = {
    "Access-Control-Allow-Origin":  "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Authorization",
}


def _proxy_target(path: str) -> tuple[str, str] | None:
    for prefix, (base, agent_addr) in PROXY_ROUTES.items():
        if path.startswith(prefix):
            return base + path[len(prefix):], agent_addr
    return None


async def handle_api(request: web.Request) -> web.Response:
    if request.method == "OPTIONS":
        return web.Response(status=204, headers=CORS)

    match = _proxy_target(request.path)
    if not match:
        return web.Response(status=404, text='{"error":"no proxy route"}',
                            content_type="application/json", headers=CORS)

    target, agent_addr = match
    timeout = ClientTimeout(total=SLOW_TIMEOUT if request.path in SLOW_ROUTES else FAST_TIMEOUT)
    fwd_headers = {
        "Content-Type": "application/json",
        "x-uagents-address": agent_addr,
    }
    try:
        async with ClientSession() as session:
            if request.method == "POST":
                body = await request.read()
                async with session.post(
                    target, data=body,
                    headers=fwd_headers,
                    timeout=timeout,
                ) as resp:
                    data = await resp.read()
                    return web.Response(body=data, status=resp.status,
                                        content_type="application/json", headers=CORS)
            else:
                async with session.get(target, headers=fwd_headers, timeout=timeout) as resp:
                    data = await resp.read()
                    return web.Response(body=data, status=resp.status,
                                        content_type="application/json", headers=CORS)
    except ClientConnectorError:
        body = f'{{"error":"agent offline","target":"{target}"}}'
        return web.Response(status=503, text=body,
                            content_type="application/json", headers=CORS)
    except Exception as exc:
        body = f'{{"error":"{exc}"}}'
        return web.Response(status=500, text=body,
                            content_type="application/json", headers=CORS)


async def handle_static(request: web.Request) -> web.Response:
    rel = request.path.lstrip("/") or "index.html"
    path = ROOT / rel
    if not path.exists() or not path.is_file():
        # SPA fallback
        path = ROOT / "index.html"
    if not path.exists():
        return web.Response(status=404, text="Not found")
    mime = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
    headers = {**CORS, "Content-Type": mime}
    return web.FileResponse(path, headers=headers)


async def handle_auth0_config(request: web.Request) -> web.Response:
    """Expose Auth0 public config to the SPA — no secrets, only public values."""
    cfg = {
        "domain":    os.getenv("AUTH0_DOMAIN", ""),
        "client_id": os.getenv("AUTH0_SPA_CLIENT_ID", ""),
        "audience":  os.getenv("AUTH0_AUDIENCE", ""),
    }
    return web.Response(
        text=json.dumps(cfg), content_type="application/json", headers=CORS,
    )


def build_app() -> web.Application:
    app = web.Application()
    app.router.add_route("GET",  "/auth0-config", handle_auth0_config)
    app.router.add_route("*", "/api/{tail:.*}", handle_api)
    app.router.add_route("GET",  "/{tail:.*}", handle_static)
    return app


if __name__ == "__main__":
    print(f"\n  StandIn Dashboard  →  http://localhost:{PORT}\n")
    for prefix, (base, addr) in PROXY_ROUTES.items():
        print(f"  {prefix}*  →  {base}* (agent: {addr[:20]}…)")
    print()
    web.run_app(build_app(), host="0.0.0.0", port=PORT, print=lambda *_: None)

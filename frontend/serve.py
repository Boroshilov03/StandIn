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
import mimetypes
import os
import sys
from pathlib import Path

try:
    from aiohttp import web, ClientSession, ClientConnectorError
except ImportError:
    print("aiohttp not installed — run: pip install aiohttp")
    sys.exit(1)

ROOT = Path(__file__).parent
PORT = int(os.getenv("STANDIN_PORT", "3000"))

PROXY_ROUTES = {
    "/api/perform/": "http://localhost:8008/",
    "/api/status/":  "http://localhost:8007/",
    "/api/history/": "http://localhost:8009/",
}

CORS = {
    "Access-Control-Allow-Origin":  "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Authorization",
}


def _proxy_target(path: str) -> str | None:
    for prefix, base in PROXY_ROUTES.items():
        if path.startswith(prefix):
            return base + path[len(prefix):]
    return None


async def handle_api(request: web.Request) -> web.Response:
    if request.method == "OPTIONS":
        return web.Response(status=204, headers=CORS)

    target = _proxy_target(request.path)
    if not target:
        return web.Response(status=404, text='{"error":"no proxy route"}',
                            content_type="application/json", headers=CORS)

    try:
        async with ClientSession() as session:
            if request.method == "POST":
                body = await request.read()
                async with session.post(
                    target, data=body,
                    headers={"Content-Type": "application/json"},
                    timeout=8,
                ) as resp:
                    data = await resp.read()
                    return web.Response(body=data, status=resp.status,
                                        content_type="application/json", headers=CORS)
            else:
                async with session.get(target, timeout=8) as resp:
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


def build_app() -> web.Application:
    app = web.Application()
    app.router.add_route("*", "/api/{tail:.*}", handle_api)
    app.router.add_route("GET",  "/{tail:.*}", handle_static)
    return app


if __name__ == "__main__":
    print(f"\n  StandIn Dashboard  →  http://localhost:{PORT}\n")
    for prefix, target in PROXY_ROUTES.items():
        print(f"  {prefix}*  →  {target}*")
    print()
    web.run_app(build_app(), host="0.0.0.0", port=PORT, print=lambda *_: None)

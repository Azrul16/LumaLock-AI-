"""Loopback-only browser launcher and authenticated local application routes."""

import argparse
import asyncio
import json
import logging
import os
import re
import secrets
import sys
import threading
import uuid
import webbrowser
from pathlib import Path
from urllib.parse import unquote

from aiohttp import web
from PIL import Image, UnidentifiedImageError

from lumalock.core.config import data_dir
from lumalock.core.exceptions import UserError
from lumalock.core.logging import configure_logging
from lumalock.webapp.previews import PreviewCache
from lumalock.webapp.resources import ResourceMonitor
from lumalock.webapp.service import Busy, ImageService

SERVICE = web.AppKey("service", ImageService)
SESSION = web.AppKey("session", str)
STOP = web.AppKey("stop", asyncio.Event)
RESOURCES = web.AppKey("resources", ResourceMonitor)
PREVIEWS = web.AppKey("previews", PreviewCache)
STATIC = Path(__file__).parent / "static"


@web.middleware
async def local_access(request, handler):
    host = request.host
    if not re.fullmatch(r"(?:127\.0\.0\.1|localhost):\d+", host):
        raise web.HTTPForbidden(text="Local requests only.")
    origin = request.headers.get("Origin")
    if origin and origin != f"http://{host}":
        raise web.HTTPForbidden(text="Cross-site requests are not allowed.")
    if request.path.startswith("/api/") and request.path != "/api/ping":
        if request.cookies.get("lumalock_session") != request.app[SESSION]:
            return web.json_response(
                {"error": "Open LumaLock in this browser first, then retry."}, status=401
            )
        if request.method != "GET" and request.headers.get("X-LumaLock") != "1":
            raise web.HTTPForbidden(text="Invalid local request.")
    try:
        response = await handler(request)
    except Busy as exc:
        response = web.json_response({"error": str(exc)}, status=409)
    except (UserError, ValueError, KeyError, TypeError) as exc:
        response = web.json_response({"error": str(exc)}, status=400)
    except web.HTTPException:
        raise
    except Exception:
        logging.getLogger("lumalock.web").exception("Local request failed")
        response = web.json_response(
            {"error": "This operation failed. Check available disk space and retry."}, status=500
        )
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' blob: data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
    )
    return response


async def index(request):
    response = web.Response(
        text=(STATIC / "index.html").read_text(encoding="utf-8"), content_type="text/html"
    )
    response.set_cookie("lumalock_session", request.app[SESSION], httponly=True, samesite="Strict")
    return response


async def state(request):
    return web.json_response(request.app[SERVICE].state(request.query.get("chat")))


async def resources(request):
    return web.json_response(request.app[RESOURCES].snapshot())


async def resource_lifetime(app):
    app[RESOURCES].start()
    try:
        yield
    finally:
        await asyncio.to_thread(app[RESOURCES].close)


async def new_chat(request):
    return web.json_response(request.app[SERVICE].new_chat())


async def delete_chat(request):
    result = await asyncio.to_thread(request.app[SERVICE].delete_chat, request.match_info["chat"])
    await asyncio.to_thread(request.app[PREVIEWS].clear)
    return web.json_response(result)


async def ping(request):
    return web.json_response({"application": "LumaLockAI"})


async def upload(request):
    service = request.app[SERVICE]
    with service.lock:
        service.require_idle()
        service.get_chat(request.match_info["chat"])
    temporary = service.store.directory / f"upload-{uuid.uuid4().hex}.part"
    size = 0
    try:
        with temporary.open("wb") as stream:
            async for chunk in request.content.iter_chunked(256 * 1024):
                size += len(chunk)
                if size > 64 * 1024**2:
                    raise UserError("This photo exceeds 64 MiB. Use a smaller image file.")
                stream.write(chunk)
        try:
            with Image.open(temporary) as image:
                if image.format not in ("JPEG", "PNG", "WEBP", "TIFF"):
                    raise UserError("Choose a JPEG, PNG, WebP or TIFF photo.")
                if image.width * image.height > 60_000_000:
                    raise UserError("Use a photo with at most 60 megapixels.")
        except (UnidentifiedImageError, Image.DecompressionBombError) as exc:
            raise UserError(
                "This photo could not be opened. Choose a valid JPEG, PNG, WebP or TIFF."
            ) from exc
        chat = await asyncio.to_thread(
            service.attach,
            request.match_info["chat"],
            temporary,
            unquote(request.headers.get("X-Filename", "Photo.png")),
        )
        return web.json_response(chat)
    finally:
        temporary.unlink(missing_ok=True)


async def select(request):
    payload = await request.json()
    return web.json_response(
        request.app[SERVICE].select(request.match_info["chat"], payload.get("image"))
    )


async def edit(request):
    payload = await request.json()
    if not isinstance(payload.get("preserve", True), bool):
        raise UserError("Choose whether to preserve people.")
    return web.json_response(
        request.app[SERVICE].start_edit(
            request.match_info["chat"],
            payload.get("prompt", ""),
            payload.get("preserve", True),
            payload.get("quality", "Maximum"),
            payload.get("device", "auto"),
        )
    )


async def image(request):
    name = request.match_info["image"]
    if not re.fullmatch(r"[a-f0-9]{32}\.png", name):
        raise web.HTTPNotFound()
    path = request.app[SERVICE].store.asset("assets/" + name)
    if not path.is_file():
        raise web.HTTPNotFound()
    if "preview" in request.query:
        maximum = int(request.query["preview"])
        if maximum not in (320, 1024):
            raise UserError("Choose a valid preview size.")
        content = await asyncio.to_thread(request.app[PREVIEWS].get, path, maximum)
        return web.Response(body=content, content_type="image/webp")
    response = web.FileResponse(path)
    if request.query.get("download") == "1":
        response.headers["Content-Disposition"] = 'attachment; filename="LumaLock-edit.png"'
    return response


async def models(request):
    payload = await request.json()
    if not isinstance(payload.get("accept_license", False), bool):
        raise UserError("License acknowledgement must be explicit.")
    if not isinstance(payload.get("verify", False), bool) or not isinstance(
        payload.get("keys", []), list
    ):
        raise UserError("Choose valid model setup options.")
    return web.json_response(
        request.app[SERVICE].start_models(
            payload.get("keys", ["prompt", "flux"]),
            payload.get("accept_license", False),
            payload.get("verify", False),
        )
    )


async def cancel(request):
    request.app[SERVICE].cancel()
    return web.json_response({"ok": True})


async def stop(request):
    request.app[STOP].set()
    return web.json_response({"ok": True})


async def static(request):
    name = request.match_info["file"]
    if name not in ("app.js", "style.css", "favicon.svg"):
        raise web.HTTPNotFound()
    return web.FileResponse(STATIC / name)


def create_app(service=None, monitor=None):
    app = web.Application(middlewares=[local_access], client_max_size=65 * 1024**2)
    app[SERVICE] = service or ImageService()
    app[SESSION] = secrets.token_urlsafe(32)
    app[STOP] = asyncio.Event()
    app[RESOURCES] = monitor or ResourceMonitor(data_dir())
    app[PREVIEWS] = PreviewCache()
    app.cleanup_ctx.append(resource_lifetime)
    app.add_routes(
        [
            web.get("/", index),
            web.get("/static/{file}", static),
            web.get("/api/ping", ping),
            web.get("/api/state", state),
            web.get("/api/resources", resources),
            web.post("/api/chats", new_chat),
            web.delete("/api/chats/{chat}", delete_chat),
            web.post("/api/chats/{chat}/upload", upload),
            web.post("/api/chats/{chat}/select", select),
            web.post("/api/chats/{chat}/edit", edit),
            web.get("/api/images/{image}", image),
            web.post("/api/models", models),
            web.post("/api/cancel", cancel),
            web.post("/api/stop", stop),
        ]
    )
    return app


async def serve(args):
    app = create_app()
    runner = web.AppRunner(app, access_log=None)
    await runner.setup()
    watcher_stop = threading.Event()
    try:
        site = web.TCPSite(runner, "127.0.0.1", args.port)
        try:
            await site.start()
        except OSError:
            site = web.TCPSite(runner, "127.0.0.1", 0)
            await site.start()
        port = site._server.sockets[0].getsockname()[1]
        url = f"http://127.0.0.1:{port}"
        info = data_dir() / "server.json"
        info.write_text(json.dumps({"url": url, "pid": os.getpid()}), encoding="utf-8")
        if args.open:
            service = app[SERVICE]
            chat_id = service.state()["chat"]["id"]
            await asyncio.to_thread(service.attach, chat_id, args.open, Path(args.open).name)
        if not args.no_browser and not args.smoke_test:
            webbrowser.open(url, new=2)
        if sys.stdout:
            print(f"LumaLock AI is running at {url}", flush=True)
            print(
                "Keep this terminal open. Ctrl+C or closing it stops the server and AI workers.",
                flush=True,
            )
        if os.getenv("LUMALOCK_WATCH_CONSOLE") == "1":
            import psutil

            console = next(
                (
                    parent
                    for parent in psutil.Process().parents()
                    if parent.name().lower() == "cmd.exe"
                ),
                None,
            )
            if console:
                loop = asyncio.get_running_loop()

                def watch_console():
                    while not watcher_stop.wait(0.25):
                        if not console.is_running():
                            from lumalock.core.process_lifetime import close_owned_workers

                            app[SERVICE].cancel()
                            close_owned_workers()
                            loop.call_soon_threadsafe(app[STOP].set)
                            return

                threading.Thread(
                    target=watch_console, daemon=True, name="terminal-lifetime"
                ).start()
        if args.smoke_test:
            import aiohttp

            async with aiohttp.ClientSession(trust_env=False) as client:
                async with client.get(url + "/api/ping") as response:
                    assert response.status == 200
            return
        await app[STOP].wait()
    finally:
        watcher_stop.set()
        await asyncio.to_thread(app[SERVICE].close)
        await runner.cleanup()


def main():
    parser = argparse.ArgumentParser(description="LumaLock AI local browser application")
    parser.add_argument("--port", type=int, default=7860)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--smoke-test", action="store_true")
    parser.add_argument("--open", type=Path)
    parser.add_argument("--check-backend", type=Path)
    args = parser.parse_args()
    configure_logging()
    if args.check_backend:
        from lumalock.core.backend_registry import GENERATIVE_BACKENDS

        backend = GENERATIVE_BACKENDS.create("flux", models=None)
        args.check_backend.write_text(
            json.dumps(
                {
                    "backend_import": type(backend).__name__,
                    "frozen": bool(getattr(sys, "frozen", False)),
                    "qt_loaded": any(name.startswith("PySide6") for name in sys.modules),
                }
            ),
            encoding="utf-8",
        )
        return 0
    from filelock import FileLock, Timeout

    lock = FileLock(data_dir() / "server.lock", timeout=0)
    try:
        with lock:
            asyncio.run(serve(args))
    except Timeout:
        try:
            info = json.loads((data_dir() / "server.json").read_text(encoding="utf-8"))
            if re.fullmatch(r"http://127\.0\.0\.1:\d+", info["url"]):
                if not args.no_browser and not args.smoke_test:
                    webbrowser.open(info["url"], new=2)
        except (OSError, ValueError, KeyError):
            raise SystemExit("LumaLock is already starting. Please wait a moment.")
    except KeyboardInterrupt:
        pass
    return 0

"""Exercise the real websocket transport with an explicit ComfyUI protocol fixture."""

import asyncio

from aiohttp import web

from lumalock.comfy.progress import ComfyProgress


def test_local_worker_progress_socket_receives_steps_and_closes():
    async def scenario():
        clients, reports = [], []

        async def socket(request):
            clients.append(request.query["clientId"])
            connection = web.WebSocketResponse()
            await connection.prepare(request)
            await connection.send_json({"type": "executing", "data": {"node": "14"}})
            await connection.send_bytes(b"ignored preview data")
            await connection.send_json(
                {"type": "progress", "data": {"node": "14", "value": 2, "max": 8}}
            )
            await connection.close()
            return connection

        app = web.Application()
        app.router.add_get("/ws", socket)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", 0)
        await site.start()
        feed = ComfyProgress(
            f"http://127.0.0.1:{site._server.sockets[0].getsockname()[1]}",
            lambda *args: reports.append(args),
        )
        try:
            await asyncio.to_thread(feed.start)
            await asyncio.to_thread(feed.thread.join, 5)
            assert clients == [feed.client_id]
            assert reports == [
                (-1, "Preparing image sampling"),
                (25, "Generating image: sampling step 2 of 8"),
            ]
            assert not feed.thread.is_alive()
        finally:
            await asyncio.to_thread(feed.close)
            await runner.cleanup()

    asyncio.run(scenario())

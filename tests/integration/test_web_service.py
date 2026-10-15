import asyncio
import io
import time

import aiohttp
import numpy as np
from aiohttp.test_utils import TestClient, TestServer
from PIL import Image

from lumalock.webapp.server import create_app
from lumalock.webapp.service import ImageService


class ReadyModels:
    def installed(self, key):
        return True

    def available(self, key):
        return True

    def verify(self, key, cancelled, progress):
        progress(100, "Verified fixture")


class FixedResources:
    """Explicit telemetry fixture, not a measurement of the test host."""

    def start(self):
        pass

    def close(self):
        pass

    def snapshot(self):
        return {
            "stale": False,
            "cpu_percent": 36,
            "ram_percent": 69,
            "ram_used_gib": 5.3,
            "ram_total_gib": 7.7,
            "disk_read_mib_s": 12,
            "disk_write_mib_s": 4,
            "disk_free_gib": 70,
            "disk_used_percent": 68,
            "disk_drive": "D:/",
            "gpu": {"percent": 73, "used_mib": 2048, "total_mib": 4096, "temperature_c": 65},
        }


def test_local_http_chat_followups_download_and_access_checks(photograph, local_storage):
    async def scenario():
        calls = []

        def edit(root, source, prompt, models, preserve, cancelled, progress, **options):
            calls.append((root, source, prompt))
            result = local_storage / f"result-{len(calls)}.png"
            pixels = np.asarray(Image.open(source)).copy()
            pixels[0, 0] = [len(calls), 20, 30]
            Image.fromarray(pixels).save(result)
            return result

        service = ImageService(models=ReadyModels(), editor=edit)
        client = TestClient(
            TestServer(create_app(service)), cookie_jar=aiohttp.CookieJar(unsafe=True)
        )
        await client.start_server()
        try:
            assert (await client.get("/api/state")).status == 401
            assert (await client.get("/api/resources")).status == 401
            response = await client.get("/")
            assert response.status == 200
            assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]
            assert (
                await client.get("/api/state", headers={"Host": "evil.test:1234"})
            ).status == 403
            assert (await client.post("/api/chats")).status == 403
            assert (
                await client.get("/api/state", headers={"Origin": "https://evil.test"})
            ).status == 403
            headers = {"X-LumaLock": "1"}
            assert (await client.get("/api/resources")).status == 200
            state = await (await client.get("/api/state")).json()
            chat_id = state["chat"]["id"]
            png = io.BytesIO()
            Image.fromarray(photograph).save(png, format="PNG")
            invalid = await client.post(
                f"/api/chats/{chat_id}/upload", data=b"invalid photo", headers=headers
            )
            assert invalid.status == 400
            assert "photo could not be opened" in (await invalid.json())["error"]
            response = await client.post(
                f"/api/chats/{chat_id}/upload",
                data=png.getvalue(),
                headers={**headers, "X-Filename": "Photo.png"},
            )
            assert response.status == 200
            original = (await response.json())["selected_root"]
            for prompt in ("Make it warmer", "Now add a subtle film look"):
                response = await client.post(
                    f"/api/chats/{chat_id}/edit", json={"prompt": prompt}, headers=headers
                )
                assert response.status == 200
                deadline = time.monotonic() + 10
                while time.monotonic() < deadline:
                    state = await (await client.get(f"/api/state?chat={chat_id}")).json()
                    if state["job"]["status"] not in ("running", "stopping"):
                        break
                    await asyncio.sleep(0.01)
                assert state["job"]["status"] == "complete"
            first, second = state["chat"]["turns"]
            assert second["source"] == first["result"]
            assert second["root"] == original
            assert calls[0][0] == calls[1][0]
            response = await client.post(
                f"/api/chats/{chat_id}/select", json={"image": first["result"]}, headers=headers
            )
            assert response.status == 200
            assert (await response.json())["selected_image"] == first["result"]
            assert (
                await client.post(
                    f"/api/chats/{chat_id}/select",
                    json={"image": "assets/outside.png"},
                    headers=headers,
                )
            ).status == 400
            response = await client.get(f"/api/images/{first['result'].split('/')[-1]}?download=1")
            assert response.status == 200
            assert "attachment" in response.headers["Content-Disposition"]
            assert Image.open(io.BytesIO(await response.read())).size == (3840, 2560)
            response = await client.get(f"/api/images/{first['result'].split('/')[-1]}?preview=320")
            assert response.content_type == "image/webp"
            assert Image.open(io.BytesIO(await response.read())).size == (192, 128)
            assert (
                await client.get(f"/api/images/{first['result'].split('/')[-1]}?preview=9999")
            ).status == 400
            assert (await client.get("/api/images/outside.png")).status == 404
        finally:
            await client.close()
            service.close()

    asyncio.run(scenario())


def test_web_job_busy_guard_and_safe_cancellation(photograph, local_storage):
    from lumalock.core.exceptions import Cancelled
    from lumalock.webapp.service import Busy

    def edit(root, source, prompt, models, preserve, cancelled, progress, **options):
        while not cancelled():
            time.sleep(0.005)
        raise Cancelled("Edit stopped")

    service = ImageService(models=ReadyModels(), editor=edit)
    source = local_storage / "photo.png"
    Image.fromarray(photograph).save(source)
    chat = service.state()["chat"]
    service.attach(chat["id"], source, "Photo.png")
    service.start_edit(chat["id"], "Make it warmer")
    import pytest

    with pytest.raises(Busy):
        service.new_chat()
    with pytest.raises(Busy):
        service.delete_chat(chat["id"])
    service.cancel()
    service.close()
    state = service.state(chat["id"])
    assert state["job"]["status"] == "cancelled"
    assert state["chat"]["turns"][0]["status"] == "failed"
    assert source.exists()


def test_restart_selects_newest_chat_and_keeps_sidebar_order(local_storage):
    from lumalock.project.chat import Conversation

    old, new = Conversation(title="Older"), Conversation(title="Newest")
    store = type("Store", (), {"recent": lambda self: [new, old]})()
    service = ImageService(models=ReadyModels(), store=store)
    try:
        state = service.state()
        assert state["chat"]["id"] == new.id
        assert [item["title"] for item in state["chats"]] == ["Newest", "Older"]
    finally:
        service.close()


def test_stop_during_backend_error_is_cancelled_not_retried(photograph, local_storage):
    def editor(root, source, prompt, models, preserve, cancelled, progress, **options):
        while not cancelled():
            time.sleep(0.005)
        raise ConnectionError("Worker stopped before interrupt response")

    service = ImageService(models=ReadyModels(), editor=editor)
    source = local_storage / "source.png"
    Image.fromarray(photograph).save(source)
    chat = service.state()["chat"]
    service.attach(chat["id"], source, "Source.png")
    service.start_edit(chat["id"], "Edit")
    service.cancel()
    service.close()
    assert service.state()["job"]["status"] == "cancelled"


def test_delete_http_requires_session_and_keeps_an_empty_chat(local_storage):
    async def scenario():
        service = ImageService(models=ReadyModels())
        client = TestClient(
            TestServer(create_app(service, monitor=FixedResources())),
            cookie_jar=aiohttp.CookieJar(unsafe=True),
        )
        await client.start_server()
        try:
            identifier = service.state()["chat"]["id"]
            assert (await client.delete(f"/api/chats/{identifier}")).status == 401
            await client.get("/")
            assert (await client.delete(f"/api/chats/{identifier}")).status == 403
            response = await client.delete(f"/api/chats/{identifier}", headers={"X-LumaLock": "1"})
            assert response.status == 200
            result = await response.json()
            assert result["deleted"] == identifier
            state = await (await client.get("/api/state")).json()
            assert len(state["chats"]) == 1
            assert state["chat"]["id"] == result["next_chat_id"] != identifier
            assert (
                await client.delete(f"/api/chats/{identifier}", headers={"X-LumaLock": "1"})
            ).status == 400
        finally:
            await client.close()
            service.close()

    asyncio.run(scenario())


def test_unlimited_edit_retains_explicit_stop_without_partial_image(photograph, local_storage):
    def editor(root, source, prompt, models, preserve, cancelled, progress, **options):
        while not cancelled():
            time.sleep(0.005)
        raise ConnectionError("Worker was stopped by the deadline")

    service = ImageService(models=ReadyModels(), editor=editor)
    source = local_storage / "source.png"
    Image.fromarray(photograph).save(source)
    identifier = service.state()["chat"]["id"]
    service.attach(identifier, source, "Photo.png")
    job = service.start_edit(identifier, "Warm late afternoon", mode="Natural")
    assert job["limit_seconds"] is None
    assert not hasattr(service, "deadline_timer")
    assert not service.cancelled.is_set()
    service.cancel()
    service.close()
    state = service.state(identifier)
    assert state["job"]["status"] == "cancelled"
    assert not state["chat"]["turns"][-1]["result"]
    assert source.exists()


def test_manual_protection_and_mode_are_persisted_for_each_request(photograph, local_storage):
    observed = []

    def editor(root, source, prompt, models, preserve, cancelled, progress, **options):
        observed.append(options)
        return source

    service = ImageService(models=ReadyModels(), editor=editor)
    source = local_storage / "source.png"
    Image.fromarray(photograph).save(source)
    identifier = service.state()["chat"]["id"]
    service.attach(identifier, source, "Photo.png")
    shape = {"tool": "rectangle", "points": [[0.2, 0.2], [0.7, 0.8]]}
    service.set_protection(identifier, [shape])
    service.start_edit(
        identifier, "Remove the background object", mode="Creative", preset="Dramatic Sky"
    )
    service.close()
    turn = service.state(identifier)["chat"]["turns"][-1]
    assert turn["mode"] == "Creative" and turn["preset"] == "Dramatic Sky"
    assert turn["protection"][0]["tool"] == "rectangle"
    assert observed[0]["protection"][0].tool == "rectangle"


def test_cancellation_during_result_storage_cannot_publish_success(photograph, local_storage):
    import threading

    expired = threading.Event()
    service = ImageService(models=ReadyModels(), editor=lambda root, source, *args, **kw: source)
    source = local_storage / "source.png"
    Image.fromarray(photograph).save(source)
    identifier = service.state()["chat"]["id"]
    service.attach(identifier, source, "Source.png")
    remember = service.store.remember_image

    def expire_during_storage(path):
        result = remember(path)
        service.cancel()
        expired.set()
        return result

    service.store.remember_image = expire_during_storage
    service.start_edit(identifier, "Late afternoon")
    assert expired.wait(timeout=10)
    service.close()
    state = service.state(identifier)
    assert state["job"]["status"] == "cancelled"
    assert state["chat"]["turns"][-1]["result"] is None

"""Real browser interaction with an explicit image-service test double, not AI quality QA."""

import asyncio
import queue
import threading
import time
from pathlib import Path

import numpy as np
import pytest
from aiohttp import web
from PIL import Image

from lumalock.webapp.server import STOP, create_app
from lumalock.webapp.service import ImageService
from tests.integration.test_web_service import FixedResources, ReadyModels


def test_edge_image_chat_save_edit_branch_refresh_and_mobile(photograph, local_storage):
    playwright = pytest.importorskip("playwright.sync_api")
    if not Path("C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe").exists():
        pytest.skip("Microsoft Edge is not installed on this host")
    calls = []

    def editor(root, source, prompt, models, preserve, cancelled, progress, **options):
        calls.append((root, source, prompt, options))
        result = local_storage / f"browser-result-{len(calls)}.png"
        pixels = np.asarray(Image.open(source)).copy()
        pixels[0, 0] = [30, len(calls), 20]
        Image.fromarray(pixels).save(result)
        return result

    service = ImageService(models=ReadyModels(), editor=editor)
    addresses = queue.Queue()

    async def run():
        app = create_app(service, monitor=FixedResources())
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", 0)
        await site.start()
        addresses.put(f"http://127.0.0.1:{site._server.sockets[0].getsockname()[1]}")
        await app[STOP].wait()
        await runner.cleanup()
        service.close()

    thread = threading.Thread(target=lambda: asyncio.run(run()), daemon=True)
    thread.start()
    url = addresses.get(timeout=10)
    source = local_storage / "browser-photo.png"
    Image.fromarray(photograph).save(source)
    original = source.read_bytes()
    try:
        with playwright.sync_playwright() as p:
            browser = p.chromium.launch(channel="msedge", headless=True)
            page = browser.new_page(viewport={"width": 1440, "height": 1000}, accept_downloads=True)
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(url)
            page.wait_for_function(
                "document.querySelector('#resource-cpu b')?.textContent === '36%'"
            )
            assert page.locator("#resource-gpu b").inner_text() == "73%"
            page.get_by_label("Live system resource usage").click()
            assert "2.0 / 4.0 GiB" in page.locator(".resource-details").inner_text()
            assert "12.0 MiB/s" in page.locator(".resource-details").inner_text()
            page.get_by_label("Live system resource usage").click()
            page.route(
                "**/api/resources",
                lambda route: route.fulfill(json={"stale": True, "cpu_percent": 99}),
            )
            page.evaluate("refreshResources()")
            assert page.locator("#resource-cpu b").inner_text() == "--"
            assert page.locator("#resource-gpu b").inner_text() == "--"
            page.unroute("**/api/resources")
            page.evaluate("refreshResources()")
            assert page.locator("#resource-gpu b").inner_text() == "73%"
            page.evaluate("""async () => {
                const original = window.fetch;
                let rejectOld;
                window.fetch = (url, ...args) => {
                    if (String(url).startsWith('/api/state') && !rejectOld)
                        return new Promise((resolve, reject) => { rejectOld = reject; });
                    return original(url, ...args);
                };
                try {
                    const older = refresh(true);
                    await refresh(true);
                    rejectOld(new Error('Stale request failed'));
                    await older;
                } finally { window.fetch = original; }
            }""")
            assert not page.locator("#connection").evaluate(
                "el => el.classList.contains('offline')"
            )
            page.route("**/api/state*", lambda route: route.abort())
            page.evaluate("refresh(true)")
            assert "server is unavailable" in page.locator("#notice").inner_text()
            page.unroute("**/api/state*")
            page.evaluate("refresh(true)")
            assert page.locator("#notice").is_hidden()
            assert page.locator("#attach").inner_text().strip().startswith("＋")
            assert page.locator("#close-settings").inner_text() == "×"
            page.locator("#open-settings").click()
            assert "Â" not in page.locator("#hardware").inner_text()
            page.locator("#close-settings").click()
            page.get_by_role("heading", name="What would you like to change?").wait_for()
            page.locator("#photo-input").set_input_files(str(source))
            page.locator("#attachment").wait_for(state="visible")
            assert page.locator("#edit-mode").input_value() == "Natural"
            assert page.locator("#preset option").count() == 13
            page.locator("#preset").select_option("Late Afternoon")
            page.locator("#protect-area").click()
            page.wait_for_function("() => !document.querySelector('#apply-protection').disabled")
            page.locator("#protection-tool").select_option("rectangle")
            box = page.locator("#protection-canvas").bounding_box()
            page.mouse.move(box["x"] + box["width"] * 0.3, box["y"] + box["height"] * 0.25)
            page.mouse.down()
            page.mouse.move(box["x"] + box["width"] * 0.65, box["y"] + box["height"] * 0.8, steps=3)
            page.mouse.up()
            page.locator("#apply-protection").click()
            page.locator("#protection-dialog").wait_for(state="hidden")
            page.wait_for_function(
                "() => document.querySelector('#protection-count').textContent === '(1)'"
            )
            for index, prompt in enumerate(
                ("Browser QA: improve lighting", "Browser QA: follow-up edit"), start=1
            ):
                page.locator("#prompt").fill(prompt)
                if index == 2:
                    page.locator("#edit-mode").select_option("Creative")
                if index == 1:

                    def preserve_new_draft(route):
                        response = route.fetch()
                        page.locator("#prompt").fill("Keep this next-prompt draft")
                        route.fulfill(response=response)

                    page.route("**/api/chats/*/edit", preserve_new_draft)
                page.get_by_role("button", name="Send prompt").click()
                page.wait_for_function(
                    "count => document.querySelectorAll('.result-image').length === count",
                    arg=index,
                )
                if index == 1:
                    assert page.locator("#prompt").input_value() == "Keep this next-prompt draft"
                    page.unroute("**/api/chats/*/edit")
            assert calls[0][0] == calls[1][0]
            assert calls[0][1] != calls[1][1]
            assert calls[0][3]["mode"] == "Natural" and calls[1][3]["mode"] == "Creative"
            assert calls[0][3]["preset"] == "Late Afternoon"
            assert calls[0][3]["protection"][0].tool == "rectangle"
            page.get_by_role("button", name="Before / after").first.click()
            page.wait_for_function(
                "() => document.querySelector('#compare-before').naturalWidth > 0 && document.querySelector('#compare-after').naturalWidth > 0"
            )
            assert page.locator("#compare-before").is_visible()
            assert page.locator("#compare-after").is_visible()
            page.locator("#close-compare").click()
            with page.expect_download() as download:
                page.get_by_role("link", name="Save 4K image").first.click()
            target = local_storage / "browser-saved.png"
            download.value.save_as(str(target))
            assert Image.open(target).size == (3840, 2560)
            page.get_by_role("button", name="Edit image").first.click()
            page.locator("#prompt").fill("Browser QA: branch from first result")
            page.get_by_role("button", name="Send prompt").click()
            page.wait_for_function("() => document.querySelectorAll('.result-image').length === 3")
            assert calls[2][1] == calls[1][1]
            page.reload()
            page.wait_for_function("() => document.querySelectorAll('.result-image').length === 3")
            page.screenshot(path=str(local_storage / "browser-chat-desktop.png"), full_page=True)
            page.set_viewport_size({"width": 390, "height": 844})
            assert page.evaluate("document.body.scrollWidth <= innerWidth")
            page.get_by_role("button", name="Open settings").click()
            assert page.get_by_role("heading", name="Models & settings").is_visible()
            page.get_by_role("button", name="Close settings").click()
            page.screenshot(path=str(local_storage / "browser-chat-mobile.png"), full_page=True)
            assert source.read_bytes() == original
            page.locator("#toggle-sidebar").click()
            page.locator(".chat-row").first.hover()
            old_chat_id = service.state()["chat"]["id"]
            page.once("dialog", lambda dialog: dialog.dismiss())
            page.locator(".delete-chat").first.click()
            assert service.state()["chat"]["id"] == old_chat_id
            page.once("dialog", lambda dialog: dialog.accept())
            page.locator(".delete-chat").first.click()
            page.wait_for_function(
                "() => document.querySelector('#chat-title').textContent === 'New chat'"
            )
            assert service.state()["chat"]["id"] != old_chat_id
            assert page.locator("#edit-mode").input_value() == "Natural"
            assert page.locator("#preset").input_value() == ""
            assert not (service.store.directory / f"{old_chat_id}.json").exists()
            assert page.locator(".result-image").count() == 0
            assert source.read_bytes() == original
            page.reload()
            page.get_by_role("heading", name="What would you like to change?").wait_for()
            assert len(service.state()["chats"]) == 1
            assert not errors, errors
            page.request.post(url + "/api/stop", headers={"X-LumaLock": "1"})
            browser.close()
    finally:
        import requests

        session = requests.Session()
        session.trust_env = False
        try:
            session.get(url, timeout=2)
            session.post(url + "/api/stop", headers={"X-LumaLock": "1"}, timeout=2)
        except requests.RequestException:
            pass
        thread.join(timeout=10)
        service.close()


def test_edge_error_retry_cancel_and_model_pause_dialog(photograph, local_storage):
    from lumalock.core.exceptions import Cancelled, UserError

    playwright = pytest.importorskip("playwright.sync_api")
    if not Path("C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe").exists():
        pytest.skip("Microsoft Edge is not installed on this host")
    attempts = []

    def editor(root, source, prompt, models, preserve, cancelled, progress, **options):
        attempts.append(prompt)
        if len(attempts) == 1:
            raise UserError("Browser test fixture: repairable error")
        if prompt == "Wait for cancellation":
            progress(0, "Sampling test image")
            time.sleep(2.1)
            progress(25, "Sampling test image: step 2 of 8")
            while not cancelled():
                time.sleep(0.005)
            raise Cancelled("Edit stopped")
        return source

    class DownloadModels(ReadyModels):
        def download(self, key, cancelled, progress):
            progress(35, "Browser test fixture: receiving model file")
            while not cancelled():
                time.sleep(0.005)
            raise Cancelled("Paused. Partial files retained.")

    service = ImageService(models=DownloadModels(), editor=editor)
    addresses = queue.Queue()

    async def run():
        app = create_app(service)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", 0)
        await site.start()
        addresses.put(f"http://127.0.0.1:{site._server.sockets[0].getsockname()[1]}")
        await app[STOP].wait()
        await runner.cleanup()
        service.close()

    thread = threading.Thread(target=lambda: asyncio.run(run()), daemon=True)
    thread.start()
    url = addresses.get(timeout=10)
    source = local_storage / "photo.png"
    Image.fromarray(photograph).save(source)
    try:
        with playwright.sync_playwright() as p:
            browser = p.chromium.launch(channel="msedge", headless=True)
            page = browser.new_page(viewport={"width": 1366, "height": 900})
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(url)
            page.get_by_role("heading", name="What would you like to change?").wait_for()
            page.locator("#photo-input").set_input_files(str(source))
            page.locator("#attachment").wait_for(state="visible")
            page.locator("#prompt").fill("Retry this edit")
            page.get_by_role("button", name="Send prompt").click()
            page.get_by_role("button", name="Retry edit").wait_for()
            page.get_by_role("button", name="Retry edit").click()
            page.get_by_role("link", name="Save 4K image").wait_for()
            page.locator("#prompt").fill("Wait for cancellation")
            page.get_by_role("button", name="Send prompt").click()
            placeholder = page.locator(".generation-placeholder")
            placeholder.wait_for(state="visible")
            assert page.locator("#job").is_hidden()
            assert page.get_by_role("button", name="Stop edit", exact=True).count() == 1
            assert placeholder.locator(".skeleton-image").is_visible()
            page.wait_for_function(
                "() => document.querySelector('.generation-placeholder .progress-percent')?.textContent === 'This stage: 25%'"
            )
            assert "left in this stage" in placeholder.locator(".progress-eta").inner_text()
            assert "Elapsed" in placeholder.locator(".progress-elapsed").inner_text()
            page.reload()
            placeholder.wait_for(state="visible")
            assert "25%" in placeholder.locator(".progress-percent").inner_text()
            assert page.locator("#job").is_hidden()
            assert page.locator(".progress-metrics:visible").count() == 1
            page.wait_for_function(
                "() => { const image = document.querySelector('.skeleton-image').getBoundingClientRect(); const thread = document.querySelector('#thread').getBoundingClientRect(); return image.bottom > thread.top && image.top < thread.bottom; }"
            )
            page.emulate_media(reduced_motion="reduce")
            assert (
                placeholder.locator(".skeleton-image").evaluate(
                    "el => getComputedStyle(el, '::after').animationName"
                )
                == "none"
            )
            page.screenshot(path=str(local_storage / "browser-generation-progress.png"))
            page.get_by_role("button", name="Stop edit", exact=True).click()
            page.wait_for_function("() => !document.querySelector('#send').disabled")
            assert page.locator(".generation-placeholder").count() == 0
            assert service.state()["job"]["status"] == "cancelled"
            page.get_by_role("button", name="Open settings").click()
            page.locator("#license").check()
            page.locator("#download-models").click()
            page.locator("#pause-models").wait_for(state="visible")
            assert page.locator("#model-progress").is_visible()
            assert page.locator("#job").is_hidden()
            assert page.locator("#model-metrics").is_visible()
            assert "This stage:" in page.locator("#model-metrics .progress-percent").inner_text()
            page.get_by_role("button", name="Close settings").click()
            page.locator("#job").wait_for(state="visible")
            page.get_by_role("button", name="Open settings").click()
            assert page.locator("#job").is_hidden()
            page.locator("#pause-models").click()
            page.wait_for_function(
                "() => document.querySelector('#download-models').textContent.includes('Resume')"
            )
            assert service.state()["job"]["status"] == "cancelled"
            assert not errors, errors
            page.request.post(url + "/api/stop", headers={"X-LumaLock": "1"})
            browser.close()
    finally:
        import requests

        session = requests.Session()
        session.trust_env = False
        try:
            session.get(url, timeout=2)
            session.post(url + "/api/stop", headers={"X-LumaLock": "1"}, timeout=2)
        except requests.RequestException:
            pass
        thread.join(timeout=10)
        service.close()

"""Read actual sampling steps from the owned ComfyUI worker; never simulate progress."""

import asyncio
import logging
import threading
import uuid

import aiohttp


class ComfyProgress:
    def __init__(self, url, progress, device_label=None, vae_label=None):
        self.url = url
        self.progress = progress
        self.client_id = uuid.uuid4().hex
        self.ready = threading.Event()
        self.stopped = threading.Event()
        self.thread = None
        self.device_label = device_label
        self.vae_label = vae_label

    def start(self):
        self.thread = threading.Thread(target=self._run, daemon=True, name="flux-progress")
        self.thread.start()
        self.ready.wait(timeout=4)

    def close(self):
        self.stopped.set()
        if self.thread:
            self.thread.join(timeout=4)

    def _run(self):
        try:
            asyncio.run(self._listen())
        except Exception:
            # Losing telemetry must not abort a valid edit or fabricate a percentage.
            logging.getLogger("lumalock.comfy").debug("Progress feed unavailable", exc_info=True)
        finally:
            self.ready.set()

    async def _listen(self):
        timeout = aiohttp.ClientTimeout(total=None, sock_connect=3)
        async with aiohttp.ClientSession(timeout=timeout, trust_env=False) as session:
            async with session.ws_connect(
                self.url + "/ws", params={"clientId": self.client_id}, max_msg_size=16 * 1024**2
            ) as socket:
                self.ready.set()
                while not self.stopped.is_set():
                    try:
                        message = await socket.receive(timeout=0.25)
                    except asyncio.TimeoutError:
                        continue
                    if message.type == aiohttp.WSMsgType.TEXT:
                        self.handle(message.json())
                    elif message.type in (
                        aiohttp.WSMsgType.CLOSED,
                        aiohttp.WSMsgType.CLOSE,
                        aiohttp.WSMsgType.ERROR,
                    ):
                        break

    def handle(self, event):
        data = event.get("data", {})
        if event.get("type") == "progress" and str(data.get("node")) == "14":
            value, maximum = data.get("value"), data.get("max")
            if (
                isinstance(value, (int, float))
                and isinstance(maximum, (int, float))
                and maximum > 0
                and 0 <= value <= maximum
            ):
                self.progress(
                    int(100 * value / maximum),
                    f"Generating image: sampling step {int(value)} of {int(maximum)}",
                )
        elif event.get("type") == "executing":
            stages = {
                "1": "Loading the image model",
                "2": "Loading the text encoder",
                "3": "Loading the image decoder",
                "5": "Encoding your reference photo",
                "6": "Encoding your prompt",
                "14": "Preparing image sampling",
                "15": "Decoding the generated image",
                "16": "Saving the generated image",
            }
            stage = stages.get(str(data.get("node")))
            if stage:
                label = (
                    self.vae_label if str(data.get("node")) in ("5", "15") else self.device_label
                )
                if label and str(data.get("node")) in ("5", "6", "14", "15"):
                    stage += f" ({label})"
                self.progress(-1, stage)

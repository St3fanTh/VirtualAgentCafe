"""Bounded, cached Codex model discovery; no agent/model inference is started."""

import asyncio
import json
import os
import re
import signal
import time

MODEL_ID = r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$"


class ModelCatalog:
    def __init__(self):
        self.lock = asyncio.Lock()
        self.cached = None
        self.expires = 0

    @staticmethod
    async def query(bundled=False):
        process = await asyncio.create_subprocess_exec(
            "codex",
            "debug",
            "models",
            *(["--bundled"] if bundled else []),
            cwd="/",
            start_new_session=True,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        try:
            async with asyncio.timeout(6):
                chunks = bytearray()
                while chunk := await process.stdout.read(65536):
                    chunks.extend(chunk)
                    if len(chunks) > 2 * 1024 * 1024:
                        raise ValueError("Model catalog exceeds limit")
                if await process.wait() != 0:
                    raise ValueError("Model catalog unavailable")
                return json.loads(chunks)
        finally:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            await process.wait()

    @staticmethod
    def parse(document):
        models = document.get("models") if isinstance(document, dict) else None
        if not isinstance(models, list):
            raise ValueError("Invalid model catalog")
        return sorted(
            {
                item["slug"]
                for item in models
                if isinstance(item, dict)
                and item.get("visibility") == "list"
                and isinstance(item.get("slug"), str)
                and re.fullmatch(MODEL_ID, item["slug"])
            }
        )

    async def get(self, *, refresh=False):
        async with self.lock:
            if not refresh and self.cached is not None and time.monotonic() < self.expires:
                return self.cached
            models, source = [], "unavailable"
            for bundled in (False, True):
                try:
                    models = self.parse(await self.query(bundled))
                    if models:
                        source = "bundled" if bundled else "codex"
                        break
                except (OSError, ValueError, TimeoutError):
                    continue
            self.cached = {
                "models": models,
                "source": source,
                "detail": (
                    "Codex catalog; account access is checked by Codex at execution."
                    if source == "codex"
                    else "Bundled catalog; account availability has not been verified."
                    if source == "bundled"
                    else "Model catalog unavailable. Check Codex installation/login and refresh."
                ),
            }
            self.expires = time.monotonic() + 60
            return self.cached

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import httpx

from .scrapers.registry import get_scraper

CONFIG_PATH = Path(__file__).parent / "config.json"


class PriceCompareService:
    def __init__(self, config_path: Path = CONFIG_PATH):
        with open(config_path) as f:
            self._config = json.load(f)
        self._client = httpx.AsyncClient(
            timeout=30.0,
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
            headers={"User-Agent": "e-kart-service/1.0"},
        )

    async def close(self):
        await self._client.aclose()

    def _enabled_sources(self) -> list[dict]:
        return [s for s in self._config["sources"] if s.get("enabled")]

    async def _scrape_source(self, source_config: dict, search_term: str) -> list[dict]:
        try:
            scraper = get_scraper(source_config["scraper"], source_config, self._client)
            return await scraper.search(search_term)
        except Exception:
            return []

    async def fetch_price_compare(self, search_term: str) -> dict:
        enabled = self._enabled_sources()
        results = await asyncio.gather(
            *[self._scrape_source(source, search_term) for source in enabled]
        )

        response: dict = {"search_term": search_term}
        for source_config, result in zip(enabled, results):
            response[source_config["id"]] = result

        for source_config in self._config["sources"]:
            if not source_config.get("enabled"):
                response[source_config["id"]] = []

        return response

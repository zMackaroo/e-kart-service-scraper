from __future__ import annotations

from abc import ABC, abstractmethod

import httpx


class BaseScraper(ABC):
    def __init__(self, source_config: dict, client: httpx.AsyncClient):
        self.config = source_config
        self._client = client

    @property
    def source_id(self) -> str:
        return self.config["id"]

    @abstractmethod
    async def search(self, search_term: str) -> list[dict]:
        pass

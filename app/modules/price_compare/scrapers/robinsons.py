from __future__ import annotations

from .base import BaseScraper


class RobinsonsScraper(BaseScraper):
    async def search(self, search_term: str) -> list[dict]:
        return []

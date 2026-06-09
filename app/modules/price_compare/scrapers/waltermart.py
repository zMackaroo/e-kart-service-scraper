from __future__ import annotations

import asyncio

from .base import BaseScraper


class WalterMartScraper(BaseScraper):
    def _page_size(self) -> int:
        return self.config.get("page_size", 24)

    def _max_pages(self) -> int | None:
        return self.config.get("max_pages")

    def _fields(self) -> str:
        return self.config.get(
            "fields",
            "id,name,unit_price,sale_price,cover_image,canonical_url,upc,size",
        )

    def _search_params(self, search_term: str, skip: int) -> dict:
        params = {
            "app_key": self.config["app_key"],
            "store_id": self.config["store_id"],
            "token": self.config["token"],
            "fields": self._fields(),
            "limit": self._page_size(),
            "skip": skip,
        }
        if search_term.strip():
            params["q"] = search_term
        return params

    async def _fetch(self, search_term: str, skip: int) -> dict:
        resp = await self._client.get(
            self.config["base_url"],
            params=self._search_params(search_term, skip),
        )
        resp.raise_for_status()
        return resp.json()

    def _format_price(self, value: float | None) -> str | None:
        if value is None:
            return None
        return f"{value:.2f}"

    def _normalize_item(self, item: dict) -> dict:
        unit_price = item.get("unit_price")
        sale_price = item.get("sale_price")
        final_price = sale_price if sale_price else unit_price

        return {
            "name": item.get("name"),
            "sku": item.get("upc"),
            "regular_price": self._format_price(unit_price),
            "final_price": self._format_price(final_price),
            "currency": "PHP",
            "size": item.get("size"),
            "url_key": item.get("canonical_url"),
            "image_url": item.get("cover_image"),
        }

    async def _search_all_pages(self, search_term: str) -> list[dict]:
        page_size = self._page_size()
        first_payload = await self._fetch(search_term, 0)
        items = first_payload.get("items") or []
        total = first_payload.get("total") or len(items)
        products = [self._normalize_item(item) for item in items]

        if total <= page_size:
            return products

        total_pages = (total + page_size - 1) // page_size
        max_pages = self._max_pages()
        if max_pages is not None:
            total_pages = min(total_pages, max_pages)

        if total_pages > 1:
            skips = [page * page_size for page in range(1, total_pages)]
            payloads = await asyncio.gather(
                *[self._fetch(search_term, skip) for skip in skips]
            )
            for payload in payloads:
                for item in payload.get("items") or []:
                    products.append(self._normalize_item(item))

        return products

    def _match_products(self, catalog: list[dict], search_term: str) -> list[dict]:
        terms = search_term.lower().split()
        return [
            product
            for product in catalog
            if all(term in (product.get("name") or "").lower() for term in terms)
        ]

    async def search(self, search_term: str) -> list[dict]:
        if not search_term.strip():
            return []

        api_products = await self._search_all_pages(search_term)
        return self._match_products(api_products, search_term)

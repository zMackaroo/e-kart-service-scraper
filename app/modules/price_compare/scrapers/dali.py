from __future__ import annotations

import asyncio

from .base import BaseScraper


class DaliScraper(BaseScraper):
    def _page_size(self) -> int:
        return self.config.get("page_size", 28)

    def _max_pages(self) -> int | None:
        return self.config.get("max_pages")

    def _search_params(self, search_term: str, skip: int) -> dict:
        return {
            "q": search_term,
            "apiKey": self.config["api_key"],
            "country": self.config.get("country", "PH"),
            "locale": self.config.get("locale", "en"),
            "collection": self.config["collection"],
            "skip": skip,
            "take": self._page_size(),
        }

    async def _fetch(self, search_term: str, skip: int) -> dict:
        resp = await self._client.get(
            self.config["base_url"],
            params=self._search_params(search_term, skip),
        )
        resp.raise_for_status()
        return resp.json()

    def _format_price(self, raw_price: int) -> str:
        return f"{raw_price / 100:.2f}"

    def _format_image_url(self, url: str | None) -> str | None:
        if not url:
            return None
        if url.startswith("//"):
            return f"https:{url}"
        return url

    def _normalize_item(self, item: dict) -> dict:
        variant = (item.get("variants") or [{}])[0]
        image = (item.get("images") or [{}])[0]
        raw_price = variant.get("price", 0)
        raw_compare = variant.get("compareAtPrice", 0)

        return {
            "name": item.get("title"),
            "sku": variant.get("sku"),
            "barcode": variant.get("barcode"),
            "vendor": item.get("vendor"),
            "regular_price": self._format_price(raw_compare) if raw_compare else None,
            "final_price": self._format_price(raw_price),
            "currency": "PHP",
            "available": variant.get("available"),
            "url_key": item.get("urlName"),
            "image_url": self._format_image_url(image.get("url")),
        }

    async def _search_all_pages(self, search_term: str) -> tuple[list[dict], int]:
        page_size = self._page_size()
        first_payload = await self._fetch(search_term, 0)
        data = first_payload.get("data") or {}
        items = data.get("items") or []
        total = data.get("total") or len(items)
        products = [self._normalize_item(item) for item in items]

        if total <= page_size:
            return products, total

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
                page_data = payload.get("data") or {}
                for item in page_data.get("items") or []:
                    products.append(self._normalize_item(item))

        return products, total

    def _match_products(self, catalog: list[dict], search_term: str) -> list[dict]:
        terms = search_term.lower().split()
        return [
            product
            for product in catalog
            if all(term in (product.get("name") or "").lower() for term in terms)
        ]

    async def search(self, search_term: str) -> list[dict]:
        if not search_term.strip():
            products, _ = await self._search_all_pages("")
            return products

        api_products, _ = await self._search_all_pages(search_term)
        return self._match_products(api_products, search_term)

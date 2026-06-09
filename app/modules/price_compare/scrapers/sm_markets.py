from __future__ import annotations

import asyncio

from .base import BaseScraper

PRODUCT_FIELDS = (
    "name sku special_price url_key "
    "price{regularPrice{amount{currency value}}} "
    "price_range{minimum_price{final_price{value currency}}} "
    "small_image{url}"
)


class SMMarketsScraper(BaseScraper):
    def _page_size(self) -> int:
        return self.config.get("page_size", 24)

    def _max_pages(self) -> int | None:
        return self.config.get("max_pages")

    def _build_category_query(self, category_id: str, page: int) -> str:
        page_size = self._page_size()
        return (
            f"{{unbxdProducts(filter: {{, category_id: {{eq: \"{category_id}\"}} }}, "
            f"pageSize: {page_size} currentPage: {page} ) "
            f"{{items{{{PRODUCT_FIELDS}}} total_count request_id}}}}"
        )

    def _build_search_query(self, search_term: str, page: int) -> str:
        page_size = self._page_size()
        return (
            f"{{unbxdProducts(filter: {{, name: {{match: \"{search_term}\"}} }}, "
            f"pageSize: {page_size} currentPage: {page} ) "
            f"{{items{{{PRODUCT_FIELDS}}} total_count request_id}}}}"
        )

    async def _fetch(self, query: str) -> dict:
        resp = await self._client.get(
            self.config["base_url"],
            params={"query": query},
        )
        resp.raise_for_status()
        return resp.json()

    def _normalize_item(self, item: dict) -> dict:
        regular = item.get("price", {}).get("regularPrice", {}).get("amount", {})
        final = (
            item.get("price_range", {})
            .get("minimum_price", {})
            .get("final_price", {})
        )
        image = item.get("small_image") or {}
        return {
            "name": item.get("name"),
            "sku": item.get("sku"),
            "regular_price": regular.get("value"),
            "final_price": final.get("value"),
            "currency": final.get("currency") or regular.get("currency"),
            "special_price": item.get("special_price"),
            "url_key": item.get("url_key"),
            "image_url": image.get("url"),
        }

    def _extract_items(self, payload: dict) -> tuple[list[dict], int]:
        result = payload.get("data", {}).get("unbxdProducts") or {}
        items = result.get("items") or []
        total_count = result.get("total_count") or len(items)
        return items, total_count

    async def _paginate(self, build_query) -> tuple[list[dict], int]:
        first_payload = await self._fetch(build_query(1))
        items, total_count = self._extract_items(first_payload)
        products = [self._normalize_item(item) for item in items]

        page_size = self._page_size()
        total_pages = max(1, (total_count + page_size - 1) // page_size)
        max_pages = self._max_pages()
        if max_pages is not None:
            total_pages = min(total_pages, max_pages)

        if total_pages > 1:
            page_numbers = range(2, total_pages + 1)
            payloads = await asyncio.gather(
                *[self._fetch(build_query(page)) for page in page_numbers]
            )
            for payload in payloads:
                page_items, _ = self._extract_items(payload)
                products.extend(self._normalize_item(item) for item in page_items)

        return products, total_count

    async def _scrape_category(self, category_id: str) -> tuple[list[dict], int]:
        return await self._paginate(
            lambda page: self._build_category_query(category_id, page)
        )

    async def _search_api(self, search_term: str) -> tuple[list[dict], int]:
        return await self._paginate(
            lambda page: self._build_search_query(search_term, page)
        )

    def _search_queries(self, search_term: str) -> list[str]:
        words = search_term.split()
        queries = [search_term]

        if len(words) > 1:
            last_word = words[-1]
            if len(last_word) >= 3 and last_word.lower() not in {w.lower() for w in words[:-1]}:
                queries.append(last_word)

        return list(dict.fromkeys(queries))

    async def _smart_search(self, search_term: str) -> tuple[list[dict], int]:
        queries = self._search_queries(search_term)
        results = await asyncio.gather(
            *[self._search_api(query) for query in queries]
        )

        products = []
        total = 0
        for query_products, query_total in results:
            products.extend(query_products)
            total = max(total, query_total)

        return products, total

    def _match_products(self, catalog: list[dict], search_term: str) -> list[dict]:
        terms = search_term.lower().split()
        return [
            product
            for product in catalog
            if all(term in (product.get("name") or "").lower() for term in terms)
        ]

    def _dedupe_by_sku(self, products: list[dict]) -> list[dict]:
        seen = set()
        unique = []
        for product in products:
            sku = product.get("sku")
            if sku in seen:
                continue
            seen.add(sku)
            unique.append(product)
        return unique

    async def _scrape_all_categories(self) -> tuple[dict, list[dict]]:
        categories = self.config.get("categories", [])

        results = await asyncio.gather(
            *[self._scrape_category(category["id"]) for category in categories]
        )

        category_stats = {}
        all_products = []
        for category, (products, total_count) in zip(categories, results):
            category_stats[category["label"]] = {
                "total_count": total_count,
                "product_count": len(products),
            }
            all_products.extend(products)

        return category_stats, all_products

    async def search(self, search_term: str) -> list[dict]:
        if not search_term.strip():
            _, all_products = await self._scrape_all_categories()
            return all_products

        api_products, _ = await self._smart_search(search_term)
        return self._dedupe_by_sku(self._match_products(api_products, search_term))

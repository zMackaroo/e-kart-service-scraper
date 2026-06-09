from __future__ import annotations

import httpx

PRODUCT_FIELDS = (
    "name sku special_price url_key "
    "price{regularPrice{amount{currency value}}} "
    "price_range{minimum_price{final_price{value currency}}} "
    "small_image{url}"
)


class PriceCompareService:
    GRAPHQL_BASE = "https://smmarkets.ph/graphql"
    SM_PRICE_DROPS = "2398"
    SM_FRESH_MEATS = "660"

    def __init__(self):
        self._client = httpx.AsyncClient(
            timeout=30.0,
            headers={"User-Agent": "e-kart-service/1.0"},
        )

    async def close(self):
        await self._client.aclose()

    def build_query(self, category_id: str, page: int = 1, page_size: int = 24) -> str:
        return (
            f"{{unbxdProducts(filter: {{, category_id: {{eq: \"{category_id}\"}} }}, "
            f"pageSize: {page_size} currentPage: {page} ) "
            f"{{items{{{PRODUCT_FIELDS}}} request_id}}}}"
        )

    async def _fetch_page(self, category_id: str, page: int, page_size: int = 24) -> dict:
        resp = await self._client.get(
            self.GRAPHQL_BASE,
            params={"query": self.build_query(category_id, page, page_size)},
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

    async def scrape_category(self, category_id: str, max_pages: int = 10) -> list[dict]:
        products = []
        for page in range(1, max_pages + 1):
            payload = await self._fetch_page(category_id, page)
            items = payload.get("data", {}).get("unbxdProducts", {}).get("items", [])
            if not items:
                break
            products.extend(self._normalize_item(item) for item in items)
        return products

    async def scrape_all(self) -> dict[str, list[dict]]:
        return {
            "price_drops": await self.scrape_category(self.SM_PRICE_DROPS),
            "fresh_meats": await self.scrape_category(self.SM_FRESH_MEATS),
        }

    def _match_products(self, catalog: list[dict], search_term: str, limit: int = 10) -> list[dict]:
        terms = search_term.lower().split()
        scored = []
        for product in catalog:
            name = (product.get("name") or "").lower()
            if all(term in name for term in terms):
                scored.append(product)
        return scored[:limit]

    async def fetch_price_compare(self, search_term: str):
        catalog = await self.scrape_all()

        all_products = catalog["price_drops"] + catalog["fresh_meats"]
        matches = (
            self._match_products(all_products, search_term)
            if search_term.strip()
            else all_products[:10]
        )

        return {
            "search_term": search_term,
            "total_scraped": {
                "price_drops": len(catalog["price_drops"]),
                "fresh_meats": len(catalog["fresh_meats"]),
            },
            "matches": matches,
        }

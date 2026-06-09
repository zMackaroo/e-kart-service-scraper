from .service import PriceCompareService


async def fetch_price_compare(search_term: str):
    service = PriceCompareService()
    try:
        return await service.fetch_price_compare(search_term)
    finally:
        await service.close()

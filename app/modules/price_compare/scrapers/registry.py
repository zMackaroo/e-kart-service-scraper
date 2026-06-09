from __future__ import annotations

from .base import BaseScraper
from .dali import DaliScraper
from .robinsons import RobinsonsScraper
from .sm_markets import SMMarketsScraper
from .waltermart import WalterMartScraper

SCRAPER_REGISTRY: dict[str, type[BaseScraper]] = {
    "sm_markets": SMMarketsScraper,
    "dali": DaliScraper,
    "waltermart": WalterMartScraper,
    "robinsons": RobinsonsScraper,
}


def get_scraper(scraper_key: str, source_config: dict, client) -> BaseScraper:
    scraper_cls = SCRAPER_REGISTRY.get(scraper_key)
    if scraper_cls is None:
        raise ValueError(f"Unknown scraper: {scraper_key}")
    return scraper_cls(source_config, client)

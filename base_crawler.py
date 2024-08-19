from abc import ABC, abstractmethod
from typing import List, Optional
from urllib.parse import urlparse
from models import CrawlerResult

class BaseCrawler(ABC):
    @abstractmethod
    async def crawl(self, host_url: str, max_links: int, use_sitemap: bool = False, sitemap_urls: Optional[List[str]] = None) -> CrawlerResult:
        pass

    @staticmethod
    def is_valid_url(url: str) -> bool:
        parsed = urlparse(url)
        return parsed.scheme in ('http', 'https') and not parsed.path.startswith('tel:')
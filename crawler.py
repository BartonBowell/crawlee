from web_crawler import WebCrawler
from models import CrawlerResult
from typing import List, Optional

async def crawl_website(host_url: str, max_links: int, use_sitemap: bool = False, sitemap_urls: Optional[List[str]] = None) -> CrawlerResult:
    crawler = WebCrawler()
    return await crawler.crawl(host_url, max_links, use_sitemap, sitemap_urls)
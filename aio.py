import asyncio
import time
import re
import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Optional
from urllib.parse import urljoin, urlparse
from datetime import datetime
from pydantic import BaseModel, Field
from crawlee.playwright_crawler import PlaywrightCrawler, PlaywrightCrawlingContext
from crawlee.autoscaling import ConcurrencySettings
from bs4 import BeautifulSoup
from playwright.async_api import Page
import aiohttp
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Models
class CrawledItem(BaseModel):
    url: str
    title: str
    text_content: str
    date_crawled: datetime = Field(default_factory=datetime.now)

class ProcessedItem(BaseModel):
    url: str
    title: str
    text_content: str
    date_crawled: datetime

class CrawlerResult(BaseModel):
    content: List[ProcessedItem]
    links: List[str]
    unique_initial_urls: List[str]

# Text processing
def clean_text(text: str) -> str:
    text = text.replace('\\n', '\n')
    return re.sub(r'\\u([0-9a-fA-F]{4})', lambda m: chr(int(m.group(1), 16)), text)

def process_crawled_item(item: CrawledItem) -> ProcessedItem:
    return ProcessedItem(
        url=item.url,
        title=clean_text(item.title),
        text_content=clean_text(item.text_content),
        date_crawled=item.date_crawled
    )

# Utilities
async def fetch_sitemap(host_url: str) -> List[str]:
    sitemap_url = urljoin(host_url, 'sitemap.xml')
    logger.info(f"Attempting to fetch sitemap from: {sitemap_url}")
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(sitemap_url) as response:
                if response.status != 200:
                    raise aiohttp.ClientResponseError(
                        response.request_info,
                        response.history,
                        status=response.status,
                        message=f"HTTP error {response.status}"
                    )
                sitemap_content = await response.text()
            
            logger.info(f"Successfully fetched sitemap from: {sitemap_url}")
            
            root = ET.fromstring(sitemap_content)
            
            namespace = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
            
            sitemap_urls = [
                loc.text for loc in root.findall('.//ns:url/ns:loc', namespace)
                if loc is not None and loc.text
            ]
            
            if not sitemap_urls:
                logger.warning("No valid URLs found in the sitemap. Falling back to regular crawling.")
                return []
            
            logger.info(f"Found {len(sitemap_urls)} URLs in the sitemap.")
            return sitemap_urls
        
        except (aiohttp.ClientError, ET.ParseError) as e:
            logger.error(f"Error fetching or parsing sitemap: {e}")
            logger.info("Falling back to regular crawling.")
            return []

# Web Crawler
class WebCrawler:
    @staticmethod
    def is_valid_url(url: str) -> bool:
        parsed = urlparse(url)
        return parsed.scheme in ('http', 'https') and bool(parsed.netloc) and not parsed.path.startswith('tel:')

    async def crawl(self, host_url: str, max_links: int, use_sitemap: bool = False, sitemap_urls: Optional[List[str]] = None) -> CrawlerResult:
        if not self.is_valid_url(host_url):
            raise ValueError(f"Invalid host URL: {host_url}")

        processed_urls: set = set()
        crawled_data: List[CrawledItem] = []
        unique_initial_urls: set = set(sitemap_urls or [])
        is_first_page = not use_sitemap

        concurrency_settings = ConcurrencySettings(desired_concurrency=50)
        crawler = PlaywrightCrawler(
            concurrency_settings=concurrency_settings,
            max_requests_per_crawl=max_links + 1,
        )

        @crawler.router.default_handler
        async def request_handler(context: PlaywrightCrawlingContext) -> None:
            nonlocal is_first_page, unique_initial_urls
            if len(crawled_data) >= max_links:
                return

            current_url = context.request.url
            if current_url in processed_urls:
                return

            logger.info(f'Processing {current_url} ...')

            try:
                html_content = await context.page.content()
                soup = BeautifulSoup(html_content, 'html.parser')
                
                title = soup.title.string if soup.title else "No title"
                
                main_content = soup.find('main') or soup.find('body')
                text_content = main_content.get_text(separator=' ', strip=True) if main_content else ""
                
                crawled_data.append(CrawledItem(
                    url=current_url,
                    title=title,
                    text_content=text_content
                ))

                processed_urls.add(current_url)

                if len(crawled_data) >= max_links:
                    return

                if not use_sitemap:
                    top_containers = await self.find_top_link_containers(context.page)
                    page_urls = await self.extract_valid_urls(top_containers, host_url, processed_urls)

                    if is_first_page:
                        unique_initial_urls.update(page_urls)
                        is_first_page = False

                    for link in page_urls:
                        if len(crawled_data) >= max_links:
                            return
                        if link not in processed_urls:
                            await crawler.add_requests([link])
            except Exception as e:
                logger.error(f"Error processing {current_url}: {str(e)}")

        try:
            if use_sitemap:
                await crawler.run(sitemap_urls[:max_links])
            else:
                await crawler.run([host_url])
        except Exception as e:
            logger.error(f"Error during crawling: {str(e)}")
        
        processed_data = [process_crawled_item(item) for item in crawled_data[:max_links]]
        
        return CrawlerResult(
            content=processed_data,
            links=[item.url for item in processed_data],
            unique_initial_urls=list(unique_initial_urls)
        )

    @staticmethod
    async def find_top_link_containers(page: Page) -> List[Dict[str, Any]]:
        await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
        await page.wait_for_timeout(100)

        return await page.evaluate('''
            () => {
                const elements = Array.from(document.body.getElementsByTagName('*'));
                return elements
                    .filter(el => el.getElementsByTagName('a').length > 0)
                    .map(el => ({
                        selector: el.tagName.toLowerCase() + 
                                (el.id ? '#' + el.id : '') + 
                                (el.className ? '.' + el.className.split(' ').join('.') : ''),
                        linkCount: el.getElementsByTagName('a').length,
                        links: Array.from(el.getElementsByTagName('a')).map(a => a.href)
                    }))
                    .sort((a, b) => b.linkCount - a.linkCount)
                    .slice(0, 3);
            }
        ''')

    async def extract_valid_urls(self, containers: List[Dict[str, Any]], host_url: str, processed_urls: set) -> List[str]:
        valid_urls = []
        host_domain = urlparse(host_url).netloc.replace('www.', '')
        
        for container in containers:
            if 'links' in container and isinstance(container['links'], list):
                for link in container['links']:
                    full_url = urljoin(host_url, link)
                    parsed_url = urlparse(full_url)
                    url_domain = parsed_url.netloc.replace('www.', '')
                    
                    if (url_domain == host_domain or url_domain.endswith('.' + host_domain)) and \
                       full_url not in processed_urls and self.is_valid_url(full_url):
                        valid_urls.append(full_url)
        
        return list(set(valid_urls))

# Main functionality
async def run_crawler_and_process(host_url: str, desired_links: int, use_sitemap: bool = False) -> CrawlerResult:
    sitemap_urls = await fetch_sitemap(host_url) if use_sitemap else []
    use_sitemap = bool(sitemap_urls)
    
    crawler = WebCrawler()
    result = await crawler.crawl(host_url, desired_links, use_sitemap=use_sitemap, sitemap_urls=sitemap_urls)
    
    logger.info(f'Crawling completed. Total pages crawled: {len(result.content)}')
    logger.info(f'Total links collected: {len(result.links)}')
    logger.info(f'Initial URLs found: {len(result.unique_initial_urls)}')

    return result

async def main() -> None:
    start_time = time.time()
    
    host_url = 'https://www.bellevuecollege.edu/'
    desired_links = 25
    use_sitemap = False  # Set this to True to use sitemap crawling

    result = await run_crawler_and_process(host_url, desired_links, use_sitemap)
    
    # Log the results instead of saving to a file
    logger.info("Crawling Results:")
    logger.info(f"Total content items: {len(result.content)}")
    logger.info(f"Total links: {len(result.links)}")
    logger.info(f"Unique initial URLs: {len(result.unique_initial_urls)}")

    # Log a sample of the content (e.g., first 3 items)
    for i, item in enumerate(result.content[:3]):
        logger.info(f"Sample item {i + 1}:")
        logger.info(f"  URL: {item.url}")
        logger.info(f"  Title: {item.title}")
        logger.info(f"  Content preview: {item.text_content[:100]}...")

    end_time = time.time()
    elapsed_time = end_time - start_time
    logger.info(f"Crawling and processing completed. Total execution time: {elapsed_time:.2f} seconds")
    logger.info(f"Sitemap used: {use_sitemap}")

if __name__ == '__main__':
    asyncio.run(main())
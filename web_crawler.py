from typing import List, Dict, Any, Optional
from urllib.parse import urljoin, urlparse
from crawlee.playwright_crawler import PlaywrightCrawler, PlaywrightCrawlingContext
from crawlee.autoscaling import ConcurrencySettings
from bs4 import BeautifulSoup
from playwright.async_api import Page
from base_crawler import BaseCrawler
from models import CrawledItem, CrawlerResult
import logging
from text_processor import process_crawled_item  # Add this import

logger = logging.getLogger(__name__)

class WebCrawler(BaseCrawler):
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
        
        # Process the crawled items
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
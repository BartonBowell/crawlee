import asyncio
import json
from urllib.parse import urlparse, urljoin
from crawlee.playwright_crawler import PlaywrightCrawler, PlaywrightCrawlingContext
from crawlee.autoscaling.autoscaled_pool import ConcurrencySettings
from bs4 import BeautifulSoup
from datetime import datetime

async def crawl_website(host_url: str, max_links: int) -> tuple[list[dict], list[str]]:
    processed_urls = set()
    links_count = 0
    crawled_data = []
    initial_urls = []
    is_first_page = True
    concurrency_settings = ConcurrencySettings(
        desired_concurrency=50
    )
    crawler = PlaywrightCrawler(
        concurrency_settings=concurrency_settings,
        max_requests_per_crawl=max_links * 2,
    )

    async def find_top_link_containers(page):
        await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
        await page.wait_for_timeout(2000)  # Wait for 2 seconds after scrolling

        return await page.evaluate('''
            () => {
                const elements = Array.from(document.body.getElementsByTagName('*'));
                const containers = elements
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
                
                return containers;
            }
        ''')

    def is_valid_url(url):
        parsed = urlparse(url)
        return parsed.scheme in ('http', 'https') and not parsed.path.startswith('tel:')

    @crawler.router.default_handler
    async def request_handler(context: PlaywrightCrawlingContext) -> None:
        nonlocal links_count, is_first_page, initial_urls
        if links_count >= max_links:
            return

        current_url = context.request.url
        if current_url in processed_urls:
            return

        context.log.info(f'Processing {current_url} ...')

        html_content = await context.page.content()
        soup = BeautifulSoup(html_content, 'html.parser')
        
        title = soup.title.string if soup.title else "No title"
        
        main_content = soup.find('main') or soup.find('body')
        text_content = main_content.get_text(separator=' ', strip=True) if main_content else ""
        
        crawled_data.append({
            "url": current_url,
            "title": title,
            "text_content": text_content,
            "date_crawled": datetime.now().isoformat()
        })

        processed_urls.add(current_url)
        links_count += 1

        top_containers = await find_top_link_containers(context.page)

        page_urls = []
        for container in top_containers:
            for link in container['links']:
                full_url = urljoin(host_url, link)
                if full_url.startswith(host_url) and full_url not in processed_urls and is_valid_url(full_url):
                    page_urls.append(full_url)

        if is_first_page:
            initial_urls = page_urls
            with open('initial_urls.json', 'w', encoding='utf-8') as f:
                json.dump({"initial_urls": initial_urls}, f, ensure_ascii=False, indent=2)
            print(f"Initial URLs saved to initial_urls.json")
            is_first_page = False

        for link in page_urls:
            if links_count >= max_links:
                return
            if link not in processed_urls:
                await crawler.add_requests([link])

    await crawler.run([host_url])
    return crawled_data, initial_urls

async def main():
    host_url = 'https://www.nasa.gov/'
    max_links = 20
    crawled_data, initial_urls = await crawl_website(host_url, max_links)
    print(f"Crawling completed. Total pages crawled: {len(crawled_data)}")
    print(f"Initial URLs found: {len(initial_urls)}")

if __name__ == "__main__":
    asyncio.run(main())
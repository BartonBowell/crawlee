import asyncio
import json
import time
from crawler import crawl_website
from text_processor import process_crawled_item
from utils import fetch_sitemap
from models import CrawlerResult

async def run_crawler_and_process(host_url: str, desired_links: int, use_sitemap: bool = False) -> CrawlerResult:
    sitemap_urls = await fetch_sitemap(host_url) if use_sitemap else []
    use_sitemap = bool(sitemap_urls)
    
    result = await crawl_website(host_url, desired_links, use_sitemap=use_sitemap, sitemap_urls=sitemap_urls)
    
    print(f'Crawling completed. Total pages crawled: {len(result.content)}')
    print(f'Initial URLs found: {len(result.initial_urls)}')

    result.content = [process_crawled_item(item) for item in result.content]
    
    print(f'Total links collected: {len(result.links)}')

    return result

def save_output(data: CrawlerResult, filename: str = 'final_output.json') -> None:
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data.model_dump(), f, ensure_ascii=False, indent=2, default=str)
    print(f'Results saved to {filename}')

async def main() -> None:
    start_time = time.time()
    
    host_url = 'https://nextjs.org/'
    desired_links = 25
    use_sitemap = False  # Set this to True to use sitemap crawling

    result = await run_crawler_and_process(host_url, desired_links, use_sitemap)
    
    save_output(result)

    end_time = time.time()
    elapsed_time = end_time - start_time
    print(f"Crawling and processing completed. Total content items: {len(result.content)}")
    print(f"Total execution time: {elapsed_time:.2f} seconds")
    print(f"Sitemap used: {use_sitemap}")

if __name__ == '__main__':
    asyncio.run(main())
import asyncio
import json
import time
from crawler import crawl_website
from text_extractor import process_crawled_data, remove_url_by_index

async def run_crawler_and_process(host_url: str, desired_links: int):
    # Crawl the website
    crawled_data, initial_urls = await crawl_website(host_url, desired_links)
    print(f'Crawling completed. Total pages crawled: {len(crawled_data)}')
    print(f'Initial URLs found: {len(initial_urls)}')

    # Process the crawled data
    processed_data = process_crawled_data(crawled_data)
    
    # Extract links for separate handling
    links = [item['url'] for item in processed_data]
    print(f'Total links collected: {len(links)}')

    return {
        "content": processed_data,
        "links": links,
        "initial_urls": initial_urls
    }

def remove_url_and_update(data, index_to_remove):
    if index_to_remove is not None and 0 <= index_to_remove < len(data['links']):
        updated_links, removed_url = remove_url_by_index(data['links'], index_to_remove)
        if removed_url:
            print(f"Removed URL: {removed_url}")
            print(f"Number of remaining URLs: {len(updated_links)}")
            # Remove the corresponding item from processed_data
            data['content'] = [item for item in data['content'] if item['url'] != removed_url]
            data['links'] = updated_links
    return data

def save_output(data, filename='final_output.json'):
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f'Results saved to {filename}')

async def main():
    start_time = time.time()
    
    host_url = 'https://www.linkedin.com/pulse/topics/home/?trk=guest_homepage-basic_guest_nav_menu_articles'
    #host_url = 'https://www.portofsandiego.org/'
    desired_links = 25

    # Run the crawler and process the data
    result = await run_crawler_and_process(host_url, desired_links)
    
    # Optionally remove a URL (uncomment the next line to use this feature)
    # result = remove_url_and_update(result, index_to_remove=5)

    # Save the final output
    save_output(result)

    end_time = time.time()
    elapsed_time = end_time - start_time
    print(f"Crawling and processing completed. Total content items: {len(result['content'])}")
    print(f"Total execution time: {elapsed_time:.2f} seconds")

if __name__ == '__main__':
    asyncio.run(main())
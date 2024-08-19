from typing import List, Optional, Tuple
from models import ProcessedItem
import xml.etree.ElementTree as ET
import aiohttp
from urllib.parse import urljoin

async def remove_url_by_index(data: List[ProcessedItem], index: int) -> Tuple[List[ProcessedItem], Optional[ProcessedItem]]:
    if 0 <= index < len(data):
        removed_item = data.pop(index)
        return data, removed_item
    else:
        print(f"Index {index} is out of range. No URL removed.")
        return data, None

async def fetch_sitemap(host_url: str) -> List[str]:
    sitemap_url = urljoin(host_url, 'sitemap.xml')
    print(f"Attempting to fetch sitemap from: {sitemap_url}")
    
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
            
            print(f"Successfully fetched sitemap from: {sitemap_url}")
            
            root = ET.fromstring(sitemap_content)
            
            namespace = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
            
            sitemap_urls = [
                loc.text for loc in root.findall('.//ns:url/ns:loc', namespace)
                if loc is not None and loc.text
            ]
            
            if not sitemap_urls:
                print("No valid URLs found in the sitemap. Falling back to regular crawling.")
                return []
            
            print(f"Found {len(sitemap_urls)} URLs in the sitemap.")
            return sitemap_urls
        
        except (aiohttp.ClientError, ET.ParseError) as e:
            print(f"Error fetching or parsing sitemap: {e}")
            print("Falling back to regular crawling.")
            return []
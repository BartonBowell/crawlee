import re
from models import CrawledItem, ProcessedItem

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
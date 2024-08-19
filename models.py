from dataclasses import dataclass, field
from datetime import datetime
from typing import List

@dataclass
class CrawledItem:
    url: str
    title: str
    text_content: str
    date_crawled: datetime = field(default_factory=datetime.now)

@dataclass
class ProcessedItem:
    url: str
    title: str
    text_content: str
    date_crawled: datetime

@dataclass
class CrawlerResult:
    content: List[CrawledItem]
    links: List[str]
    initial_urls: List[str]
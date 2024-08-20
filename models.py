from pydantic import BaseModel, Field
from datetime import datetime
from typing import List

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
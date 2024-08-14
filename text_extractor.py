import re

def clean_text(text):
    text = text.replace('\\n', '\n')
    text = re.sub(r'\\u([0-9a-fA-F]{4})', lambda m: chr(int(m.group(1), 16)), text)
    return text

def process_crawled_data(crawled_data: list[dict]) -> list[dict]:
    processed_data = []
    for item in crawled_data:
        cleaned_text = clean_text(item['text_content'])
        
        processed_item = {
            "url": item['url'],
            "title": clean_text(item['title']),
            "date_crawled": item['date_crawled'],
            "text_content": cleaned_text
        }
        processed_data.append(processed_item)
    
    return processed_data

def remove_url_by_index(data, index):
    if 0 <= index < len(data):
        removed_item = data.pop(index)
        return data, removed_item
    else:
        print(f"Index {index} is out of range. No URL removed.")
        return data, None
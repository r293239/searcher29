import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin
import re
import math
import time
import json
from collections import defaultdict

# ===== YOUR BACK4APP KEYS =====
PARSE_APP_ID = "qXJqQ3HWKYsGVB1oQKnYZo7zdNLHgjZMiwonhozr"
PARSE_REST_KEY = "mdTfymJLDHJY46HUv0tgKtWkqMm4YHQEbdsPX8tJ"
PARSE_URL = "https://parseapi.back4app.com"

HEADERS = {
    "X-Parse-Application-Id": PARSE_APP_ID,
    "X-Parse-REST-API-Key": PARSE_REST_KEY,
    "Content-Type": "application/json"
}
# ==============================

class Crawler:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "Mozilla/5.0 (compatible; SearchBot/1.0)"})
    
    def fetch(self, url):
        """Download and parse a webpage"""
        resp = self.session.get(url, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')
        title = soup.title.string.strip() if soup.title else url
        text = soup.get_text(separator=' ', strip=True)[:10000]
        links = []
        for a in soup.find_all('a', href=True):
            full = urljoin(url, a['href'])
            if full.startswith('http'):
                links.append(full)
        return {"url": url, "title": title, "text": text, "links": links[:20]}
    
    def crawl(self, start_urls, max_pages=50):
        """BFS crawl from seed URLs"""
        visited = set()
        queue = list(start_urls)
        pages = []
        
        while queue and len(pages) < max_pages:
            url = queue.pop(0)
            if url in visited:
                continue
            visited.add(url)
            try:
                page = self.fetch(url)
                pages.append(page)
                queue.extend(page['links'])
                print(f"✓ [{len(pages)}/{max_pages}] {url}")
                time.sleep(1)
            except Exception as e:
                print(f"✗ {url}: {e}")
        return pages


class Indexer:
    def __init__(self):
        self.stopwords = {
            "the","a","an","is","are","was","were","be","been","being",
            "have","has","had","do","does","did","will","would","shall",
            "should","may","might","must","can","could","of","in","to",
            "for","with","on","at","by","from","and","or","not","but",
            "if","then","else","when","where","why","how","all","any",
            "both","each","few","more","most","other","some","such","no",
            "only","own","same","so","than","too","very","this","that",
            "it","its","he","she","they","them","these","those","i","my",
            "your","we","our","you","me","us","him","his","her","their"
        }
    
    def tokenize(self, text):
        """Split text into words, filter stopwords"""
        words = re.findall(r'\b[a-zA-Z]{2,}\b', text.lower())
        return [w for w in words if w not in self.stopwords]
    
    def build_index(self, pages):
        """Build inverted index with TF-IDF"""
        N = len(pages)
        
        doc_tokens = {}
        doc_urls = []
        for i, page in enumerate(pages):
            tokens = self.tokenize(page['text'])
            doc_tokens[i] = tokens
            doc_urls.append(page['url'])
        
        # Document frequency
        df = defaultdict(int)
        for tokens in doc_tokens.values():
            for word in set(tokens):
                df[word] += 1
        
        # Build inverted index
        index = {}
        for i, tokens in doc_tokens.items():
            tf = defaultdict(int)
            for w in tokens:
                tf[w] += 1
            max_tf = max(tf.values()) if tf else 1
            
            for word, count in tf.items():
                if word not in index:
                    index[word] = {}
                tf_norm = count / max_tf
                idf = math.log((N - df[word] + 0.5) / (df[word] + 0.5) + 1)
                index[word][str(i)] = round(tf_norm * idf, 4)
        
        return {
            "index": index,
            "urls": doc_urls,
            "titles": [p['title'] for p in pages],
            "snippets": [p['text'][:300] for p in pages],
            "doc_count": N,
            "timestamp": time.time()
        }
    
    def save_to_back4app(self, index_data):
        """Save index to Back4App"""
        payload = {
            "data": json.dumps(index_data),
            "docCount": index_data["doc_count"],
            "timestamp": int(index_data["timestamp"])
        }
        resp = requests.post(f"{PARSE_URL}/classes/Index", json=payload, headers=HEADERS)
        if resp.status_code in [200, 201]:
            print(f"✅ Index saved!")
            return True
        else:
            print(f"❌ Failed: {resp.json()}")
            return False


def get_queue():
    """Get pending URLs from CrawlQueue"""
    where = json.dumps({"status": "pending"})
    resp = requests.get(
        f"{PARSE_URL}/classes/CrawlQueue",
        params={"where": where, "limit": 10},
        headers=HEADERS
    )
    if resp.status_code == 200:
        results = resp.json().get('results', [])
        return [item['url'] for item in results]
    return []


def clear_queue():
    """Delete crawled queue items"""
    where = json.dumps({"status": "pending"})
    resp = requests.get(
        f"{PARSE_URL}/classes/CrawlQueue",
        params={"where": where},
        headers=HEADERS
    )
    if resp.status_code == 200:
        for item in resp.json().get('results', []):
            requests.delete(
                f"{PARSE_URL}/classes/CrawlQueue/{item['objectId']}",
                headers=HEADERS
            )


def main():
    crawler = Crawler()
    indexer = Indexer()
    
    # Get URLs from queue or use defaults
    seeds = get_queue()
    if not seeds:
        seeds = [
            "https://en.wikipedia.org/wiki/Search_engine",
            "https://en.wikipedia.org/wiki/Web_crawler",
            "https://developer.mozilla.org/en-US/",
            "https://www.python.org/",
            "https://github.com/"
        ]
        print("Using default seed URLs")
    
    print(f"🕷️ Crawling {len(seeds)} seeds, max 30 pages...")
    pages = crawler.crawl(seeds, max_pages=30)
    
    if pages:
        print(f"\n📊 Building index from {len(pages)} pages...")
        index = indexer.build_index(pages)
        print(f"Unique terms: {len(index['index'])}")
        
        print("💾 Saving to Back4App...")
        if indexer.save_to_back4app(index):
            clear_queue()
            print("✅ All done! Search engine index updated.")
    else:
        print("❌ No pages crawled.")


if __name__ == "__main__":
    main()

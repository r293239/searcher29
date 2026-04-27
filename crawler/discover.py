import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin
import time
import json
import random

PARSE_APP_ID = "qXJqQ3HWKYsGVB1oQKnYZo7zdNLHgjZMiwonhozr"
PARSE_REST_KEY = "mdTfymJLDHJY46HUv0tgKtWkqMm4YHQEbdsPX8tJ"
PARSE_URL = "https://parseapi.back4app.com"

HEADERS = {
    "X-Parse-Application-Id": PARSE_APP_ID,
    "X-Parse-REST-API-Key": PARSE_REST_KEY,
    "Content-Type": "application/json"
}

# Seeds are a fallback - we primarily use existing index + discovered links
FALLBACK_SEEDS = [
    "https://en.wikipedia.org/wiki/Special:Random",
    "https://news.ycombinator.com/",
    "https://www.bbc.com/news",
    "https://developer.mozilla.org/en-US/",
    "https://www.freecodecamp.org/news/",
    "https://dev.to/",
    "https://stackoverflow.com/questions?tab=hot",
    "https://github.com/trending",
    "https://arstechnica.com/",
    "https://techcrunch.com/",
    "https://www.theverge.com/",
    "https://www.wired.com/",
    "https://www.nature.com/news/",
    "https://www.sciencedaily.com/",
    "https://medium.com/tag/technology",
]

class DiscoverCrawler:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "Mozilla/5.0 (compatible; DiscoverBot/1.0)"})
    
    def fetch(self, url):
        """Fetch a page, return title + new links"""
        resp = self.session.get(url, timeout=15, allow_redirects=True)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')
        final_url = resp.url
        
        title = None
        if soup.title and soup.title.string:
            title = soup.title.string.strip()
        if not title:
            og = soup.find('meta', property='og:title')
            if og: title = og.get('content', '').strip()
        if not title: title = final_url
        
        # Extract links - prioritize internal links (same domain)
        domain = urlparse(final_url).netloc
        internal_links = []
        external_links = []
        
        for a in soup.find_all('a', href=True):
            full = urljoin(final_url, a['href'])
            parsed = urlparse(full)
            if parsed.scheme not in ('http', 'https'):
                continue
            path_lower = parsed.path.lower()
            if any(path_lower.endswith(ext) for ext in ['.jpg','.jpeg','.png','.gif','.svg','.css','.js','.pdf','.zip','.mp4','.mp3','.ico','.woff','.woff2']):
                continue
            if parsed.netloc == domain:
                internal_links.append(full)
            else:
                external_links.append(full)
        
        # Mix: 5 internal + 3 external
        links = (internal_links[:5] + external_links[:3])
        return {"url": final_url, "title": title, "links": links}
    
    def get_crawled_urls(self):
        """Get all URLs already in the index"""
        resp = requests.get(f"{PARSE_URL}/classes/Index", params={"order": "-createdAt", "limit": 1}, headers=HEADERS)
        if resp.status_code == 200:
            results = resp.json().get('results', [])
            if results and results[0].get('data'):
                try:
                    index_data = json.loads(results[0]['data'])
                    return set(index_data.get('urls', []))
                except: pass
        return set()
    
    def get_queue_urls(self):
        """Get URLs already pending in queue"""
        where = json.dumps({"status": "pending"})
        resp = requests.get(f"{PARSE_URL}/classes/CrawlQueue", params={"where": where, "limit": 200}, headers=HEADERS)
        if resp.status_code == 200:
            return set(item['url'] for item in resp.json().get('results', []))
        return set()
    
    def queue_url(self, url):
        """Add URL to crawl queue"""
        resp = requests.post(f"{PARSE_URL}/classes/CrawlQueue", json={"url": url, "status": "pending"}, headers=HEADERS)
        return resp.status_code in [200, 201]
    
    def pick_seed_from_index(self, crawled, queue_urls):
        """Pick random URLs from existing index to crawl deeper"""
        if len(crawled) < 5:
            return []
        
        # Pick 3 random URLs from the index
        crawled_list = list(crawled)
        picks = random.sample(crawled_list, min(3, len(crawled_list)))
        
        new_seeds = []
        for url in picks:
            try:
                page = self.fetch(url)
                for link in page['links']:
                    if link not in crawled and link not in queue_urls and link not in new_seeds:
                        new_seeds.append(link)
                        if len(new_seeds) >= 5:
                            break
                time.sleep(0.5)
            except Exception as e:
                print(f"  ⚠ Error re-crawling {url[:60]}: {e}")
        
        return new_seeds
    
    def discover(self):
        crawled = self.get_crawled_urls()
        queue_urls = self.get_queue_urls()
        all_known = crawled | queue_urls
        
        print(f"📚 {len(crawled)} pages indexed | {len(queue_urls)} in queue")
        
        new_found = 0
        max_new = 25  # Increased from 10
        
        # STRATEGY 1: Re-crawl existing index pages to find new links
        print("\n🔍 Strategy 1: Mining existing index for new links...")
        mined_seeds = self.pick_seed_from_index(crawled, all_known)
        for url in mined_seeds[:5]:
            if new_found >= max_new: break
            if url not in all_known:
                if self.queue_url(url):
                    print(f"  ✓ [mined] {url[:100]}")
                    all_known.add(url)
                    new_found += 1
        
        # STRATEGY 2: Crawl a couple fallback seeds
        print(f"\n🌐 Strategy 2: Exploring {min(2, len(FALLBACK_SEEDS))} fresh seeds...")
        seeds = random.sample(FALLBACK_SEEDS, min(2, len(FALLBACK_SEEDS)))
        for seed_url in seeds:
            if new_found >= max_new: break
            try:
                page = self.fetch(seed_url)
                # Queue the seed itself
                if page['url'] not in all_known:
                    if self.queue_url(page['url']):
                        print(f"  ✓ [seed] {page['title'][:80]}")
                        all_known.add(page['url'])
                        new_found += 1
                # Queue its links
                for link in page['links']:
                    if new_found >= max_new: break
                    if link not in all_known:
                        if self.queue_url(link):
                            print(f"  ✓ [link] {link[:100]}")
                            all_known.add(link)
                            new_found += 1
                time.sleep(1)
            except Exception as e:
                print(f"  ✗ {seed_url[:60]}: {e}")
        
        # STRATEGY 3: If we still have room, add Wikipedia random pages
        if new_found < 5:
            print(f"\n🎲 Strategy 3: Random Wikipedia pages...")
            for _ in range(3):
                if new_found >= max_new: break
                try:
                    url = "https://en.wikipedia.org/wiki/Special:Random"
                    page = self.fetch(url)
                    if page['url'] not in all_known:
                        if self.queue_url(page['url']):
                            print(f"  ✓ [wiki] {page['title'][:80]}")
                            all_known.add(page['url'])
                            new_found += 1
                    time.sleep(0.5)
                except Exception as e:
                    print(f"  ✗ Wiki: {e}")
        
        print(f"\n✅ Discovery done! {new_found} new URLs queued.")
        if new_found > 0:
            print("💡 Crawler will index these next run.")
        else:
            print("📭 Nothing new found. Index is growing nicely!")

if __name__ == "__main__":
    DiscoverCrawler().discover()

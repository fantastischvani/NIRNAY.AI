import json
import time
import requests
import threading  # <--- NEW IMPORT: Needed to fix the error
from abc import ABC, abstractmethod
from typing import List, Dict, Optional
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from app.config.settings import settings

# Configuration constants
PH_API_TOKEN = settings.PH_API_TOKEN  
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"

class BaseConnector(ABC):
    @abstractmethod
    def fetch_signals(self, query: str, limit: int = 5) -> List:
        pass

class YCombinatorConnector(BaseConnector):
    """
    Implements the 'Scroll and Wait' pattern to harvest YC Company data.
    FIXED: Now wraps the synchronous Playwright code in a separate thread 
    to avoid crashing the main AsyncIO event loop.
    """
    def fetch_signals(self, query: str, limit: int = 10) -> List:
        results = []
        error = None

        # --- INTERNAL FUNCTION: This contains your original scraping logic ---
        def run_scrape():
            nonlocal results, error
            try:
                with sync_playwright() as p:
                    browser = p.chromium.launch(headless=True,slow_mo=1000)
                    page = browser.new_page(user_agent=USER_AGENT)
                    
                    url = f"https://www.ycombinator.com/companies?q={query}"
                    print(f"DEBUG: Scraping YC URL: {url}")
                    page.goto(url)
                    
                    # Infinite Scroll Logic
                    previous_height = 0
                    while len(results) < limit:
                        # Extract cards currently in DOM
                        company_cards = page.locator('a._company_86jzd_338').all()
                        
                        if not company_cards:
                            company_cards = page.locator('a[href^="/companies/"]').all()

                        for card in company_cards:
                            if len(results) >= limit: 
                                break
                            
                            try:
                                name = card.locator('.coName').first.text_content()
                                desc = card.locator('.coDescription').first.text_content()
                                # Safe check for batch
                                if card.locator('.coBatch').count() > 0:
                                    batch = card.locator('.coBatch').first.text_content()
                                else:
                                    batch = "Unknown"
                                
                                # Deduping check
                                if not any(r['name'] == name for r in results):
                                    results.append({
                                        "source": "Y Combinator",
                                        "type": "supply_signal",
                                        "name": name,
                                        "description": desc,
                                        "batch": batch,
                                        "url": f"https://www.ycombinator.com{card.get_attribute('href')}"
                                    })
                            except Exception:
                                continue

                        # Scroll down
                        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                        page.wait_for_timeout(2000) 
                        
                        new_height = page.evaluate("document.body.scrollHeight")
                        if new_height == previous_height:
                            break 
                        previous_height = new_height
                    
                    browser.close()
            except Exception as e:
                error = e
        # -------------------------------------------------------------------

        # --- THE FIX: Run the scraper in a separate thread ---
        # This tricks Python into thinking the scraping is happening "elsewhere",
        # so it doesn't block the main Async Event Loop.
        t = threading.Thread(target=run_scrape)
        t.start()
        t.join()  # We wait here for the thread to finish
        
        if error:
            print(f"Error scraping YC: {error}")
            return []

        return results

class ProductHuntConnector(BaseConnector):
    """
    Implements GraphQL v2 API to fetch high-velocity launches.
    """
    def fetch_signals(self, query: str, limit: int = 5) -> List:
        # Check if token is missing or default
        if not PH_API_TOKEN or PH_API_TOKEN == "YOUR_PRODUCT_HUNT_DEVELOPER_TOKEN":
            print("Warning: Product Hunt API Token missing.")
            return []

        url = "https://api.producthunt.com/v2/api/graphql"
        headers = {"Authorization": f"Bearer {PH_API_TOKEN}"}
        
        graphql_query = """
        {
          posts(first: %d, order: VOTES_COUNT) {
            edges {
              node {
                name
                tagline
                description
                votesCount
                commentsCount
                website
                topics {
                  edges {
                    node {
                      name
                    }
                  }
                }
              }
            }
          }
        }
        """ % limit

        try:
            response = requests.post(url, json={'query': graphql_query}, headers=headers)
            if response.status_code != 200:
                print(f"Product Hunt API Error: {response.status_code}")
                return []

            data = response.json().get('data', {}).get('posts', {}).get('edges', [])
            normalized = []
            
            for edge in data:
                node = edge['node']
                topics = [t['node']['name'] for t in node['topics']['edges']]
                normalized.append({
                    "source": "Product Hunt",
                    "type": "market_velocity",
                    "name": node['name'],
                    "pitch": node['tagline'],
                    "metrics": f"{node['votesCount']} votes, {node['commentsCount']} comments",
                    "tags": topics,
                    "url": node['website']
                })
            return normalized
        except Exception as e:
            print(f"Product Hunt connection failed: {e}")
            return []

class DevpostConnector(BaseConnector):
    """
    Scrapes 'Built With' tags to identify Technical Momentum.
    """
    def fetch_signals(self, query: str, limit: int = 5) -> List:
        search_url = f"https://devpost.com/software/search?query={query}"
        try:
            resp = requests.get(search_url, headers={'User-Agent': USER_AGENT})
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            projects = []
            # Selector might need maintenance as Devpost updates UI
            project_links = [a['href'] for a in soup.select('.link-to-software')][:limit]
            
            for link in project_links:
                try:
                    p_resp = requests.get(link, headers={'User-Agent': USER_AGENT})
                    p_soup = BeautifulSoup(p_resp.text, 'html.parser')
                    
                    title = p_soup.select_one('#app-title').text.strip() if p_soup.select_one('#app-title') else "Unknown"
                    tagline = p_soup.select_one('.large.mb-4').text.strip() if p_soup.select_one('.large.mb-4') else ""
                    
                    built_with = [li.text.strip() for li in p_soup.select('#built-with li')]
                    
                    projects.append({
                        "source": "Devpost",
                        "type": "technical_signal",
                        "name": title,
                        "tagline": tagline,
                        "tech_stack": built_with,
                        "url": link
                    })
                except Exception:
                    continue
            return projects
        except Exception as e:
            print(f"Devpost scraping failed: {e}")
            return []

class RedditDorkGenerator(BaseConnector):
    """
    Generates 'Google Dork' URLs for high-intent social listening.
    """
    def fetch_signals(self, query: str, limit: int = 5) -> List:
        dorks = [
            {"source": "Reddit", "type": "social_signal", "dork": f'site:reddit.com "{query}" "I hate doing"'},
            {"source": "Reddit", "type": "social_signal", "dork": f'site:reddit.com "{query}" "alternative to"'},
            {"source": "Reddit", "type": "social_signal", "dork": f'site:reddit.com "{query}" "willing to pay"'},
            {"source": "Reddit", "type": "social_signal", "dork": f'site:reddit.com "{query}" "why isn\'t there a"'},
        ]
        return dorks

def market_intel_search(query: str, sources: List[str] = ["yc", "ph", "devpost", "reddit"]):
    """
    The Orchestrator function to be called by the Agent.
    """
    aggregator = []
    
    if "yc" in sources:
        aggregator.extend(YCombinatorConnector().fetch_signals(query))
    if "ph" in sources:
        aggregator.extend(ProductHuntConnector().fetch_signals(query))
    if "devpost" in sources:
        aggregator.extend(DevpostConnector().fetch_signals(query))
    if "reddit" in sources:
        aggregator.extend(RedditDorkGenerator().fetch_signals(query))
        
    return json.dumps(aggregator, indent=2)

def search_all(query: str, limit: int = 5, types: Optional[List[str]] = None) -> List[Dict]:
    """
    Unified search function that coordinates all connector classes.
    """
    aggregator = []
    
    # 1. YC (Now Thread-Safe)
    aggregator.extend(YCombinatorConnector().fetch_signals(query, limit=limit))
    
    # 2. Product Hunt
    aggregator.extend(ProductHuntConnector().fetch_signals(query, limit=limit))
    
    # 3. Devpost
    aggregator.extend(DevpostConnector().fetch_signals(query, limit=limit))
    
    # 4. Reddit
    aggregator.extend(RedditDorkGenerator().fetch_signals(query, limit=limit))
    
    # Filter by types if provided
    if types:
        aggregator = [item for item in aggregator if item.get("type") in types]
    
    return aggregator

# --- Tool Definition ---
tools = [
    {
        "type": "function",
        "function": {
            "name": "market_intel_search",
            "description": "Search for market intelligence signals across multiple sources (YC, Product Hunt, Devpost, Reddit).",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The market/product/technology query to search for."
                    },
                    "sources": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Specific data silos to mine."
                    }
                },
                "required": ["query"]
            }
        }
    }
]
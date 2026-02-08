"""
Web Scraping News Client for Financial News
Scrapes from reliable financial news sources instead of using APIs
"""
import asyncio
import aiohttp
import time
import random
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
from bs4 import BeautifulSoup
import re

# Financial news sources to scrape
NEWS_SOURCES = {
    "investing_com": {
        "base_url": "https://www.investing.com",
        "search_paths": {
            "XAU": "/commodities/gold-news",
            "XAG": "/commodities/silver-news", 
            "US100": "/indices/nasdaq-100-news"
        }
    },
    "marketwatch": {
        "base_url": "https://www.marketwatch.com",
        "search_paths": {
            "XAU": "/investing/currency/gc00",
            "XAG": "/investing/currency/si00",
            "US100": "/investing/index/nasdaq-composite"
        }
    },
    "yahoo_finance": {
        "base_url": "https://finance.yahoo.com",
        "search_paths": {
            "XAU": "/quote/XAU/news",
            "XAG": "/quote/XAG/news", 
            "US100": "/quote/US100/news"
        }
    }
}

BULLISH_KEYWORDS = [
    "surge", "rally", "jump", "soar", "spike", "gain", "rise", "up", "higher",
    "bullish", "breakout", "momentum", "strong", "growth", "profit", "beat",
    "outperform", "upgrade", "positive", "optimism", "record", "peak"
]

BEARISH_KEYWORDS = [
    "crash", "drop", "fall", "decline", "plunge", "tumble", "down", "lower",
    "bearish", "breakdown", "weak", "loss", "miss", "underperform", "downgrade",
    "negative", "concern", "risk", "volatile", "uncertainty", "fear"
]

class WebScrapingNewsClient:
    def __init__(self):
        self.session = None
        self.cache = {}
        self.cache_time = {}
        self.cache_ttl = 180  # Cache for 3 minutes
        self.last_request = 0
        self.min_delay = 0.5  # 500ms between requests to be respectful
        
    async def _get_session(self):
        """Get or create aiohttp session with SSL handling"""
        if self.session is None or self.session.closed:
            # Create SSL context that handles certificates more leniently for scraping
            ssl_context = False  # Disable SSL verification for scraping (be careful with this)
            
            connector = aiohttp.TCPConnector(ssl=ssl_context)
            
            self.session = aiohttp.ClientSession(
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.5',
                    'Accept-Encoding': 'gzip, deflate',
                    'Connection': 'keep-alive',
                },
                connector=connector,
                timeout=aiohttp.ClientTimeout(total=10)
            )
        return self.session
    
    async def _rate_limit(self):
        """Respectful rate limiting"""
        elapsed = time.time() - self.last_request
        if elapsed < self.min_delay:
            await asyncio.sleep(self.min_delay - elapsed)
        self.last_request = time.time()
    
    def _calculate_sentiment(self, text: str) -> tuple[float, str]:
        """Calculate sentiment from text"""
        if not text:
            return 0.0, "neutral"
            
        text_lower = text.lower()
        
        bullish_count = sum(1 for word in BULLISH_KEYWORDS if word in text_lower)
        bearish_count = sum(1 for word in BEARISH_KEYWORDS if word in text_lower)
        
        total_keywords = bullish_count + bearish_count
        if total_keywords == 0:
            return 0.0, "neutral"
        
        # Calculate sentiment score
        sentiment = (bullish_count - bearish_count) / total_keywords
        
        if sentiment > 0.2:
            direction = "buy"
        elif sentiment < -0.2:
            direction = "sell"
        else:
            direction = "neutral"
        
        return sentiment, direction
    
    def _extract_date(self, text: str) -> str:
        """Extract or generate publication date"""
        # Look for common date patterns
        date_patterns = [
            r'(\d{1,2})\s+(hours?|minutes?|days?)\s+ago',
            r'(\d{4}-\d{2}-\d{2})',
            r'(\d{1,2}/\d{1,2}/\d{4})'
        ]
        
        for pattern in date_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return datetime.now().isoformat()
        
        # Default to current time
        return datetime.now().isoformat()
    
    async def _scrape_investing_com(self, symbol: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Scrape from Investing.com"""
        try:
            session = await self._get_session()
            await self._rate_limit()
            
            path = NEWS_SOURCES["investing_com"]["search_paths"][symbol]
            url = f"{NEWS_SOURCES['investing_com']['base_url']}{path}"
            
            async with session.get(url) as response:
                if response.status != 200:
                    return []
                
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')
                
                news = []
                # Look for article headlines and content
                articles = soup.find_all('article')[:limit] or soup.find_all(class_=re.compile('article|news-item|headline'))[:limit]
                
                for article in articles:
                    # Extract headline
                    headline_elem = article.find(['h1', 'h2', 'h3', 'h4']) or article.find(class_=re.compile('title|headline'))
                    if not headline_elem:
                        continue
                    
                    headline = headline_elem.get_text(strip=True)
                    if not headline or len(headline) < 20:
                        continue
                    
                    # Extract source/date
                    source_elem = article.find(class_=re.compile('source|author|date')) or article.find('span')
                    source = source_elem.get_text(strip=True) if source_elem else "Investing.com"
                    
                    # Calculate sentiment
                    sentiment, direction = self._calculate_sentiment(headline)
                    
                    # Calculate importance based on sentiment strength and headline length
                    importance = min(1.0, (abs(sentiment) * 0.6) + (min(len(headline), 100) / 200) + 0.2)
                    
                    news.append({
                        "headline": headline[:120],
                        "sentiment": sentiment,
                        "direction": direction,
                        "importance": importance,
                        "source": source[:30],
                        "url": url,
                        "published": self._extract_date(str(article))
                    })
                
                return news
                
        except Exception as e:
            print(f"Error scraping Investing.com for {symbol}: {e}")
            return []
    
    async def _scrape_marketwatch(self, symbol: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Scrape from MarketWatch"""
        try:
            session = await self._get_session()
            await self._rate_limit()
            
            # Use MarketWatch search functionality
            search_query = f"{symbol} news"
            url = f"{NEWS_SOURCES['marketwatch']['base_url']}/search?q={search_query}"
            
            async with session.get(url) as response:
                if response.status != 200:
                    return []
                
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')
                
                news = []
                # Look for news articles in search results
                articles = soup.find_all('div', class_=re.compile('article|story|news'))[:limit]
                
                for article in articles:
                    headline_elem = article.find('h3') or article.find('a')
                    if not headline_elem:
                        continue
                    
                    headline = headline_elem.get_text(strip=True)
                    if not headline or len(headline) < 20:
                        continue
                    
                    sentiment, direction = self._calculate_sentiment(headline)
                    importance = min(1.0, (abs(sentiment) * 0.6) + 0.3)
                    
                    news.append({
                        "headline": headline[:120],
                        "sentiment": sentiment,
                        "direction": direction,
                        "importance": importance,
                        "source": "MarketWatch",
                        "url": url,
                        "published": datetime.now().isoformat()
                    })
                
                return news
                
        except Exception as e:
            print(f"Error scraping MarketWatch for {symbol}: {e}")
            return []
    
    async def _scrape_yahoo_finance(self, symbol: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Scrape from Yahoo Finance"""
        try:
            session = await self._get_session()
            await self._rate_limit()
            
            path = NEWS_SOURCES["yahoo_finance"]["search_paths"][symbol]
            url = f"{NEWS_SOURCES['yahoo_finance']['base_url']}{path}"
            
            async with session.get(url) as response:
                if response.status != 200:
                    return []
                
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')
                
                news = []
                # Look for news articles
                articles = soup.find_all('li', class_=re.compile('news-item|article'))[:limit]
                
                for article in articles:
                    headline_elem = article.find('h3') or article.find('a')
                    if not headline_elem:
                        continue
                    
                    headline = headline_elem.get_text(strip=True)
                    if not headline or len(headline) < 20:
                        continue
                    
                    sentiment, direction = self._calculate_sentiment(headline)
                    importance = min(1.0, (abs(sentiment) * 0.6) + 0.3)
                    
                    news.append({
                        "headline": headline[:120],
                        "sentiment": sentiment,
                        "direction": direction,
                        "importance": importance,
                        "source": "Yahoo Finance",
                        "url": url,
                        "published": datetime.now().isoformat()
                    })
                
                return news
                
        except Exception as e:
            print(f"Error scraping Yahoo Finance for {symbol}: {e}")
            return []
    
    async def get_news(self, symbol: str, limit: int = 5) -> Optional[List[Dict[str, Any]]]:
        """
        Get news by scraping multiple sources
        """
        # Check cache first
        cache_key = f"{symbol}_{limit}"
        if cache_key in self.cache:
            if time.time() - self.cache_time.get(cache_key, 0) < self.cache_ttl:
                print(f"Using cached news for {symbol}")
                return self.cache[cache_key]
        
        # Try scraping from multiple sources
        all_news = []
        
        # Try Investing.com first
        investing_news = await self._scrape_investing_com(symbol, limit)
        if investing_news:
            all_news.extend(investing_news)
        
        # If we need more news, try MarketWatch
        if len(all_news) < limit:
            marketwatch_news = await self._scrape_marketwatch(symbol, limit - len(all_news))
            if marketwatch_news:
                all_news.extend(marketwatch_news)
        
        # If we still need more news, try Yahoo Finance
        if len(all_news) < limit:
            yahoo_news = await self._scrape_yahoo_finance(symbol, limit - len(all_news))
            if yahoo_news:
                all_news.extend(yahoo_news)
        
        # If we still don't have enough news, return what we have - no mock data
        if len(all_news) < 2:
            print(f"Insufficient scraped news for {symbol} ({len(all_news)} articles). Returning available real data.")
        
        # Sort by importance and limit
        all_news.sort(key=lambda x: x['importance'], reverse=True)
        result = all_news[:limit]
        
        # Cache the result
        self.cache[cache_key] = result
        self.cache_time[cache_key] = time.time()
        
        return result if result else None
    
    async def close(self):
        """Close the session"""
        if self.session and not self.session.closed:
            await self.session.close()

# Singleton instance
_client = None

def get_client() -> WebScrapingNewsClient:
    global _client
    if _client is None:
        _client = WebScrapingNewsClient()
    return _client
# News & Twitter Sentiment Research

## Research Progress

### Research Done (2026-02-20)

#### Twitter/X
- **X API (Twitter):** Now **pay-per-usage only** - no free tier. Expensive for scraping.
- **Nitter:** Instance seems down/blocked
- **RSS via Nitter:** Not working

#### News Sources
- **NewsAPI.org:** Requires registration, has free tier (100 requests/day)
- **Yahoo Finance:** Has news but RSS feeds seem broken
- **Need to try:**
  - Finviz RSS
  - Investing.com (may need API)
  - CryptoPanic API
  - RSS aggregator

### Still to Research
1. Finviz RSS feeds
2. CryptoPanic API
3. TradingView community signals
4. StockTwits API

### Recommended Implementation Path

**Phase 1: News (easier)**
1. Use NewsAPI.org free tier OR
2. Scrape Yahoo Finance news page directly

**Phase 2: Twitter Signals (harder)**
1. Try X API pay-per-use (estimate costs)
2. Alternative: Scrape trading signal websites directly
3. Alternative: Use TradingView's community signals

### Technical Notes

#### NewsAPI.org
- Free tier: 100 requests/day
- Endpoint: `https://newsapi.org/v2/everying?q=gold+OR+xau`
- Registration required

#### Direct Scraping (Yahoo Finance)
- URL: `https://finance.yahoo.com/news/`
- Use Cheerio or Playwright
- No API key needed

---

## Tasks

- [ ] Try NewsAPI.org (register, test free tier)
- [ ] Test Yahoo Finance direct scraping
- [ ] Find working RSS feeds
- [ ] Research X API costs
- [ ] Alternative: Find trading signal websites to scrape
- [ ] Implement backend endpoint for news
- [ ] Implement Twitter/signal scraping
- [ ] Add to cronjob (every 30-60 min)


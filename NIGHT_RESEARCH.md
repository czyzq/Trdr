# News & Twitter Sentiment Research

## Tasks

### 1. News Tab
- Figure out best free news source for trading
- Options to research:
  - Yahoo Finance API (free)
  - NewsAPI.org (free tier)
  - RSS feeds from trading sites
  - CryptoPanic API
- Implement in backend

### 2. Twitter/X Scraping for Trade Signals
- **Goal:** Scrape tweets from accounts that post trading signals
- **Use case:** Sentiment analysis + signal confirmation
- **Accounts to consider:** (need to find actual ones)
  - Crypto traders
  - Forex signals accounts
  - Stock trading influencers

### Technical Options (Free)

#### Option A: Twitter API v2 (Free Tier)
- 1.5M tweets/month free
- Need developer account
- Rate limits apply

#### Option B: Nitter (Twitter frontend - RSS)
- Free, open source
- No API needed
- RSS feeds available
- Might break due to Twitter restrictions

#### Option C: Web Scraping
- Use Playwright/Cheerio
- Scrape profile pages
- Risk: IP blocks, TOS violations

#### Option D: Third-party aggregators
- CryptoScreener signals
- TradingView community
- StockTwits API

### Recommended Approach
1. Start with **Twitter API free tier** if available
2. Fallback to **RSS feeds** via Nitter or similar
3. Use cronjob to poll every 1 hour

### Implementation Plan
1. Research free news APIs → implement news endpoint
2. Research Twitter scraping options
3. Create backend endpoint for Twitter signals
4. Add cronjob to fetch every 1 hour
5. Integrate with trading signals

---

## Notes


import React, { useState, useEffect } from 'react';

interface NewsArticle {
  symbol: string; // XAU, XAG, US100
  name: string; // Gold, Silver, Nasdaq-100
  headline: string;
  sentiment: number; // -1 to +1
  direction: 'buy' | 'sell' | 'neutral';
  importance: number; // 0 to 1
  source: string;
  url: string;
  published: string;
}

interface NewsResponse {
  news: NewsArticle[];
  timestamp: string;
}

export const NewsTab: React.FC = () => {
  const [newsData, setNewsData] = useState<NewsArticle[]>([]);
  const [loading, setLoading] = useState(false);
  const [cachedNewsIds, setCachedNewsIds] = useState<Set<string>>(new Set());
  const [lastFetchTime, setLastFetchTime] = useState<Date | null>(null);

  useEffect(() => {
    const fetchNews = async () => {
      const fetchStartTime = new Date();
      setLoading(true);
      try {
        const response = await fetch('/api/news/all');
        if (response.ok) {
          const data: NewsResponse = await response.json();
          
          // Cache news IDs for identifying new items
          const newIds = new Set(data.news.map((article, index) => 
            `${article.symbol}-${article.headline}-${article.published}`
          ));
          
          // Update cached IDs and last fetch time
          setCachedNewsIds(newIds);
          setLastFetchTime(fetchStartTime);
          setNewsData(data.news);
        }
      } catch (error) {
        console.error('Failed to fetch news:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchNews();
    // Refresh news every 2 minutes
    const interval = setInterval(fetchNews, 120000);
    return () => clearInterval(interval);
  }, []);

  const getSignalColor = (direction: string) => {
    switch (direction) {
      case 'buy':
        return '#00ff41'; // Green
      case 'sell':
        return '#ff1f1f'; // Red
      default:
        return '#666'; // Gray
    }
  };

  const getSignalLabel = (direction: string) => {
    switch (direction) {
      case 'buy':
        return 'BUY';
      case 'sell':
        return 'SELL';
      default:
        return 'NEUTRAL';
    }
  };

  const getTickerShort = (symbol: string) => {
    const map: Record<string, string> = {
      'XAU': 'GOLD',
      'XAG': 'SILVER',
      'US100': 'NQ'
    };
    return map[symbol] || symbol;
  };

  const formatDateTime = (dateString: string) => {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;
    
    return date.toLocaleDateString('en-GB', { 
      day: '2-digit', 
      month: '2-digit', 
      hour: '2-digit', 
      minute: '2-digit' 
    });
  };

  const isNewNews = (published: string, fetchTime: Date | null) => {
    if (!fetchTime) return true;
    const publishedDate = new Date(published);
    return publishedDate > fetchTime;
  };

  return (
    <div className="flex-1 flex flex-col overflow-hidden" style={{ backgroundColor: '#0a0e27' }}>
      {/* Header */}
      <div className="border-b px-3 py-3 sm:px-6 sm:py-4" style={{ borderColor: '#1a1f2e' }}>
        <div className="font-mono text-xs sm:text-sm uppercase tracking-widest font-bold" style={{ color: '#00ff41' }}>
          📰 News Feed
        </div>
      </div>

      {/* News Table */}
      <div className="flex-1 overflow-y-auto">
        {loading && newsData.length === 0 ? (
          <div className="text-center p-6" style={{ color: '#666' }}>
            <div className="font-mono text-xs sm:text-sm">Loading news...</div>
          </div>
        ) : newsData.length > 0 ? (
          <div className="divide-y" style={{ borderColor: '#1a1f2e' }}>
            {newsData.map((article, idx) => (
              <div
                key={idx}
                className="p-3 sm:p-4 hover:bg-opacity-30 transition"
                style={{
                  backgroundColor: idx % 2 === 0 ? 'rgba(0, 0, 0, 0.2)' : 'transparent'
                }}
              >
                {/* Ticker + Signal Row */}
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-xs sm:text-sm font-bold" style={{ color: '#00ff41' }}>
                      {getTickerShort(article.symbol)}
                    </span>
                    <span className="font-mono text-[10px] sm:text-xs opacity-60" style={{ color: '#fff' }}>
                      {article.name}
                    </span>
                    {isNewNews(article.published, lastFetchTime) && (
                      <span className="font-mono text-[9px] px-1 py-0.5 rounded bg-yellow-500 text-black font-bold">
                        NEW
                      </span>
                    )}
                  </div>
                  <div className="font-mono text-[9px] sm:text-[10px] opacity-60" style={{ color: '#666' }}>
                    {formatDateTime(article.published)}
                  </div>
                  
                  <div className="flex items-center gap-2">
                    <span
                      className="font-mono text-[10px] sm:text-xs font-bold px-2 py-1 rounded"
                      style={{
                        color: getSignalColor(article.direction),
                        backgroundColor: `${getSignalColor(article.direction)}20`,
                        border: `1px solid ${getSignalColor(article.direction)}`
                      }}
                    >
                      {getSignalLabel(article.direction)}
                    </span>
                    
                    <span
                      className="font-mono text-[10px] sm:text-xs font-bold"
                      style={{ color: getSignalColor(article.direction) }}
                    >
                      {article.sentiment > 0 ? '+' : ''}{article.sentiment.toFixed(2)}
                    </span>
                  </div>
                </div>

                {/* Headline */}
                <div
                  className="font-mono text-xs sm:text-sm mb-2 leading-relaxed"
                  style={{ color: '#fff' }}
                >
                  {article.headline}
                </div>

                {/* Importance Bar + Source */}
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 flex-1">
                    <span className="font-mono text-[9px] sm:text-[10px] opacity-60" style={{ color: '#888' }}>
                      IMP:
                    </span>
                    <div className="flex-1 max-w-[100px] h-1.5 sm:h-2 rounded" style={{ backgroundColor: '#1a1f2e' }}>
                      <div
                        className="h-full rounded"
                        style={{
                          width: `${article.importance * 100}%`,
                          backgroundColor: '#00ff41'
                        }}
                      />
                    </div>
                    <span className="font-mono text-[9px] sm:text-[10px]" style={{ color: '#00ff41' }}>
                      {Math.round(article.importance * 100)}%
                    </span>
                  </div>

                  <div className="flex items-center gap-2">
                    <span className="font-mono text-[9px] sm:text-[10px] opacity-60" style={{ color: '#666' }}>
                      {article.source}
                    </span>
                    {article.url && (
                      <a
                        href={article.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="font-mono text-[9px] sm:text-[10px]"
                        style={{ color: '#00ff41' }}
                      >
                        →
                      </a>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-center p-6" style={{ color: '#666' }}>
            <div className="font-mono text-xs sm:text-sm">No news available</div>
          </div>
        )}
      </div>
    </div>
  );
};

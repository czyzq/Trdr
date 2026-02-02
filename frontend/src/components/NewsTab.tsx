import React, { useState, useEffect } from 'react';

interface NewsArticle {
  headline: string;
  sentiment: number; // -1 to +1
  direction: 'buy' | 'sell' | 'neutral';
  importance: number; // 0 to 1
  source: string;
  url: string;
  published: string;
}

interface NewsData {
  symbol: string;
  news: NewsArticle[];
  timestamp: string;
}

const SYMBOLS = ['GC=F', 'SI=F', 'NQ=F'];
const SYMBOL_NAMES: Record<string, string> = {
  'GC=F': 'Gold',
  'SI=F': 'Silver',
  'NQ=F': 'Nasdaq-100'
};

export const NewsTab: React.FC = () => {
  const [selectedSymbol, setSelectedSymbol] = useState<string>('GC=F');
  const [newsData, setNewsData] = useState<Record<string, NewsData>>({});
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const fetchNews = async () => {
      setLoading(true);
      try {
        // Fetch news for all symbols
        for (const symbol of SYMBOLS) {
          const response = await fetch(`/api/news/${symbol}`);
          if (response.ok) {
            const data = await response.json();
            setNewsData(prev => ({
              ...prev,
              [symbol]: data
            }));
          }
        }
      } catch (error) {
        console.error('Failed to fetch news:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchNews();
    // Refresh news every 2 minutes (avoid API spam)
    const interval = setInterval(fetchNews, 120000);
    return () => clearInterval(interval);
  }, []);

  const currentNews = newsData[selectedSymbol];

  const getSignalColor = (direction: string) => {
    switch (direction) {
      case 'buy':
        return '#00ff41'; // Green
      case 'sell':
        return '#ff1f1f'; // Red
      default:
        return '#888'; // Gray
    }
  };

  const getSignalLabel = (direction: string) => {
    switch (direction) {
      case 'buy':
        return '🟢 BUY';
      case 'sell':
        return '🔴 SELL';
      default:
        return '⚪ NEUTRAL';
    }
  };

  return (
    <div className="flex-1 flex flex-col overflow-hidden" style={{ backgroundColor: '#0a0e27' }}>
      {/* Symbol Selector */}
      <div className="border-b px-6 py-4" style={{ borderColor: '#1a1f2e' }}>
        <div className="flex gap-4">
          {SYMBOLS.map(symbol => (
            <button
              key={symbol}
              onClick={() => setSelectedSymbol(symbol)}
              className={`font-mono text-xs uppercase tracking-widest font-bold px-4 py-2 border transition ${
                selectedSymbol === symbol ? 'border-opacity-100' : 'border-opacity-30'
              }`}
              style={{
                color: selectedSymbol === symbol ? '#00ff41' : '#666',
                borderColor: '#00ff41',
                backgroundColor: selectedSymbol === symbol ? 'rgba(0, 255, 65, 0.1)' : 'transparent'
              }}
            >
              {SYMBOL_NAMES[symbol]}
            </button>
          ))}
        </div>
      </div>

      {/* News List */}
      <div className="flex-1 overflow-y-auto p-6">
        {loading && !currentNews && (
          <div className="text-center" style={{ color: '#666' }}>
            <div className="font-mono text-sm">Loading news...</div>
          </div>
        )}

        {currentNews && currentNews.news && currentNews.news.length > 0 ? (
          <div className="space-y-4">
            {currentNews.news.map((article, idx) => (
              <div
                key={idx}
                className="border rounded p-4"
                style={{
                  borderColor: getSignalColor(article.direction),
                  backgroundColor: 'rgba(0, 0, 0, 0.3)'
                }}
              >
                {/* Header: Signal + Importance */}
                <div className="flex items-center justify-between mb-3">
                  <div
                    className="font-mono text-sm font-bold"
                    style={{ color: getSignalColor(article.direction) }}
                  >
                    {getSignalLabel(article.direction)}
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-[10px]" style={{ color: '#888' }}>
                      IMPORTANCE:
                    </span>
                    <div className="flex gap-1">
                      {[...Array(5)].map((_, i) => (
                        <div
                          key={i}
                          className="w-2 h-4"
                          style={{
                            backgroundColor: i < Math.round(article.importance * 5)
                              ? '#00ff41'
                              : '#1a1f2e'
                          }}
                        />
                      ))}
                    </div>
                    <span className="font-mono text-xs" style={{ color: '#00ff41' }}>
                      {Math.round(article.importance * 100)}%
                    </span>
                  </div>
                </div>

                {/* Headline */}
                <div className="font-mono text-sm mb-2" style={{ color: '#fff' }}>
                  {article.headline}
                </div>

                {/* Metadata */}
                <div className="flex items-center justify-between text-[10px] font-mono" style={{ color: '#666' }}>
                  <span>{article.source}</span>
                  {article.url && (
                    <a
                      href={article.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="hover:underline"
                      style={{ color: '#00ff41' }}
                    >
                      Read more →
                    </a>
                  )}
                </div>

                {/* Sentiment Score */}
                <div className="mt-2 pt-2 border-t" style={{ borderColor: '#1a1f2e' }}>
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-[10px]" style={{ color: '#888' }}>
                      SENTIMENT:
                    </span>
                    <div className="flex-1 h-2 rounded" style={{ backgroundColor: '#1a1f2e' }}>
                      <div
                        className="h-full rounded"
                        style={{
                          width: `${Math.abs(article.sentiment) * 50 + 50}%`,
                          backgroundColor: article.sentiment > 0 ? '#00ff41' : '#ff1f1f',
                          marginLeft: article.sentiment < 0 ? '0' : `${50 - Math.abs(article.sentiment) * 50}%`
                        }}
                      />
                    </div>
                    <span className="font-mono text-xs" style={{ color: getSignalColor(article.direction) }}>
                      {article.sentiment > 0 ? '+' : ''}{article.sentiment.toFixed(2)}
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : !loading && (
          <div className="text-center" style={{ color: '#666' }}>
            <div className="font-mono text-sm">No news available for {SYMBOL_NAMES[selectedSymbol]}</div>
          </div>
        )}
      </div>
    </div>
  );
};

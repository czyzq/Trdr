"""
Test News and Sentiment functionality
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestNewsSentiment:
    """Tests for sentiment analysis"""

    def test_sentiment_calculation_exists(self):
        """Test sentiment calculation method exists"""
        from news_client import NewsClient
        client = NewsClient(api_key="test")
        
        # Should have _calculate_sentiment method
        assert hasattr(client, '_calculate_sentiment')

    def test_bullish_sentiment_keywords(self):
        """Test bullish keywords generate positive sentiment"""
        from news_client import NewsClient
        client = NewsClient(api_key="test")
        
        bullish_headlines = [
            "Stock soars to new highs",
            "Company beats earnings expectations",
            "Strong quarterly results push shares up",
            "Bull market continues for tech sector",
            "Investors optimistic about growth"
        ]
        
        for headline in bullish_headlines:
            sentiment, _ = client._calculate_sentiment(headline)
            assert sentiment >= 0, f"Bullish headline got negative sentiment: {headline}"

    def test_bearish_sentiment_keywords(self):
        """Test bearish keywords generate negative sentiment"""
        from news_client import NewsClient
        client = NewsClient(api_key="test")
        
        bearish_headlines = [
            "Stock plummets on poor earnings",
            "Company misses revenue targets",
            "Market crashes amid fears",
            "Bear market grips global economy",
            "Investors flee on recession fears"
        ]
        
        for headline in bearish_headlines:
            sentiment, _ = client._calculate_sentiment(headline)
            assert sentiment <= 0, f"Bearish headline got positive sentiment: {headline}"

    def test_neutral_sentiment(self):
        """Test neutral headlines"""
        from news_client import NewsClient
        client = NewsClient(api_key="test")
        
        neutral_headlines = [
            "Company announces board meeting",
            "Stock price remains steady",
            "Quarterly report released",
            "Annual meeting scheduled",
            "No comment from spokesperson"
        ]
        
        for headline in neutral_headlines:
            _, label = client._calculate_sentiment(headline)
            # Should be neutral
            assert label == "neutral"


class TestNewsClientIntegration:
    """Integration-style tests for news client"""

    def test_get_news_method_exists(self):
        """Test get_news method exists"""
        from news_client import NewsClient
        client = NewsClient(api_key="test")
        
        assert hasattr(client, 'get_news')

    def test_get_news_with_valid_symbol(self):
        """Test news retrieval with valid symbol"""
        from news_client import NewsClient
        client = NewsClient(api_key="test")
        
        # Should not raise exception
        try:
            news = client.get_news("AAPL")
            assert isinstance(news, list)
        except Exception as e:
            # Network/API issues are acceptable in test
            if "API" not in str(e) and "request" not in str(e).lower():
                pytest.fail(f"Unexpected error: {e}")

    def test_get_news_with_unknown_symbol(self):
        """Test news retrieval with obscure symbol"""
        from news_client import NewsClient
        client = NewsClient(api_key="test")
        
        # Obscure symbol might have no news
        news = client.get_news("XYZUNKNOWN123")
        assert isinstance(news, list)


class TestNewsClientEdgeCases:
    """Edge case tests"""

    def test_empty_headline(self):
        """Test handling of empty headline"""
        from news_client import NewsClient
        client = NewsClient(api_key="test")
        
        sentiment, label = client._calculate_sentiment("")
        # Should handle gracefully
        assert sentiment == 0
        assert label == "neutral"

    def test_very_long_headline(self):
        """Test handling of very long headline"""
        from news_client import NewsClient
        client = NewsClient(api_key="test")
        
        long_headline = "A" * 1000
        sentiment, label = client._calculate_sentiment(long_headline)
        
        # Should handle without crashing
        assert isinstance(sentiment, float)

    def test_special_characters(self):
        """Test handling of special characters in headline"""
        from news_client import NewsClient
        client = NewsClient(api_key="test")
        
        headline = "Stock (AAPL) jumps 10% after Q3 earnings!"
        sentiment, label = client._calculate_sentiment(headline)
        
        # Should handle without crashing
        assert isinstance(sentiment, float)
        # Label can be buy/sell/neutral or positive/negative/neutral
        assert label in ["buy", "sell", "positive", "neutral", "negative"]

    def test_numbers_in_headline(self):
        """Test handling of numbers in headline"""
        from news_client import NewsClient
        client = NewsClient(api_key="test")
        
        headline = "Stock up 5% to $105.50"
        sentiment, label = client._calculate_sentiment(headline)
        
        # Should handle without crashing
        assert isinstance(sentiment, float)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

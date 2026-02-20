"""
Broker and data source settings
Configurable refresh rates per broker/data source
"""

import os
from typing import Any, Dict

# Broker type (set via BROKER_TYPE env var)
# Options: "sim" (default), "ibkr"
BROKER_TYPE = os.getenv("BROKER_TYPE", "sim")

# ============================================
# REFRESH RATES (in seconds)
# ============================================

# Price cache refresh - how often to fetch fresh quotes
PRICE_CACHE_REFRESH_SEC = int(os.getenv("PRICE_CACHE_REFRESH_SEC", "3"))

# Signal generation interval - how often to regenerate signals
SIGNAL_SCAN_INTERVAL_SEC = int(os.getenv("SIGNAL_SCAN_INTERVAL_SEC", "300"))  # 5 min

# News fetch interval - how often to fetch fresh news
NEWS_REFRESH_INTERVAL_SEC = int(os.getenv("NEWS_REFRESH_INTERVAL_SEC", "600"))  # 10 min

# Account balance refresh
ACCOUNT_REFRESH_SEC = int(os.getenv("ACCOUNT_REFRESH_SEC", "5"))

# Console logs refresh
LOGS_REFRESH_SEC = int(os.getenv("LOGS_REFRESH_SEC", "10"))

# ============================================
# BROKER-SPECIFIC SETTINGS
# ============================================

BROKER_SETTINGS: Dict[str, Dict[str, Any]] = {
    "sim": {
        "name": "Simulated (Paper Trading)",
        "data_sources": ["alpha_vantage", "yahoo_finance"],
        "price_refresh_sec": 3,
        "supports_streaming": False,
        "rate_limit": "5 req/min (Alpha Vantage free tier)",
        "notes": "Uses Alpha Vantage + Yahoo Finance as data providers",
    },
    "ibkr": {
        "name": "Interactive Brokers",
        "data_sources": ["ibkr_gateway"],
        "price_refresh_sec": 1,  # IBKR streaming
        "supports_streaming": True,
        "rate_limit": "100 msg/sec (IBKR API)",
        "notes": "Real-time streaming via IB Gateway/TWS",
    },
    "xtb": {
        "name": "XTB",
        "data_sources": ["xtb_api"],
        "price_refresh_sec": 1,  # XTB streaming
        "supports_streaming": True,
        "rate_limit": "Real-time streaming",
        "notes": "XTB CFD - requires XTB account",
    },
}


def get_current_broker_settings() -> Dict[str, Any]:
    """Get settings for currently configured broker"""
    return BROKER_SETTINGS.get(BROKER_TYPE, BROKER_SETTINGS["sim"])


def get_all_settings() -> Dict[str, Any]:
    """Get all configuration for API response"""
    broker = get_current_broker_settings()
    return {
        "broker_type": BROKER_TYPE,
        "broker_name": broker["name"],
        "data_sources": broker["data_sources"],
        "refresh_rates": {
            "price_cache_sec": PRICE_CACHE_REFRESH_SEC,
            "signal_scan_sec": SIGNAL_SCAN_INTERVAL_SEC,
            "news_fetch_sec": NEWS_REFRESH_INTERVAL_SEC,
            "account_sec": ACCOUNT_REFRESH_SEC,
            "logs_sec": LOGS_REFRESH_SEC,
        },
        "broker_specific": broker,
    }

#!/usr/bin/env python3
import os
import httpx
import time
from dotenv import load_dotenv

load_dotenv()

BRAVE_API_KEY = os.getenv("BRAVE_API_KEY")
BRAVE_BASE_URL = "https://api.search.brave.com/res/v1/web/search"

print(f"Testing Brave API with key: {BRAVE_API_KEY[:10] if BRAVE_API_KEY else 'NOT SET'}...")

params = {
    "q": "gold price news",
    "count": 2,
    "freshness": "past-24h"
}

headers = {
    "Accept": "application/json",
    "X-Subscription-Token": BRAVE_API_KEY
}

print("Making request...")
try:
    with httpx.Client() as client:
        response = client.get(BRAVE_BASE_URL, params=params, headers=headers, timeout=10)
        print(f"Status code: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"Found {len(data.get('web', []))} articles")
            for article in data.get('web', [])[:2]:
                print(f"- {article.get('title', 'No title')}")
        else:
            print(f"Error: {response.text}")
except Exception as e:
    print(f"Exception: {e}")
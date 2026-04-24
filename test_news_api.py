#!/usr/bin/env python3
# test_news_api.py
"""Diagnostic test for the newsapi.ai (Event Registry) integration."""

import config
import requests

EVENT_REGISTRY_URL = "https://eventregistry.org/api/v1/article/getArticles"

print("Testing News API (newsapi.ai / Event Registry)...")
key = config.NEWS_API_KEY or ""
print(f"API Key: {key[:10]}..." if len(key) > 10 else "NOT SET")
print()

if not key or key == "your_newsapi_key_here":
    print("❌ API key not configured. Set NEWS_API_KEY in .env")
else:
    print("✅ API key found")
    print("\nTesting API call...")
    try:
        r = requests.post(EVENT_REGISTRY_URL, json={
            "action": "getArticles",
            "keyword": "Apple stock",
            "lang": "eng",
            "articlesSortBy": "date",
            "articlesCount": 5,
            "resultType": "articles",
            "apiKey": key,
        }, timeout=20)
        r.raise_for_status()
        data = r.json()
        if data.get("error"):
            print(f"❌ API error: {data['error']}")
        else:
            results = (data.get("articles") or {}).get("results", [])
            total = (data.get("articles") or {}).get("totalResults", 0)
            print(f"✅ SUCCESS! Got {len(results)} articles (totalResults: {total})")
            if results:
                first = results[0]
                print("\nFirst article:")
                print(f"  Title: {first.get('title', '')}")
                src = first.get("source") or {}
                print(f"  Source: {src.get('title') or src.get('uri', 'Unknown')}")
                print(f"  Published: {first.get('dateTimePub') or first.get('dateTime', '')}")
    except requests.HTTPError as e:
        print(f"❌ HTTP error: {e}")
        print("\nPossible issues:")
        print("- Invalid API key (401)")
        print("- Rate limit / quota exceeded (429)")
    except Exception as e:
        print(f"❌ Error: {e}")

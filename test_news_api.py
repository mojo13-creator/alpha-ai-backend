#!/usr/bin/env python3
# test_news_api.py

import config

print("Testing News API...")
print(f"API Key: {config.NEWS_API_KEY[:10]}..." if len(config.NEWS_API_KEY) > 10 else "NOT SET")
print()

if config.NEWS_API_KEY == "your_newsapi_key_here":
    print("❌ API key not configured in config.py")
else:
    print("✅ API key found in config.py")
    print()
    
    try:
        from newsapi import NewsApiClient
        print("✅ newsapi-python is installed")
        
        newsapi = NewsApiClient(api_key=config.NEWS_API_KEY)
        print("✅ NewsApiClient created")
        
        # Test fetch
        print("\nTesting API call...")
        articles = newsapi.get_everything(
            q='Apple stock',
            language='en',
            page_size=5
        )
        
        print(f"✅ SUCCESS! Got {len(articles.get('articles', []))} articles")
        print("\nFirst article:")
        if articles.get('articles'):
            first = articles['articles'][0]
            print(f"  Title: {first['title']}")
            print(f"  Source: {first['source']['name']}")
        
    except ImportError:
        print("❌ newsapi-python not installed")
        print("Run: pip install newsapi-python")
    
    except Exception as e:
        print(f"❌ Error: {e}")
        print("\nPossible issues:")
        print("- Invalid API key")
        print("- Free tier rate limit exceeded (100 requests/day)")
        print("- Network issue")
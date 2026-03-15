# analysis/ai_analyzer.py
"""
AI-Powered Stock Analysis Engine
Uses Claude AI for sophisticated analysis
"""

import pandas as pd
from datetime import datetime
import json
import os
import sys

# Add parent directory to path for config import
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class AIStockAnalyzer:
    """AI-powered stock analyzer using Claude"""
    
    def __init__(self, db_manager, technical_analyzer, news_scraper):
        self.db = db_manager
        self.technical = technical_analyzer
        self.news = news_scraper
        print("🤖 AI Stock Analyzer initialized")
    
    def analyze_stock_with_ai(self, symbol):
        """
        Complete AI analysis of a stock
        """
        print(f"\n🤖 AI ANALYSIS: {symbol}")
        
        # Get technical data
        df = self.technical.calculate_all_indicators(symbol)
        if df is None or df.empty:
            return None
        
        latest = df.iloc[-1]
        price = latest['close']
        
        # Gather all data
        analysis_data = {
            "symbol": symbol,
            "price": float(price),
            "rsi": float(latest.get('RSI', 50)),
            "macd": float(latest.get('MACD', 0)),
            "macd_signal": float(latest.get('MACD_Signal', 0)),
            "sma_20": float(latest.get('SMA_20', price)),
            "sma_50": float(latest.get('SMA_50', price)),
            "sma_200": float(latest.get('SMA_200', price)),
        }
        
        # Get news
        try:
            news = self.news.fetch_stock_news(symbol, days=7)
            news_text = self._summarize_news(news)
        except:
            news_text = "No recent news"
        
        # Get Reddit sentiment
        try:
            from data_collection.reddit_scraper import fetch_reddit_sentiment
            reddit_data = fetch_reddit_sentiment(symbol)
            reddit_text = f"Sentiment: {reddit_data['sentiment_label']} ({reddit_data['sentiment_score']}/100) from {reddit_data['post_count']} posts"
        except:
            reddit_text = 'No Reddit data available'

        # Call AI
        ai_result = self._call_claude_ai(analysis_data, news_text, reddit_text)
        
        if ai_result:
            # Save to database
            self.db.save_recommendation(
                symbol=symbol,
                recommendation=ai_result['recommendation'],
                score=ai_result['score'],
                reasoning=ai_result['reasoning'],
                price=price
            )
            
            print(f"✅ AI Analysis: {ai_result['recommendation']} ({ai_result['score']}/100)")
            return ai_result
        
        return None
    
    def _summarize_news(self, articles):
        """Summarize news"""
        if not articles:
            return "No recent news"
        
        summaries = []
        for article in articles[:5]:
            title = article.get('title', '')
            if title:
                summaries.append(f"- {title}")
        
        return "\n".join(summaries) if summaries else "No news"
    
    def _call_claude_ai(self, data, news, reddit='No Reddit data available'):
        """Call Claude API for analysis"""
        
        try:
            import config
            import anthropic
            
            if not hasattr(config, 'CLAUDE_API_KEY') or not config.CLAUDE_API_KEY:
                print("⚠️  No Claude API key configured")
                return None
            
            client = anthropic.Anthropic(api_key=config.CLAUDE_API_KEY)
            
            prompt = f"""Analyze this stock and provide a recommendation.

STOCK: {data['symbol']}
PRICE: ${data['price']:.2f}
RSI: {data['rsi']:.1f}
MACD: {data['macd']:.2f} (Signal: {data['macd_signal']:.2f})
20-day SMA: ${data['sma_20']:.2f}
50-day SMA: ${data['sma_50']:.2f}
200-day SMA: ${data['sma_200']:.2f}

RECENT NEWS:
{news}

REDDIT COMMUNITY SENTIMENT:
{reddit}

Provide analysis in JSON format:
{{
    "score": <0-100>,
    "recommendation": "<STRONG BUY|BUY|HOLD|SELL|STRONG SELL>",
    "key_factors": ["factor1", "factor2"],
    "risks": ["risk1"],
    "reasoning": "detailed explanation"
}}"""
            
            message = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1500,
                messages=[{"role": "user", "content": prompt}]
            )
            
            response_text = message.content[0].text
            
            # Parse JSON
            import re
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                ai_response = json.loads(json_match.group())
                
                reasoning = f"""AI ANALYSIS - {data['symbol']}
Score: {ai_response['score']}/100
Recommendation: {ai_response['recommendation']}

{ai_response['reasoning']}

KEY FACTORS:
{chr(10).join(f"  • {f}" for f in ai_response['key_factors'])}

RISKS:
{chr(10).join(f"  ⚠️  {r}" for r in ai_response['risks'])}

Price: ${data['price']:.2f}
"""
                
                return {
                    'symbol': data['symbol'],
                    'recommendation': ai_response['recommendation'],
                    'score': ai_response['score'],
                    'price': data['price'],
                    'price_target': ai_response.get('price_target', 0),
                    'stop_loss': ai_response.get('stop_loss', 0),
                    'bull_case': ai_response.get('bull_case', ''),
                    'bear_case': ai_response.get('bear_case', ''),
                    'reasoning': reasoning,
                    'timestamp': datetime.now()
                }
        
        except Exception as e:
            print(f"⚠️  AI error: {e}")
            return None

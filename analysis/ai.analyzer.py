import os
# === AI CONFIGURATION ===
CLAUDE_API_KEY = "REDACTED_CLAUDE_API_KEY"  # Replace with your actual key

# Use AI for stock analysis (set to False to use technical only)
USE_AI_ANALYSIS = True
# analysis/ai_analyzer.py
"""
AI-Powered Stock Analysis Engine
Uses Claude AI for sophisticated, multi-factor analysis
"""

import os

import anthropic
import pandas as pd
from datetime import datetime, timedelta
import json

class AIStockAnalyzer:
    """
    Ultimate AI-powered stock analyzer
    Combines technical analysis, news, market context, and AI reasoning
    """
    
    def __init__(self, db_manager, technical_analyzer, news_scraper):
        self.db = db_manager
        self.technical = technical_analyzer
        self.news = news_scraper
        print("🤖 AI Stock Analyzer initialized")
    
    def analyze_stock_with_ai(self, symbol):
        """
        Complete AI-powered analysis of a stock
        Returns detailed recommendation with AI reasoning
        """
        print(f"\n{'='*70}")
        print(f"🤖 AI ANALYSIS: {symbol}")
        print('='*70)
        
        # === 1. GATHER ALL DATA ===
        print("📊 Gathering comprehensive data...")
        
        # Technical data
        df = self.technical.calculate_all_indicators(symbol)
        if df is None or df.empty:
            return None
        
        # Get latest values and historical context
        latest = df.iloc[-1]
        last_week = df.iloc[-5] if len(df) >= 5 else latest
        last_month = df.iloc[-20] if len(df) >= 20 else latest
        
        # Calculate performance metrics
        price_1d = latest['close']
        price_5d = last_week['close']
        price_20d = last_month['close']
        
        perf_5d = ((price_1d - price_5d) / price_5d) * 100
        perf_20d = ((price_1d - price_20d) / price_20d) * 100
        
        # Volatility
        volatility = df['close'].tail(20).std() / df['close'].tail(20).mean() * 100
        
        # Volume trends
        avg_volume_20d = df['volume'].tail(20).mean()
        recent_volume = latest['volume']
        volume_trend = (recent_volume / avg_volume_20d) if avg_volume_20d > 0 else 1
        
        # === 2. GET NEWS & CATALYSTS ===
        print("📰 Fetching recent news and catalysts...")
        
        try:
            news_articles = self.news.fetch_stock_news(symbol, days=7)
            news_summary = self._summarize_news(news_articles)
        except:
            news_summary = "No recent news available"
        
        # === 3. COMPILE COMPREHENSIVE DATA PACKAGE ===
        analysis_data = {
            "symbol": symbol,
            "current_price": float(price_1d),
            
            "technical_indicators": {
                "rsi": float(latest.get('RSI', 50)),
                "macd": float(latest.get('MACD', 0)),
                "macd_signal": float(latest.get('MACD_Signal', 0)),
                "adx": float(latest.get('ADX', 25)),
                "stochastic": float(latest.get('Stochastic', 50)),
                "atr": float(latest.get('ATR', 0))
            },
            
            "moving_averages": {
                "sma_20": float(latest.get('SMA_20', price_1d)),
                "sma_50": float(latest.get('SMA_50', price_1d)),
                "sma_200": float(latest.get('SMA_200', price_1d)),
                "ema_12": float(latest.get('EMA_12', price_1d)),
                "ema_26": float(latest.get('EMA_26', price_1d))
            },
            
            "bollinger_bands": {
                "upper": float(latest.get('BB_Upper', price_1d * 1.02)),
                "middle": float(latest.get('BB_Middle', price_1d)),
                "lower": float(latest.get('BB_Lower', price_1d * 0.98)),
                "position": self._calculate_bb_position(latest, price_1d)
            },
            
            "performance": {
                "5_day_change": float(perf_5d),
                "20_day_change": float(perf_20d),
                "volatility": float(volatility)
            },
            
            "volume": {
                "current": int(recent_volume),
                "20d_average": int(avg_volume_20d),
                "ratio": float(volume_trend)
            },
            
            "trend_analysis": {
                "short_term": "bullish" if price_1d > latest.get('SMA_20', price_1d) else "bearish",
                "medium_term": "bullish" if price_1d > latest.get('SMA_50', price_1d) else "bearish",
                "long_term": "bullish" if price_1d > latest.get('SMA_200', price_1d) else "bearish",
                "golden_cross": latest.get('SMA_50', 0) > latest.get('SMA_200', 0)
            },
            
            "news_sentiment": news_summary
        }
        
        # === 4. SEND TO AI FOR ANALYSIS ===
        print("🧠 AI is analyzing all data...")
        
        ai_analysis = self._get_ai_analysis(analysis_data)
        
        if not ai_analysis:
            print("❌ AI analysis failed, falling back to technical only")
            return self._fallback_analysis(symbol, analysis_data)
        
        # === 5. SAVE AND RETURN ===
        self.db.save_recommendation(
            symbol=symbol,
            recommendation=ai_analysis['recommendation'],
            score=ai_analysis['score'],
            reasoning=ai_analysis['reasoning'],
            price=price_1d
        )
        
        print(f"✅ AI Analysis Complete: {ai_analysis['recommendation']} ({ai_analysis['score']}/100)")
        
        return ai_analysis
    
    def _calculate_bb_position(self, latest, price):
        """Calculate position within Bollinger Bands (0-1)"""
        upper = latest.get('BB_Upper', price * 1.02)
        lower = latest.get('BB_Lower', price * 0.98)
        
        if upper == lower:
            return 0.5
        
        return (price - lower) / (upper - lower)
    
    def _summarize_news(self, articles):
        """Summarize news articles into key points"""
        if not articles or len(articles) == 0:
            return "No recent news"
        
        summaries = []
        for article in articles[:5]:  # Top 5 articles
            title = article.get('title', '')
            if title:
                summaries.append(f"- {title}")
        
        return "\n".join(summaries) if summaries else "No significant news"
    
    def _get_ai_analysis(self, data):
        """
        Send data to Claude AI for sophisticated analysis
        Returns: dict with recommendation, score, reasoning
        """
        
        # Build the AI prompt
        prompt = f"""You are an expert stock analyst with decades of experience. Analyze this stock comprehensively and provide a sophisticated investment recommendation.

STOCK: {data['symbol']}
CURRENT PRICE: ${data['current_price']:.2f}

TECHNICAL ANALYSIS:
- RSI: {data['technical_indicators']['rsi']:.1f}
- MACD: {data['technical_indicators']['macd']:.2f} (Signal: {data['technical_indicators']['macd_signal']:.2f})
- ADX (Trend Strength): {data['technical_indicators']['adx']:.1f}
- Stochastic: {data['technical_indicators']['stochastic']:.1f}

MOVING AVERAGES:
- 20-day SMA: ${data['moving_averages']['sma_20']:.2f}
- 50-day SMA: ${data['moving_averages']['sma_50']:.2f}
- 200-day SMA: ${data['moving_averages']['sma_200']:.2f}

BOLLINGER BANDS:
- Upper: ${data['bollinger_bands']['upper']:.2f}
- Lower: ${data['bollinger_bands']['lower']:.2f}
- Position: {data['bollinger_bands']['position']:.2%} (0% = at lower band, 100% = at upper band)

PERFORMANCE:
- 5-day change: {data['performance']['5_day_change']:+.2f}%
- 20-day change: {data['performance']['20_day_change']:+.2f}%
- Volatility: {data['performance']['volatility']:.2f}%

VOLUME:
- Current: {data['volume']['current']:,}
- 20-day average: {data['volume']['20d_average']:,}
- Ratio: {data['volume']['ratio']:.2f}x

TREND ANALYSIS:
- Short-term (20-day): {data['trend_analysis']['short_term']}
- Medium-term (50-day): {data['trend_analysis']['medium_term']}
- Long-term (200-day): {data['trend_analysis']['long_term']}
- Golden Cross: {"Yes" if data['trend_analysis']['golden_cross'] else "No"}

RECENT NEWS:
{data['news_sentiment']}

INSTRUCTIONS:
Analyze this stock from multiple angles:
1. Technical strength (momentum, trend, overbought/oversold)
2. Risk factors (volatility, trend weakness, bearish signals)
3. Opportunity factors (oversold conditions, strong momentum, catalysts)
4. Volume confirmation
5. News sentiment and catalysts

Provide your response in this EXACT JSON format:
{{
    "score": <integer 0-100>,
    "recommendation": "<STRONG BUY|BUY|HOLD|SELL|STRONG SELL>",
    "confidence": "<HIGH|MEDIUM|LOW>",
    "time_horizon": "<SHORT-TERM|SWING|LONG-TERM>",
    "key_factors": [
        "factor 1",
        "factor 2",
        "factor 3"
    ],
    "risks": [
        "risk 1",
        "risk 2"
    ],
    "catalysts": [
        "catalyst 1 if any"
    ],
    "reasoning": "Detailed 3-4 sentence explanation of your recommendation"
}}

Be analytical, nuanced, and consider ALL the data. Give unique scores based on the complete picture, not just one indicator."""

        # Call Claude AI
        try:
            import anthropic
            
            import sys
            sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            import config

            client = anthropic.Anthropic(
                api_key=config.CLAUDE_API_KEY
            )
            
            message = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=2000,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            
            # Parse AI response
            response_text = message.content[0].text
            
            # Extract JSON from response
            import re
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                ai_response = json.loads(json_match.group())
                
                # Format the complete analysis
                reasoning = f"""
AI ANALYSIS FOR {data['symbol']}
Score: {ai_response['score']}/100
Recommendation: {ai_response['recommendation']}
Confidence: {ai_response['confidence']}
Time Horizon: {ai_response['time_horizon']}

{ai_response['reasoning']}

KEY FACTORS:
{chr(10).join(f"  • {factor}" for factor in ai_response['key_factors'])}

RISKS TO CONSIDER:
{chr(10).join(f"  ⚠️  {risk}" for risk in ai_response['risks'])}

{f"CATALYSTS:{chr(10)}" + chr(10).join(f"  🔥 {cat}" for cat in ai_response['catalysts']) if ai_response.get('catalysts') else ""}

Current Price: ${data['current_price']:.2f}
"""
                
                return {
                    'symbol': data['symbol'],
                    'recommendation': ai_response['recommendation'],
                    'score': ai_response['score'],
                    'confidence': ai_response['confidence'],
                    'time_horizon': ai_response['time_horizon'],
                    'price': data['current_price'],
                    'reasoning': reasoning.strip(),
                    'timestamp': datetime.now()
                }
        
        except Exception as e:
            print(f"⚠️  AI analysis error: {e}")
            return None
    
    def _fallback_analysis(self, symbol, data):
        """Fallback to technical analysis if AI fails"""
        # Use the enhanced scoring from before
        score = 50
        
        # Quick technical scoring
        rsi = data['technical_indicators']['rsi']
        if rsi < 30:
            score += 15
        elif rsi > 70:
            score -= 15
        
        # Add more quick logic...
        
        if score >= 60:
            recommendation = "BUY"
        elif score >= 40:
            recommendation = "HOLD"
        else:
            recommendation = "SELL"
        
        return {
            'symbol': symbol,
            'recommendation': recommendation,
            'score': score,
            'price': data['current_price'],
            'reasoning': "Technical analysis (AI unavailable)",
            'timestamp': datetime.now()
        }
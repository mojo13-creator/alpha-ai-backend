# analysis/hybrid_recommender.py
"""
Hybrid Recommendation Engine
AI + Technical Analysis
"""

import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.ai_analyzer import AIStockAnalyzer
from analysis.recommendation_engine import RecommendationEngine

class HybridRecommender:
    """
    Smart recommender using AI when available
    """
    
    def __init__(self, db_manager, technical_analyzer, news_scraper):
        self.db = db_manager
        self.technical = technical_analyzer
        self.news = news_scraper
        
        # Check if AI is enabled
        try:
            import config
            self.use_ai = getattr(config, 'USE_AI_ANALYSIS', False)
        except:
            self.use_ai = False
        
        # Initialize both engines
        self.ai_analyzer = AIStockAnalyzer(db_manager, technical_analyzer, news_scraper)
        self.technical_recommender = RecommendationEngine(db_manager, technical_analyzer)
        
        print(f"🤖 Hybrid Recommender initialized (AI: {'ON' if self.use_ai else 'OFF'})")
    
    def analyze_and_recommend(self, symbol):
        """Analyze stock with AI or technical analysis"""
        
        # Check current AI setting
        try:
            import config
            self.use_ai = getattr(config, 'USE_AI_ANALYSIS', False)
        except:
            self.use_ai = False
        
        if self.use_ai:
            try:
                print(f"🤖 AI analysis for {symbol}...")
                result = self.ai_analyzer.analyze_stock_with_ai(symbol)
                
                if result:
                    return result
                else:
                    print("⚠️  AI failed, using technical...")
                    return self.technical_recommender.analyze_and_recommend(symbol)
            
            except Exception as e:
                print(f"⚠️  AI error: {e}, using technical...")
                return self.technical_recommender.analyze_and_recommend(symbol)
        else:
            print(f"📊 Technical analysis for {symbol}...")
            return self.technical_recommender.analyze_and_recommend(symbol)
    
    def analyze_watchlist(self):
        """Analyze all watchlist stocks"""
        watchlist = self.db.get_watchlist()
        
        if watchlist.empty:
            return []
        
        results = []
        for _, row in watchlist.iterrows():
            result = self.analyze_and_recommend(row['symbol'])
            if result:
                results.append(result)
        
        return results

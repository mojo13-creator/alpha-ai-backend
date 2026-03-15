# analysis/discovery_engine.py
"""
Discovery Engine - Find Hidden Gems with Breakthrough Catalysts
"""

import pandas as pd
from datetime import datetime, timedelta
import re

class DiscoveryEngine:
    """
    Advanced stock discovery focusing on:
    - Breaking news and catalysts
    - Niche sectors (quantum, biotech, space, AI)
    - Breakthrough technologies
    - Strategic timing recommendations
    """
    
    def __init__(self, db_manager, analyzer, news_scraper):
        self.db = db_manager
        self.analyzer = analyzer
        self.news_scraper = news_scraper
        print("🔍 Discovery Engine initialized")
    
    # Catalyst keywords that indicate major opportunities
    CATALYST_KEYWORDS = {
        'breakthrough': {
            'keywords': ['breakthrough', 'revolutionary', 'first-of-its-kind', 'paradigm shift', 
                        'game-changer', 'milestone', 'major advance', 'unprecedented'],
            'weight': 10,
            'category': 'BREAKTHROUGH'
        },
        'fda_approval': {
            'keywords': ['FDA approval', 'FDA cleared', 'regulatory approval', 'clinical trial success',
                        'phase 3', 'accelerated approval', 'orphan drug'],
            'weight': 15,
            'category': 'BIOTECH_CATALYST'
        },
        'ai_advancement': {
            'keywords': ['AI breakthrough', 'machine learning', 'GPT', 'artificial intelligence',
                        'neural network', 'deep learning', 'AGI', 'LLM', 'foundation model'],
            'weight': 12,
            'category': 'AI_CATALYST'
        },
        'quantum': {
            'keywords': ['quantum computing', 'qubit', 'quantum supremacy', 'quantum advantage',
                        'quantum processor', 'error correction', 'quantum algorithm'],
            'weight': 13,
            'category': 'QUANTUM_CATALYST'
        },
        'space': {
            'keywords': ['satellite launch', 'space mission', 'orbital', 'NASA contract',
                        'SpaceX', 'rocket launch', 'space exploration', 'constellation'],
            'weight': 11,
            'category': 'SPACE_CATALYST'
        },
        'partnerships': {
            'keywords': ['partnership with', 'joint venture', 'collaboration with', 'signed deal',
                        'strategic alliance', 'acquisition', 'merger'],
            'weight': 8,
            'category': 'BUSINESS_CATALYST'
        },
        'earnings_beat': {
            'keywords': ['beats earnings', 'exceeds expectations', 'record revenue', 
                        'strong guidance', 'upgraded', 'raises outlook'],
            'weight': 7,
            'category': 'EARNINGS_CATALYST'
        },
        'contracts': {
            'keywords': ['wins contract', 'awarded contract', 'government contract',
                        'DOD contract', 'military contract', '$100 million', '$1 billion'],
            'weight': 9,
            'category': 'CONTRACT_CATALYST'
        }
    }
    
    # Niche sectors to focus on
    NICHE_SECTORS = {
        'QUANTUM': ['IONQ', 'RGTI', 'QBTS', 'ARQQ'],
        'AI_SMALL_CAP': ['AI', 'SOUN', 'BBAI', 'AVAV'],
        'BIOTECH_EMERGING': ['CRSP', 'NTLA', 'EDIT', 'BEAM', 'VERV', 'BLUE'],
        'SPACE_NEW': ['RKLB', 'ASTS', 'PL', 'LUNR', 'SPIR'],
        'CLEAN_ENERGY_NICHE': ['ENPH', 'RUN', 'FSLR', 'CHPT', 'PLUG'],
        'DEFENSE_TECH': ['LMT', 'RTX', 'NOC', 'LHX', 'PLTR'],
        'GENOMICS': ['ARKG', 'NVTA', 'PACB', 'ILMN', 'TWST']
    }
    
    def analyze_news_catalysts(self, symbol, days=7):
        """
        Analyze recent news for breakthrough catalysts
        Returns catalyst score and recommended strategy
        """
        # Fetch recent news
        articles = self.news_scraper.fetch_stock_news(symbol, days=days)
        
        if not articles:
            return None
        
        catalyst_score = 0
        found_catalysts = []
        
        for article in articles:
            title = article.get('title', '').lower()
            description = article.get('description', '').lower()
            full_text = f"{title} {description}"
            
            # Check for catalyst keywords
            for catalyst_type, catalyst_info in self.CATALYST_KEYWORDS.items():
                for keyword in catalyst_info['keywords']:
                    if keyword.lower() in full_text:
                        catalyst_score += catalyst_info['weight']
                        found_catalysts.append({
                            'type': catalyst_info['category'],
                            'keyword': keyword,
                            'title': article.get('title', ''),
                            'date': article.get('published_at', ''),
                            'weight': catalyst_info['weight']
                        })
                        break
        
        if catalyst_score > 0:
            return {
                'symbol': symbol,
                'catalyst_score': catalyst_score,
                'catalysts': found_catalysts,
                'num_catalysts': len(found_catalysts),
                'articles_analyzed': len(articles)
            }
        
        return None
    
    def determine_trade_strategy(self, symbol, catalyst_data, technical_score):
        """
        Determine if stock is short-term trade or long-term hold
        Returns detailed strategy with timeline
        """
        strategy = {
            'symbol': symbol,
            'strategy_type': 'UNKNOWN',
            'time_horizon': 'UNKNOWN',
            'confidence': 0,
            'entry_strategy': '',
            'exit_strategy': '',
            'position_size': 'MEDIUM',
            'risk_level': 'MEDIUM'
        }
        
        catalyst_score = catalyst_data['catalyst_score'] if catalyst_data else 0
        
        # Determine strategy based on catalysts and technicals
        
        # LONG-TERM HOLD (6-18 months)
        if catalyst_score >= 15 or any(c['type'] in ['BREAKTHROUGH', 'BIOTECH_CATALYST', 'QUANTUM_CATALYST'] 
                                        for c in (catalyst_data.get('catalysts', []) if catalyst_data else [])):
            strategy['strategy_type'] = 'LONG-TERM HOLD'
            strategy['time_horizon'] = '6-18 months'
            strategy['confidence'] = min(95, catalyst_score * 3 + technical_score)
            strategy['entry_strategy'] = 'Scale in over 2-4 weeks, buy dips'
            strategy['exit_strategy'] = 'Hold through volatility, sell 20% on major catalyst realization'
            strategy['position_size'] = 'LARGE (3-5% of portfolio)'
            strategy['risk_level'] = 'MEDIUM-HIGH'
            strategy['rationale'] = 'Major breakthrough catalyst with transformative potential'
        
        # SWING TRADE (2-8 weeks)
        elif catalyst_score >= 8 and technical_score >= 65:
            strategy['strategy_type'] = 'SWING TRADE'
            strategy['time_horizon'] = '2-8 weeks'
            strategy['confidence'] = catalyst_score * 2 + technical_score
            strategy['entry_strategy'] = 'Buy on technical confirmation (RSI<40 or breakout)'
            strategy['exit_strategy'] = 'Take profits at 15-25% gain or technical reversal'
            strategy['position_size'] = 'MEDIUM (2-3% of portfolio)'
            strategy['risk_level'] = 'MEDIUM'
            strategy['rationale'] = 'Near-term catalyst + strong technicals = momentum opportunity'
        
        # SHORT-TERM MOMENTUM (3-10 days)
        elif technical_score >= 75 and catalyst_score >= 5:
            strategy['strategy_type'] = 'SHORT-TERM MOMENTUM'
            strategy['time_horizon'] = '3-10 days'
            strategy['confidence'] = technical_score + catalyst_score
            strategy['entry_strategy'] = 'Buy early morning on strong volume'
            strategy['exit_strategy'] = 'Take 10-15% profit quickly, cut losses at -5%'
            strategy['position_size'] = 'SMALL (1-2% of portfolio)'
            strategy['risk_level'] = 'HIGH'
            strategy['rationale'] = 'Strong technical setup with news catalyst'
        
        # ACCUMULATION (3-6 months)
        elif technical_score <= 40 and catalyst_score >= 10:
            strategy['strategy_type'] = 'ACCUMULATION'
            strategy['time_horizon'] = '3-6 months'
            strategy['confidence'] = catalyst_score * 2.5
            strategy['entry_strategy'] = 'Dollar-cost average over 4-8 weeks during weakness'
            strategy['exit_strategy'] = 'Hold until catalyst materializes, reassess quarterly'
            strategy['position_size'] = 'LARGE (3-5% of portfolio)'
            strategy['risk_level'] = 'MEDIUM'
            strategy['rationale'] = 'Oversold with major catalyst pending - value opportunity'
        
        # WAIT AND WATCH
        else:
            strategy['strategy_type'] = 'WAIT AND WATCH'
            strategy['time_horizon'] = 'Not recommended yet'
            strategy['confidence'] = 40
            strategy['entry_strategy'] = 'Wait for clearer catalyst or better technical setup'
            strategy['exit_strategy'] = 'N/A'
            strategy['position_size'] = 'NONE'
            strategy['risk_level'] = 'N/A'
            strategy['rationale'] = 'Insufficient catalyst strength or technical confirmation'
        
        return strategy
    
    def discover_hidden_gems(self, sectors_to_scan=None):
        """
        Main discovery function - scans niche sectors for breakthrough opportunities
        Returns ranked list of discoveries with detailed strategies
        """
        print("\n" + "="*70)
        print("🔍 DISCOVERY ENGINE: Scanning for Hidden Gems")
        print("="*70)
        
        if sectors_to_scan is None:
            sectors_to_scan = list(self.NICHE_SECTORS.keys())
        
        discoveries = []
        
        for sector in sectors_to_scan:
            symbols = self.NICHE_SECTORS.get(sector, [])
            
            print(f"\n📊 Scanning {sector} ({len(symbols)} stocks)...")
            
            for symbol in symbols:
                try:
                    print(f"   Analyzing {symbol}...", end=" ")
                    
                    # 1. Analyze news catalysts
                    catalyst_data = self.analyze_news_catalysts(symbol, days=7)
                    
                    # 2. Get technical analysis
                    df = self.analyzer.calculate_all_indicators(symbol)
                    
                    if df is None or df.empty:
                        print("No data")
                        continue
                    
                    signals = self.analyzer.get_trading_signals(df)
                    technical_score = signals['score']
                    
                    # 3. Determine strategy
                    strategy = self.determine_trade_strategy(symbol, catalyst_data, technical_score)
                    
                    # 4. Only include if there's a real opportunity
                    if strategy['strategy_type'] != 'WAIT AND WATCH':
                        latest_price = df.iloc[-1]['close']
                        
                        discoveries.append({
                            'symbol': symbol,
                            'sector': sector,
                            'price': latest_price,
                            'technical_score': technical_score,
                            'catalyst_score': catalyst_data['catalyst_score'] if catalyst_data else 0,
                            'total_score': strategy['confidence'],
                            'strategy': strategy,
                            'catalysts': catalyst_data['catalysts'] if catalyst_data else []
                        })
                        
                        print(f"✅ {strategy['strategy_type']} (Score: {strategy['confidence']:.0f})")
                    else:
                        print("⏭️  Skip")
                
                except Exception as e:
                    print(f"Error: {e}")
                    continue
        
        # Sort by total score
        discoveries_sorted = sorted(discoveries, key=lambda x: x['total_score'], reverse=True)
        
        print("\n" + "="*70)
        print(f"✅ Discovery Complete: Found {len(discoveries_sorted)} opportunities")
        print("="*70)
        
        return discoveries_sorted
    
    def format_discovery_report(self, discoveries, top_n=10):
        """
        Format discoveries into a readable report
        """
        report = []
        report.append("\n" + "="*70)
        report.append("🔍 HIDDEN GEM DISCOVERIES")
        report.append(f"Top {min(top_n, len(discoveries))} Breakthrough Opportunities")
        report.append("="*70)
        report.append("")
        
        for idx, discovery in enumerate(discoveries[:top_n], 1):
            symbol = discovery['symbol']
            strategy = discovery['strategy']
            
            report.append(f"{idx}. {symbol} - {discovery['sector']}")
            report.append(f"   Price: ${discovery['price']:.2f}")
            report.append(f"   Overall Score: {discovery['total_score']:.0f}/100")
            report.append(f"   Technical: {discovery['technical_score']:.0f} | Catalyst: {discovery['catalyst_score']:.0f}")
            report.append("")
            report.append(f"   🎯 STRATEGY: {strategy['strategy_type']}")
            report.append(f"   ⏰ Time Horizon: {strategy['time_horizon']}")
            report.append(f"   💰 Position Size: {strategy['position_size']}")
            report.append(f"   ⚠️  Risk Level: {strategy['risk_level']}")
            report.append("")
            report.append(f"   📈 Entry: {strategy['entry_strategy']}")
            report.append(f"   📉 Exit: {strategy['exit_strategy']}")
            report.append("")
            report.append(f"   💡 Why: {strategy['rationale']}")
            
            # Show catalysts
            if discovery['catalysts']:
                report.append(f"\n   🔥 Catalysts Found:")
                for catalyst in discovery['catalysts'][:3]:
                    report.append(f"      • {catalyst['type']}: {catalyst['title'][:60]}...")
            
            report.append("")
            report.append("-" * 70)
            report.append("")
        
        return "\n".join(report)
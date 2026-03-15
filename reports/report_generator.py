# reports/report_generator.py
"""
Personalized Report Generator
Focuses on YOUR portfolio and watchlist
"""

from datetime import datetime, timedelta
import pandas as pd
from analysis.discovery_engine import DiscoveryEngine

class ReportGenerator:
    """Generate personalized portfolio reports"""
    
    def __init__(self, db_manager, analyzer, recommender, news_scraper=None):
        self.db = db_manager
        self.analyzer = analyzer
        self.recommender = recommender
        self.news_scraper = news_scraper
        
        # Initialize discovery engine if news scraper is available
        if news_scraper:
            self.discovery = DiscoveryEngine(db_manager, analyzer, news_scraper)
        else:
            self.discovery = None
        
        print("📊 Report Generator initialized")
    
    def generate_daily_report(self):
        """
        DAILY REPORT - Your Portfolio Today
        Focus: Daily performance, immediate actions, breaking news
        """
        report = []
        report.append("=" * 70)
        report.append("📊 YOUR DAILY STOCK REPORT")
        report.append(f"Generated: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}")
        report.append("=" * 70)
        report.append("")
        
        # Import portfolio tracker
        from portfolio.portfolio_tracker import PortfolioTracker
        portfolio = PortfolioTracker(self.db)
        
        # ========== SECTION 1: YOUR PORTFOLIO ==========
        report.append("💼 YOUR PORTFOLIO TODAY")
        report.append("-" * 70)
        
        pf_value = portfolio.get_portfolio_value()
        
        if pf_value['current_value'] > 0:
            report.append(f"Portfolio Value: ${pf_value['current_value']:,.2f}")
            report.append(f"Total Cost Basis: ${pf_value['total_cost']:,.2f}")
            report.append(f"Total Gain/Loss: ${pf_value['gain_loss']:+,.2f} ({pf_value['gain_loss_pct']:+.2f}%)")
            report.append(f"Number of Holdings: {pf_value['num_positions']}")
            report.append("")
            
            # Individual holdings performance
            holdings = portfolio.get_holdings()
            
            if not holdings.empty:
                report.append("📈 YOUR HOLDINGS:")
                report.append("")
                
                # Sort by gain/loss %
                holdings_sorted = holdings.sort_values('gain_loss_pct', ascending=False)
                
                for _, holding in holdings_sorted.iterrows():
                    symbol = holding['symbol']
                    shares = holding['shares']
                    current_price = holding.get('current_price', 0)
                    avg_cost = holding['avg_cost']
                    gain_pct = holding.get('gain_loss_pct', 0)
                    gain_dollar = holding.get('gain_loss', 0)
                    
                    report.append("📈 YOUR HOLDINGS:")
                report.append("")
                
                # Sort by gain/loss %
                holdings_sorted = holdings.sort_values('gain_loss_pct', ascending=False)
                
                for _, holding in holdings_sorted.iterrows():
                    symbol = holding['symbol']
                    shares = holding['shares']
                    current_price = holding.get('current_price', 0)
                    avg_cost = holding['avg_cost']
                    gain_pct = holding.get('gain_loss_pct', 0)
                    gain_dollar = holding.get('gain_loss', 0)
                    
                    # Better status indicators
                    if gain_pct > 5:
                        status = "💚 UP"
                    elif gain_pct > 0:
                        status = "⬆️  UP"
                    elif gain_pct < -5:
                        status = "💔 DOWN"
                    elif gain_pct < 0:
                        status = "⬇️  DOWN"
                    else:
                        status = "➡️  FLAT"
                    
                    report.append(f"  {status} {symbol}:")
                    report.append(f"     Shares: {shares:.4f} | Avg Cost: ${avg_cost:.2f} | Current: ${current_price:.2f}")
                    report.append(f"     Gain/Loss: ${gain_dollar:+,.2f} ({gain_pct:+.2f}%)")
                    report.append("")
                    
                    report.append(f"  {status} {symbol}:")
                    report.append(f"     Shares: {shares:.4f} | Avg Cost: ${avg_cost:.2f} | Current: ${current_price:.2f}")
                    report.append(f"     Gain/Loss: ${gain_dollar:+,.2f} ({gain_pct:+.2f}%)")
                    report.append("")
        else:
            report.append("⚠️  No portfolio holdings found.")
            report.append("   Add transactions in the Portfolio Tracker to track performance!")
            report.append("")
        
        report.append("")
        
        # ========== SECTION 2: PORTFOLIO RECOMMENDATIONS ==========
        report.append("🎯 RECOMMENDATIONS FOR YOUR HOLDINGS")
        report.append("-" * 70)
        
        if pf_value['current_value'] > 0:
            holdings = portfolio.get_holdings()
            portfolio_recs = []
            
            for _, holding in holdings.iterrows():
                symbol = holding['symbol']
                
                # Get latest recommendation
                recs = self.db.get_latest_recommendations(days=7)
                stock_rec = recs[recs['symbol'] == symbol]
                
                if not stock_rec.empty:
                    rec = stock_rec.iloc[0]
                    portfolio_recs.append({
                        'symbol': symbol,
                        'recommendation': rec['recommendation'],
                        'score': rec['score'],
                        'current_value': holding.get('current_value', 0),
                        'gain_pct': holding.get('gain_loss_pct', 0)
                    })
                else:
                    # Generate fresh recommendation
                    result = self.recommender.analyze_and_recommend(symbol)
                    if result:
                        portfolio_recs.append({
                            'symbol': symbol,
                            'recommendation': result['recommendation'],
                            'score': result['score'],
                            'current_value': holding.get('current_value', 0),
                            'gain_pct': holding.get('gain_loss_pct', 0)
                        })
            
            # Group by recommendation
            sells = [r for r in portfolio_recs if 'SELL' in r['recommendation']]
            holds = [r for r in portfolio_recs if 'HOLD' in r['recommendation']]
            buys = [r for r in portfolio_recs if 'BUY' in r['recommendation']]
            
            if sells:
                report.append("⚠️  CONSIDER SELLING:")
                for rec in sells:
                    report.append(f"   • {rec['symbol']}: {rec['recommendation']} (Score: {rec['score']:.0f}/100)")
                    report.append(f"     Current Gain: {rec['gain_pct']:+.2f}% | Value: ${rec['current_value']:,.2f}")
                report.append("")
            
            if buys:
                report.append("💰 CONSIDER BUYING MORE:")
                for rec in buys:
                    report.append(f"   • {rec['symbol']}: {rec['recommendation']} (Score: {rec['score']:.0f}/100)")
                    report.append(f"     Current Gain: {rec['gain_pct']:+.2f}%")
                report.append("")
            
            if holds:
                report.append("✋ HOLD POSITIONS:")
                for rec in holds:
                    report.append(f"   • {rec['symbol']}: Score {rec['score']:.0f}/100 | Gain: {rec['gain_pct']:+.2f}%")
                report.append("")
        else:
            report.append("No portfolio holdings to analyze.")
            report.append("")
        
        report.append("")
        
        # ========== SECTION 3: WATCHLIST OPPORTUNITIES ==========
        report.append("⭐ WATCHLIST OPPORTUNITIES")
        report.append("-" * 70)
        
        watchlist = self.db.get_watchlist()
        
        if not watchlist.empty:
            report.append(f"Tracking {len(watchlist)} stocks on your watchlist")
            report.append("")
            
            # Get recommendations for watchlist stocks (not in portfolio)
            watchlist_recs = self.db.get_latest_recommendations(days=7)
            
            # Filter to watchlist stocks only
            watchlist_symbols = set(watchlist['symbol'].tolist())
            
            # Remove portfolio holdings from watchlist recommendations
            if pf_value['current_value'] > 0:
                holdings = portfolio.get_holdings()
                portfolio_symbols = set(holdings['symbol'].tolist())
                watchlist_symbols = watchlist_symbols - portfolio_symbols
            
            watchlist_recs = watchlist_recs[watchlist_recs['symbol'].isin(watchlist_symbols)]
            
            # Show BUY opportunities
            buys = watchlist_recs[watchlist_recs['recommendation'].str.contains('BUY')]
            
            if not buys.empty:
                buys_sorted = buys.sort_values('score', ascending=False)
                
                report.append("🔥 TOP BUY OPPORTUNITIES:")
                for _, rec in buys_sorted.head(5).iterrows():
                    report.append(f"   • {rec['symbol']}: {rec['recommendation']} (Score: {rec['score']:.0f}/100)")
                    report.append(f"     Price: ${rec['price_at_recommendation']:.2f} | Date: {rec['date']}")
                report.append("")
            else:
                report.append("No strong BUY signals in your watchlist right now.")
                report.append("")
        else:
            report.append("⚠️  Your watchlist is empty!")
            report.append("   Add stocks from the Stock Categories page to track opportunities.")
            report.append("")
        
        report.append("")
        
       # ========== SECTION 4: HIDDEN GEM DISCOVERIES ==========
        report.append("🔍 BREAKTHROUGH DISCOVERIES & HIDDEN GEMS")
        report.append("-" * 70)
        
        if self.discovery:
            try:
                # Run discovery on niche sectors
                discoveries = self.discovery.discover_hidden_gems(
                    sectors_to_scan=['QUANTUM', 'AI_SMALL_CAP', 'BIOTECH_EMERGING', 'SPACE_NEW']
                )
                
                if discoveries:
                    # Show top 5 discoveries
                    for idx, disc in enumerate(discoveries[:5], 1):
                        strategy = disc['strategy']
                        
                        report.append(f"{idx}. {disc['symbol']} ({disc['sector']})")
                        report.append(f"   💰 Price: ${disc['price']:.2f} | Score: {disc['total_score']:.0f}/100")
                        report.append(f"   🎯 {strategy['strategy_type']} | ⏰ {strategy['time_horizon']}")
                        report.append(f"   📈 Entry: {strategy['entry_strategy']}")
                        report.append(f"   💡 {strategy['rationale']}")
                        
                        # Show key catalyst
                        if disc['catalysts']:
                            top_catalyst = disc['catalysts'][0]
                            report.append(f"   🔥 Catalyst: {top_catalyst['title'][:60]}...")
                        
                        report.append("")
                else:
                    report.append("No significant breakthrough opportunities found today.")
                    report.append("Check back tomorrow for new discoveries!")
                    report.append("")
            
            except Exception as e:
                report.append(f"Discovery scan temporarily unavailable: {str(e)}")
                report.append("")
        else:
            report.append("💡 Enable News API to activate breakthrough discovery!")
            report.append("")
        
        report.append("")
       
        # ========== SECTION 4: RECENT NEWS & MARKET MOVERS ==========
        report.append("📰 RECENT NEWS AFFECTING YOUR STOCKS")
        report.append("-" * 70)
        
        # Get news for portfolio holdings
        news_found = False
        
        if pf_value['current_value'] > 0:
            holdings = portfolio.get_holdings()
            
            for _, holding in holdings.head(5).iterrows():  # Top 5 holdings
                symbol = holding['symbol']
                recent_news = self.db.get_recent_news(symbol=symbol, days=3, limit=3)
                
                if not recent_news.empty:
                    news_found = True
                    report.append(f"📌 {symbol}:")
                    for _, article in recent_news.iterrows():
                        report.append(f"   • {article['title']}")
                        report.append(f"     Source: {article['source']} | {article['published_at'][:10]}")
                    report.append("")
        
        # General market news
        market_news = self.db.get_recent_news(symbol=None, days=1, limit=5)
        
        if not market_news.empty:
            news_found = True
            report.append("🌍 BROADER MARKET NEWS:")
            for _, article in market_news.head(3).iterrows():
                report.append(f"   • {article['title']}")
                report.append(f"     {article['source']}")
            report.append("")
        
        if not news_found:
            report.append("No recent news available.")
            report.append("💡 Tip: Use the News page to fetch latest articles!")
            report.append("")
        
        report.append("")
        
        # ========== FOOTER ==========
        report.append("=" * 70)
        report.append("💡 ACTION ITEMS FOR TODAY:")
        report.append("   1. Review any SELL recommendations for your holdings")
        report.append("   2. Check BUY opportunities in your watchlist")
        report.append("   3. Set price alerts for stocks near entry points")
        report.append("=" * 70)
        report.append("")
        report.append("⚠️  DISCLAIMER: This is automated analysis for informational purposes only.")
        report.append("    Always do your own research before making investment decisions.")
        report.append("")
        
        full_report = "\n".join(report)
        
        # Save to database
        try:
            self.db.save_report('DAILY', full_report)
        except:
            pass  # If save fails, still return the report
        
        return full_report
    
    def generate_weekly_report(self):
        """
        WEEKLY REPORT - Your 7-Day Performance
        Focus: Weekly trends, momentum, strategic moves
        """
        report = []
        report.append("=" * 70)
        report.append("📊 YOUR WEEKLY STOCK REPORT")
        report.append(f"Week Ending: {datetime.now().strftime('%B %d, %Y')}")
        report.append("=" * 70)
        report.append("")
        
        from portfolio.portfolio_tracker import PortfolioTracker
        portfolio = PortfolioTracker(self.db)
        
        # Portfolio summary
        report.append("💼 PORTFOLIO WEEKLY PERFORMANCE")
        report.append("-" * 70)
        
        pf_value = portfolio.get_portfolio_value()
        
        if pf_value['current_value'] > 0:
            report.append(f"Current Value: ${pf_value['current_value']:,.2f}")
            report.append(f"Total Return: {pf_value['gain_loss_pct']:+.2f}%")
            report.append("")
            
            holdings = portfolio.get_holdings()
            
            if not holdings.empty:
                # Best/Worst performers
                best = holdings.loc[holdings['gain_loss_pct'].idxmax()] if 'gain_loss_pct' in holdings.columns else None
                worst = holdings.loc[holdings['gain_loss_pct'].idxmin()] if 'gain_loss_pct' in holdings.columns else None
                
                if best is not None:
                    report.append(f"🏆 Best Performer: {best['symbol']} ({best['gain_loss_pct']:+.2f}%)")
                if worst is not None:
                    report.append(f"📉 Worst Performer: {worst['symbol']} ({worst['gain_loss_pct']:+.2f}%)")
                report.append("")
        
        # Recommendations summary
        report.append("🎯 RECOMMENDATIONS THIS WEEK")
        report.append("-" * 70)
        
        recs = self.db.get_latest_recommendations(days=7)
        
        if not recs.empty:
            buy_count = len(recs[recs['recommendation'].str.contains('BUY')])
            sell_count = len(recs[recs['recommendation'].str.contains('SELL')])
            hold_count = len(recs[recs['recommendation'].str.contains('HOLD')])
            
            report.append(f"Total Recommendations: {len(recs)}")
            report.append(f"  • BUY signals: {buy_count}")
            report.append(f"  • SELL signals: {sell_count}")
            report.append(f"  • HOLD signals: {hold_count}")
            report.append("")
            
            # Top opportunities
            top_buys = recs[recs['recommendation'].str.contains('BUY')].nlargest(5, 'score')
            
            if not top_buys.empty:
                report.append("🔥 TOP 5 OPPORTUNITIES:")
                for _, rec in top_buys.iterrows():
                    report.append(f"   {rec['symbol']}: {rec['recommendation']} (Score: {rec['score']:.0f}/100) - ${rec['price_at_recommendation']:.2f}")
                report.append("")
        
        report.append("=" * 70)
        report.append("This report covers the past 7 days of market activity.")
        report.append("=" * 70)
        
        full_report = "\n".join(report)
        
        try:
            self.db.save_report('WEEKLY', full_report)
        except:
            pass
        
        return full_report
    
    def generate_monthly_report(self):
        """
        MONTHLY REPORT - Strategic Overview
        Focus: Long-term trends, portfolio health, rebalancing
        """
        report = []
        report.append("=" * 70)
        report.append("📊 YOUR MONTHLY STOCK REPORT")
        report.append(f"Month: {datetime.now().strftime('%B %Y')}")
        report.append("=" * 70)
        report.append("")
        
        from portfolio.portfolio_tracker import PortfolioTracker
        portfolio = PortfolioTracker(self.db)
        
        # Portfolio analysis
        report.append("💼 PORTFOLIO HEALTH CHECK")
        report.append("-" * 70)
        
        pf_value = portfolio.get_portfolio_value()
        
        if pf_value['current_value'] > 0:
            report.append(f"Portfolio Value: ${pf_value['current_value']:,.2f}")
            report.append(f"Total Return: {pf_value['gain_loss_pct']:+.2f}%")
            report.append(f"Number of Positions: {pf_value['num_positions']}")
            report.append("")
            
            # Diversification check
            holdings = portfolio.get_holdings()
            
            if not holdings.empty and 'current_value' in holdings.columns:
                # Calculate concentration
                total_value = holdings['current_value'].sum()
                holdings['weight'] = (holdings['current_value'] / total_value) * 100
                
                report.append("📊 PORTFOLIO ALLOCATION:")
                for _, holding in holdings.sort_values('weight', ascending=False).iterrows():
                    report.append(f"   {holding['symbol']}: {holding['weight']:.1f}%")
                report.append("")
                
                # Concentration warning
                max_weight = holdings['weight'].max()
                if max_weight > 30:
                    report.append(f"⚠️  CONCENTRATION WARNING:")
                    report.append(f"   {holdings.loc[holdings['weight'].idxmax(), 'symbol']} represents {max_weight:.1f}% of your portfolio")
                    report.append(f"   Consider rebalancing for better diversification")
                    report.append("")
        
        # Monthly recommendations
        report.append("🎯 30-DAY RECOMMENDATION SUMMARY")
        report.append("-" * 70)
        
        recs = self.db.get_latest_recommendations(days=30)
        
        if not recs.empty:
            report.append(f"Total Stocks Analyzed: {recs['symbol'].nunique()}")
            report.append(f"Total Recommendations: {len(recs)}")
            report.append("")
            
            # Top 10 opportunities
            top_picks = recs[recs['recommendation'].str.contains('BUY')].nlargest(10, 'score')
            
            if not top_picks.empty:
                report.append("🏆 TOP 10 OPPORTUNITIES THIS MONTH:")
                for idx, rec in enumerate(top_picks.iterrows(), 1):
                    _, r = rec
                    report.append(f"   {idx}. {r['symbol']}: Score {r['score']:.0f}/100 - ${r['price_at_recommendation']:.2f}")
                report.append("")
        
        report.append("=" * 70)
        report.append("Strategic monthly overview - Use this for long-term planning")
        report.append("=" * 70)
        
        full_report = "\n".join(report)
        
        try:
            self.db.save_report('MONTHLY', full_report)
        except:
            pass
        
        return full_report
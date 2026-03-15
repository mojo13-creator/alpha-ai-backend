# analysis/backtester.py
"""
Backtesting Engine - Test how recommendations performed
"""

import pandas as pd
from datetime import datetime, timedelta

class Backtester:
    """Backtest recommendation performance"""
    
    def __init__(self, db_manager):
        self.db = db_manager
        print("📊 Backtester initialized")
    
    def test_recommendation_performance(self, days_back=30):
        """
        Test how recommendations from the past performed
        Returns win rate, average gain, etc.
        """
        print(f"\n📊 Backtesting recommendations from last {days_back} days...")
        
        # Get recommendations
        recs = self.db.get_latest_recommendations(days=days_back)
        
        if recs.empty:
            print("⚠️  No recommendations to backtest")
            return None
        
        results = []
        
        for _, rec in recs.iterrows():
            symbol = rec['symbol']
            rec_date = pd.to_datetime(rec['date'])
            entry_price = rec['price_at_recommendation']
            recommendation = rec['recommendation']
            
            # Get current price
            current = self.db.get_latest_price(symbol)
            
            if current:
                exit_price = current['price']
                
                # Calculate return
                if 'BUY' in recommendation:
                    # For buy recommendations, profit = price increase
                    returns = ((exit_price - entry_price) / entry_price) * 100
                elif 'SELL' in recommendation:
                    # For sell recommendations, profit = price decrease
                    returns = ((entry_price - exit_price) / entry_price) * 100
                else:  # HOLD
                    returns = 0
                
                # Determine if trade was successful
                success = False
                if 'BUY' in recommendation and returns > 0:
                    success = True
                elif 'SELL' in recommendation and returns > 0:
                    success = True
                elif 'HOLD' in recommendation:
                    success = None  # Neutral
                
                results.append({
                    'symbol': symbol,
                    'date': rec_date,
                    'recommendation': recommendation,
                    'entry_price': entry_price,
                    'exit_price': exit_price,
                    'returns_pct': returns,
                    'success': success,
                    'days_held': (datetime.now() - rec_date).days
                })
        
        results_df = pd.DataFrame(results)
        
        # Calculate statistics
        buy_recs = results_df[results_df['recommendation'].str.contains('BUY')]
        sell_recs = results_df[results_df['recommendation'].str.contains('SELL')]
        
        stats = {
            'total_trades': len(results_df),
            'buy_trades': len(buy_recs),
            'sell_trades': len(sell_recs),
            'avg_return': results_df['returns_pct'].mean(),
            'win_rate': (results_df['success'] == True).sum() / len(results_df) * 100 if len(results_df) > 0 else 0,
            'best_trade': results_df.loc[results_df['returns_pct'].idxmax()] if not results_df.empty else None,
            'worst_trade': results_df.loc[results_df['returns_pct'].idxmin()] if not results_df.empty else None,
            'avg_buy_return': buy_recs['returns_pct'].mean() if not buy_recs.empty else 0,
            'avg_sell_return': sell_recs['returns_pct'].mean() if not sell_recs.empty else 0
        }
        
        print(f"\n📊 BACKTEST RESULTS:")
        print(f"   Total Trades: {stats['total_trades']}")
        print(f"   Win Rate: {stats['win_rate']:.1f}%")
        print(f"   Avg Return: {stats['avg_return']:.2f}%")
        print(f"   Buy Recs Avg Return: {stats['avg_buy_return']:.2f}%")
        print(f"   Sell Recs Avg Return: {stats['avg_sell_return']:.2f}%")
        
        return {
            'results': results_df,
            'stats': stats
        }
    
    def simulate_portfolio(self, initial_capital=10000, days_back=30):
        """
        Simulate trading a portfolio based on recommendations
        """
        print(f"\n💰 Simulating portfolio with ${initial_capital:,.0f} starting capital...")
        
        recs = self.db.get_latest_recommendations(days=days_back)
        
        if recs.empty:
            return None
        
        # Sort by date
        recs = recs.sort_values('date')
        
        cash = initial_capital
        holdings = {}
        trades = []
        portfolio_value = []
        
        for _, rec in recs.iterrows():
            symbol = rec['symbol']
            price = rec['price_at_recommendation']
            recommendation = rec['recommendation']
            
            if 'BUY' in recommendation:
                # Buy with 10% of portfolio
                buy_amount = cash * 0.10
                shares = buy_amount / price
                
                if symbol in holdings:
                    holdings[symbol]['shares'] += shares
                    holdings[symbol]['avg_price'] = (
                        (holdings[symbol]['avg_price'] * holdings[symbol]['shares'] + buy_amount) /
                        (holdings[symbol]['shares'] + shares)
                    )
                else:
                    holdings[symbol] = {
                        'shares': shares,
                        'avg_price': price
                    }
                
                cash -= buy_amount
                trades.append({
                    'date': rec['date'],
                    'action': 'BUY',
                    'symbol': symbol,
                    'shares': shares,
                    'price': price,
                    'value': buy_amount
                })
            
            elif 'SELL' in recommendation and symbol in holdings:
                # Sell all shares
                shares = holdings[symbol]['shares']
                sell_value = shares * price
                cash += sell_value
                
                profit = sell_value - (holdings[symbol]['avg_price'] * shares)
                
                trades.append({
                    'date': rec['date'],
                    'action': 'SELL',
                    'symbol': symbol,
                    'shares': shares,
                    'price': price,
                    'value': sell_value,
                    'profit': profit
                })
                
                del holdings[symbol]
        
        # Calculate final portfolio value
        final_value = cash
        for symbol, holding in holdings.items():
            current = self.db.get_latest_price(symbol)
            if current:
                final_value += holding['shares'] * current['price']
        
        total_return = ((final_value - initial_capital) / initial_capital) * 100
        
        print(f"\n💰 PORTFOLIO SIMULATION RESULTS:")
        print(f"   Starting Capital: ${initial_capital:,.2f}")
        print(f"   Final Value: ${final_value:,.2f}")
        print(f"   Total Return: {total_return:+.2f}%")
        print(f"   Trades Made: {len(trades)}")
        
        return {
            'initial_capital': initial_capital,
            'final_value': final_value,
            'total_return': total_return,
            'trades': pd.DataFrame(trades),
            'current_holdings': holdings
        }
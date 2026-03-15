
# analysis/stock_screener.py
"""
Enhanced Stock Screener
Find stocks matching technical criteria with advanced filters
"""

import pandas as pd
from datetime import datetime, timedelta

class StockScreener:
    """Advanced stock screener with multiple strategies"""
    
    def __init__(self, db_manager, analyzer):
        self.db = db_manager
        self.analyzer = analyzer
        print("🔍 Stock Screener initialized")
    
    def get_scannable_stocks(self):
        """Get all stocks with sufficient data for screening"""
        all_symbols = self.db.get_all_symbols()
        
        # Filter to stocks with recent data
        valid_stocks = []
        for symbol in all_symbols:
            latest = self.db.get_latest_price(symbol)
            if latest:
                valid_stocks.append(symbol)
        
        return valid_stocks
    
    def screen_oversold_stocks(self, rsi_threshold=30):
        """Find oversold stocks (RSI below threshold)"""
        print(f"\n🔍 Screening for oversold stocks (RSI < {rsi_threshold})...")
        
        stocks = self.get_scannable_stocks()
        results = []
        
        for symbol in stocks:
            try:
                df = self.analyzer.calculate_all_indicators(symbol)
                
                if df is None or df.empty:
                    continue
                
                latest = df.iloc[-1]
                rsi = latest.get('RSI', 50)
                
                if rsi < rsi_threshold:
                    results.append({
                        'symbol': symbol,
                        'price': latest['close'],
                        'rsi': rsi,
                        'sma_20': latest.get('SMA_20', 0),
                        'volume': latest['volume'],
                        'signal': f"Oversold (RSI: {rsi:.1f})"
                    })
            
            except Exception as e:
                continue
        
        df = pd.DataFrame(results)
        
        if not df.empty:
            df = df.sort_values('rsi')
        
        print(f"✅ Found {len(df)} oversold stocks")
        return df
    
    def screen_overbought_stocks(self, rsi_threshold=70):
        """Find overbought stocks (RSI above threshold)"""
        print(f"\n🔍 Screening for overbought stocks (RSI > {rsi_threshold})...")
        
        stocks = self.get_scannable_stocks()
        results = []
        
        for symbol in stocks:
            try:
                df = self.analyzer.calculate_all_indicators(symbol)
                
                if df is None or df.empty:
                    continue
                
                latest = df.iloc[-1]
                rsi = latest.get('RSI', 50)
                
                if rsi > rsi_threshold:
                    results.append({
                        'symbol': symbol,
                        'price': latest['close'],
                        'rsi': rsi,
                        'signal': f"Overbought (RSI: {rsi:.1f})"
                    })
            
            except Exception as e:
                continue
        
        df = pd.DataFrame(results)
        
        if not df.empty:
            df = df.sort_values('rsi', ascending=False)
        
        print(f"✅ Found {len(df)} overbought stocks")
        return df
    
    def screen_golden_cross(self):
        """Find stocks with golden cross (50-MA > 200-MA)"""
        print("\n🔍 Screening for golden cross patterns...")
        
        stocks = self.get_scannable_stocks()
        results = []
        
        for symbol in stocks:
            try:
                df = self.analyzer.calculate_all_indicators(symbol)
                
                if df is None or df.empty or len(df) < 200:
                    continue
                
                latest = df.iloc[-1]
                sma_50 = latest.get('SMA_50', 0)
                sma_200 = latest.get('SMA_200', 0)
                
                if sma_50 > sma_200 and sma_50 > 0 and sma_200 > 0:
                    strength = ((sma_50 - sma_200) / sma_200) * 100
                    
                    results.append({
                        'symbol': symbol,
                        'price': latest['close'],
                        'sma_50': sma_50,
                        'sma_200': sma_200,
                        'strength': strength,
                        'signal': f"Golden Cross ({strength:.1f}% separation)"
                    })
            
            except Exception as e:
                continue
        
        df = pd.DataFrame(results)
        
        if not df.empty:
            df = df.sort_values('strength', ascending=False)
        
        print(f"✅ Found {len(df)} golden cross stocks")
        return df
    
    def screen_death_cross(self):
        """Find stocks with death cross (50-MA < 200-MA)"""
        print("\n🔍 Screening for death cross patterns...")
        
        stocks = self.get_scannable_stocks()
        results = []
        
        for symbol in stocks:
            try:
                df = self.analyzer.calculate_all_indicators(symbol)
                
                if df is None or df.empty or len(df) < 200:
                    continue
                
                latest = df.iloc[-1]
                sma_50 = latest.get('SMA_50', 0)
                sma_200 = latest.get('SMA_200', 0)
                
                if sma_50 < sma_200 and sma_50 > 0 and sma_200 > 0:
                    strength = ((sma_200 - sma_50) / sma_200) * 100
                    
                    results.append({
                        'symbol': symbol,
                        'price': latest['close'],
                        'sma_50': sma_50,
                        'sma_200': sma_200,
                        'strength': strength,
                        'signal': f"Death Cross ({strength:.1f}% separation)"
                    })
            
            except Exception as e:
                continue
        
        df = pd.DataFrame(results)
        
        if not df.empty:
            df = df.sort_values('strength', ascending=False)
        
        print(f"✅ Found {len(df)} death cross stocks")
        return df
    
    def screen_volume_spike(self, volume_multiplier=2.0):
        """Find stocks with unusual volume"""
        print(f"\n🔍 Screening for volume spikes ({volume_multiplier}x average)...")
        
        stocks = self.get_scannable_stocks()
        results = []
        
        for symbol in stocks:
            try:
                df = self.analyzer.calculate_all_indicators(symbol)
                
                if df is None or df.empty or len(df) < 20:
                    continue
                
                latest = df.iloc[-1]
                avg_volume = df['volume'].tail(20).mean()
                current_volume = latest['volume']
                
                if avg_volume > 0:
                    volume_ratio = current_volume / avg_volume
                    
                    if volume_ratio >= volume_multiplier:
                        results.append({
                            'symbol': symbol,
                            'price': latest['close'],
                            'volume': current_volume,
                            'avg_volume': avg_volume,
                            'volume_ratio': volume_ratio,
                            'signal': f"{volume_ratio:.1f}x average volume"
                        })
            
            except Exception as e:
                continue
        
        df = pd.DataFrame(results)
        
        if not df.empty:
            df = df.sort_values('volume_ratio', ascending=False)
        
        print(f"✅ Found {len(df)} volume spike stocks")
        return df
    
    def screen_price_near_52w_high(self, threshold_pct=5):
        """Find stocks near 52-week highs"""
        print(f"\n🔍 Screening for stocks near 52-week highs (within {threshold_pct}%)...")
        
        stocks = self.get_scannable_stocks()
        results = []
        
        for symbol in stocks:
            try:
                df = self.analyzer.calculate_all_indicators(symbol)
                
                if df is None or df.empty or len(df) < 252:
                    continue
                
                latest = df.iloc[-1]
                price = latest['close']
                high_52w = df['high'].tail(252).max()
                
                distance_pct = ((high_52w - price) / high_52w) * 100
                
                if distance_pct <= threshold_pct:
                    results.append({
                        'symbol': symbol,
                        'price': price,
                        '52w_high': high_52w,
                        'distance_pct': distance_pct,
                        'signal': f"{distance_pct:.1f}% from 52-week high"
                    })
            
            except Exception as e:
                continue
        
        df = pd.DataFrame(results)
        
        if not df.empty:
            df = df.sort_values('distance_pct')
        
        print(f"✅ Found {len(df)} stocks near 52-week highs")
        return df
    
    def screen_price_near_52w_low(self, threshold_pct=5):
        """Find stocks near 52-week lows (potential value plays)"""
        print(f"\n🔍 Screening for stocks near 52-week lows (within {threshold_pct}%)...")
        
        stocks = self.get_scannable_stocks()
        results = []
        
        for symbol in stocks:
            try:
                df = self.analyzer.calculate_all_indicators(symbol)
                
                if df is None or df.empty or len(df) < 252:
                    continue
                
                latest = df.iloc[-1]
                price = latest['close']
                low_52w = df['low'].tail(252).min()
                
                distance_pct = ((price - low_52w) / low_52w) * 100
                
                if distance_pct <= threshold_pct:
                    results.append({
                        'symbol': symbol,
                        'price': price,
                        '52w_low': low_52w,
                        'distance_pct': distance_pct,
                        'signal': f"{distance_pct:.1f}% from 52-week low"
                    })
            
            except Exception as e:
                continue
        
        df = pd.DataFrame(results)
        
        if not df.empty:
            df = df.sort_values('distance_pct')
        
        print(f"✅ Found {len(df)} stocks near 52-week lows")
        return df
    
    def screen_macd_bullish_crossover(self):
        """Find stocks with recent MACD bullish crossover"""
        print("\n🔍 Screening for MACD bullish crossovers...")
        
        stocks = self.get_scannable_stocks()
        results = []
        
        for symbol in stocks:
            try:
                df = self.analyzer.calculate_all_indicators(symbol)
                
                if df is None or df.empty or len(df) < 2:
                    continue
                
                latest = df.iloc[-1]
                prev = df.iloc[-2]
                
                macd_curr = latest.get('MACD', 0)
                signal_curr = latest.get('MACD_Signal', 0)
                macd_prev = prev.get('MACD', 0)
                signal_prev = prev.get('MACD_Signal', 0)
                
                # Bullish crossover: MACD crosses above signal
                if macd_curr > signal_curr and macd_prev <= signal_prev:
                    strength = macd_curr - signal_curr
                    
                    results.append({
                        'symbol': symbol,
                        'price': latest['close'],
                        'macd': macd_curr,
                        'signal_line': signal_curr,
                        'strength': strength,
                        'signal': f"MACD Bullish Crossover (strength: {strength:.2f})"
                    })
            
            except Exception as e:
                continue
        
        df = pd.DataFrame(results)
        
        if not df.empty:
            df = df.sort_values('strength', ascending=False)
        
        print(f"✅ Found {len(df)} MACD bullish crossovers")
        return df
    
    def screen_strong_uptrend(self):
        """Find stocks in strong uptrends (price > all MAs)"""
        print("\n🔍 Screening for strong uptrends...")
        
        stocks = self.get_scannable_stocks()
        results = []
        
        for symbol in stocks:
            try:
                df = self.analyzer.calculate_all_indicators(symbol)
                
                if df is None or df.empty or len(df) < 200:
                    continue
                
                latest = df.iloc[-1]
                price = latest['close']
                sma_20 = latest.get('SMA_20', 0)
                sma_50 = latest.get('SMA_50', 0)
                sma_200 = latest.get('SMA_200', 0)
                
                # Strong uptrend: price above all major MAs
                if price > sma_20 > sma_50 > sma_200 and sma_200 > 0:
                    distance_from_200 = ((price - sma_200) / sma_200) * 100
                    
                    results.append({
                        'symbol': symbol,
                        'price': price,
                        'sma_20': sma_20,
                        'sma_50': sma_50,
                        'sma_200': sma_200,
                        'strength': distance_from_200,
                        'signal': f"Strong uptrend ({distance_from_200:.1f}% above 200-MA)"
                    })
            
            except Exception as e:
                continue
        
        df = pd.DataFrame(results)
        
        if not df.empty:
            df = df.sort_values('strength', ascending=False)
        
        print(f"✅ Found {len(df)} stocks in strong uptrends")
        return df
    
    def screen_high_momentum(self):
        """Find stocks with strong recent momentum"""
        print("\n🔍 Screening for high momentum stocks...")
        
        stocks = self.get_scannable_stocks()
        results = []
        
        for symbol in stocks:
            try:
                df = self.analyzer.calculate_all_indicators(symbol)
                
                if df is None or df.empty or len(df) < 20:
                    continue
                
                latest = df.iloc[-1]
                price_20d_ago = df.iloc[-20]['close']
                
                momentum_pct = ((latest['close'] - price_20d_ago) / price_20d_ago) * 100
                
                if momentum_pct > 10:  # 10%+ gain in 20 days
                    results.append({
                        'symbol': symbol,
                        'price': latest['close'],
                        'momentum_20d': momentum_pct,
                        'rsi': latest.get('RSI', 50),
                        'signal': f"{momentum_pct:+.1f}% in 20 days"
                    })
            
            except Exception as e:
                continue
        
        df = pd.DataFrame(results)
        
        if not df.empty:
            df = df.sort_values('momentum_20d', ascending=False)
        
        print(f"✅ Found {len(df)} high momentum stocks")
        return df
    
    def screen_custom(self, criteria):
        """Custom screener with multiple criteria"""
        print("\n🔍 Running custom screen...")
        
        stocks = self.get_scannable_stocks()
        results = []
        
        for symbol in stocks:
            try:
                df = self.analyzer.calculate_all_indicators(symbol)
                
                if df is None or df.empty:
                    continue
                
                latest = df.iloc[-1]
                
                # Check all criteria
                passes = True
                
                if 'rsi_min' in criteria and latest.get('RSI', 50) < criteria['rsi_min']:
                    passes = False
                
                if 'rsi_max' in criteria and latest.get('RSI', 50) > criteria['rsi_max']:
                    passes = False
                
                if 'price_min' in criteria and latest['close'] < criteria['price_min']:
                    passes = False
                
                if 'price_max' in criteria and latest['close'] > criteria['price_max']:
                    passes = False
                
                if 'volume_min' in criteria and latest['volume'] < criteria['volume_min']:
                    passes = False
                
                if 'above_sma_200' in criteria and criteria['above_sma_200']:
                    if latest['close'] <= latest.get('SMA_200', 0):
                        passes = False
                
                if 'golden_cross' in criteria and criteria['golden_cross']:
                    if latest.get('SMA_50', 0) <= latest.get('SMA_200', 0):
                        passes = False
                
                if passes:
                    results.append({
                        'symbol': symbol,
                        'price': latest['close'],
                        'rsi': latest.get('RSI', 50),
                        'volume': latest['volume'],
                        'signal': "Meets all criteria"
                    })
            
            except Exception as e:
                continue
        
        df = pd.DataFrame(results)
        print(f"✅ Found {len(df)} stocks matching criteria")
        return df
    
    def run_all_screens(self):
        """Run all screening strategies"""
        print("\n🔍 Running ALL screening strategies...")
        
        results = {
            'oversold': self.screen_oversold_stocks(),
            'overbought': self.screen_overbought_stocks(),
            'golden_cross': self.screen_golden_cross(),
            'volume_spike': self.screen_volume_spike(),
            'near_52w_high': self.screen_price_near_52w_high(),
            'near_52w_low': self.screen_price_near_52w_low(),
            'macd_bullish': self.screen_macd_bullish_crossover(),
            'strong_uptrend': self.screen_strong_uptrend(),
            'high_momentum': self.screen_high_momentum()
        }
        
        return results
# analysis/technical_analysis.py
"""
Technical Analysis Module
Calculates technical indicators: RSI, MACD, Moving Averages, Bollinger Bands, etc.
"""

import pandas as pd
import numpy as np

class TechnicalAnalyzer:
    """Performs technical analysis on stock data"""
    
    def __init__(self, db_manager):
        self.db = db_manager
        print("📈 Technical Analyzer initialized")
    
    def calculate_sma(self, df, periods=[20, 50, 200]):
        """Calculate Simple Moving Averages"""
        for period in periods:
            df[f'SMA_{period}'] = df['close'].rolling(window=period).mean()
        return df
    
    def calculate_ema(self, df, periods=[12, 26]):
        """Calculate Exponential Moving Averages"""
        for period in periods:
            df[f'EMA_{period}'] = df['close'].ewm(span=period, adjust=False).mean()
        return df
    
    def calculate_rsi(self, df, period=14):
        """Calculate Relative Strength Index (RSI)"""
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))
        
        return df
    
    def calculate_macd(self, df):
        """Calculate MACD"""
        exp1 = df['close'].ewm(span=12, adjust=False).mean()
        exp2 = df['close'].ewm(span=26, adjust=False).mean()
        
        df['MACD'] = exp1 - exp2
        df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
        df['MACD_Histogram'] = df['MACD'] - df['MACD_Signal']
        
        return df
    
    def calculate_bollinger_bands(self, df, period=20, std_dev=2):
        """Calculate Bollinger Bands"""
        df['BB_Middle'] = df['close'].rolling(window=period).mean()
        std = df['close'].rolling(window=period).std()
        
        df['BB_Upper'] = df['BB_Middle'] + (std * std_dev)
        df['BB_Lower'] = df['BB_Middle'] - (std * std_dev)
        
        return df
    
    def calculate_atr(self, df, period=14):
        """Calculate Average True Range (ATR)"""
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = np.max(ranges, axis=1)
        
        df['ATR'] = true_range.rolling(window=period).mean()
        
        return df
    
    def calculate_stochastic(self, df, period=14):
        """Calculate Stochastic Oscillator"""
        low_min = df['low'].rolling(window=period).min()
        high_max = df['high'].rolling(window=period).max()
        
        df['STOCH'] = 100 * ((df['close'] - low_min) / (high_max - low_min))
        df['STOCH_Signal'] = df['STOCH'].rolling(window=3).mean()
        
        return df
    
    def calculate_adx(self, df, period=14):
        """Calculate Average Directional Index (ADX)"""
        df['high_diff'] = df['high'].diff()
        df['low_diff'] = df['low'].diff()

        df['+DM'] = np.where((df['high_diff'] > df['low_diff']) & (df['high_diff'] > 0), df['high_diff'], 0)
        df['-DM'] = np.where((df['low_diff'] > df['high_diff']) & (df['low_diff'] > 0), df['low_diff'], 0)

        if 'ATR' not in df.columns:
            df = self.calculate_atr(df, period)

        df['+DI'] = 100 * (df['+DM'].rolling(window=period).mean() / df['ATR'])
        df['-DI'] = 100 * (df['-DM'].rolling(window=period).mean() / df['ATR'])

        df['DX'] = 100 * np.abs(df['+DI'] - df['-DI']) / (df['+DI'] + df['-DI'])
        df['ADX'] = df['DX'].rolling(window=period).mean()

        df.drop(['high_diff', 'low_diff', '+DM', '-DM'], axis=1, inplace=True)

        return df

    def calculate_obv(self, df):
        """Calculate On-Balance Volume (OBV)"""
        obv = [0]
        for i in range(1, len(df)):
            if df['close'].iloc[i] > df['close'].iloc[i - 1]:
                obv.append(obv[-1] + df['volume'].iloc[i])
            elif df['close'].iloc[i] < df['close'].iloc[i - 1]:
                obv.append(obv[-1] - df['volume'].iloc[i])
            else:
                obv.append(obv[-1])
        df['OBV'] = obv
        df['OBV_SMA_20'] = df['OBV'].rolling(window=20).mean()
        return df

    def calculate_keltner_channels(self, df, period=20, atr_mult=1.5):
        """Calculate Keltner Channels for squeeze detection"""
        if 'ATR' not in df.columns:
            df = self.calculate_atr(df)
        ema = df['close'].ewm(span=period, adjust=False).mean()
        df['KC_Upper'] = ema + (atr_mult * df['ATR'])
        df['KC_Lower'] = ema - (atr_mult * df['ATR'])
        df['KC_Middle'] = ema
        return df
    
    def calculate_all_indicators(self, symbol, period='1y'):
        """Calculate ALL technical indicators for a stock"""
        print(f"\n🔍 Calculating technical indicators for {symbol.upper()}...")
        
        df = self.db.get_stock_prices(symbol)
        
        if df.empty:
            print(f"❌ No data found for {symbol}. Fetch data first!")
            return None
        
        df = df.sort_values('date')
        df = df.set_index('date')
        
        print("   📊 Calculating Moving Averages...")
        df = self.calculate_sma(df, [20, 50, 100, 200])
        df = self.calculate_ema(df, [9, 12, 21, 26])

        print("   📊 Calculating RSI...")
        df = self.calculate_rsi(df)

        print("   📊 Calculating MACD...")
        df = self.calculate_macd(df)

        print("   📊 Calculating Bollinger Bands...")
        df = self.calculate_bollinger_bands(df)

        print("   📊 Calculating ATR...")
        df = self.calculate_atr(df)

        print("   📊 Calculating Stochastic...")
        df = self.calculate_stochastic(df)

        print("   📊 Calculating ADX...")
        df = self.calculate_adx(df)

        print("   📊 Calculating OBV...")
        df = self.calculate_obv(df)

        print("   📊 Calculating Keltner Channels...")
        df = self.calculate_keltner_channels(df)

        print(f"✅ All indicators calculated for {symbol.upper()}")
        
        return df
    
    def get_trading_signals(self, df):
        """Generate trading signals based on technical indicators"""
        if df is None or df.empty:
            return None
        
        latest = df.iloc[-1]
        signals = []
        score = 50
        
        # RSI Signals
        if 'RSI' in df.columns and not pd.isna(latest['RSI']):
            if latest['RSI'] < 30:
                signals.append("RSI oversold - BUY signal")
                score += 15
            elif latest['RSI'] > 70:
                signals.append("RSI overbought - SELL signal")
                score -= 15
        
        # MACD Signals
        if 'MACD' in df.columns and 'MACD_Signal' in df.columns:
            if not pd.isna(latest['MACD']) and not pd.isna(latest['MACD_Signal']):
                if latest['MACD'] > latest['MACD_Signal']:
                    signals.append("MACD bullish crossover")
                    score += 10
                else:
                    signals.append("MACD bearish crossover")
                    score -= 10
        
        # Moving Average Signals
        if 'SMA_50' in df.columns and 'SMA_200' in df.columns:
            if not pd.isna(latest['SMA_50']) and not pd.isna(latest['SMA_200']):
                if latest['SMA_50'] > latest['SMA_200']:
                    signals.append("Golden Cross - bullish")
                    score += 10
                else:
                    signals.append("Death Cross - bearish")
                    score -= 10
        
        # Price vs SMA_20
        if 'SMA_20' in df.columns and not pd.isna(latest['SMA_20']):
            if latest['close'] > latest['SMA_20']:
                signals.append("Price above 20-day SMA")
                score += 5
            else:
                signals.append("Price below 20-day SMA")
                score -= 5
        
        # Bollinger Bands
        if 'BB_Upper' in df.columns and 'BB_Lower' in df.columns:
            if not pd.isna(latest['BB_Upper']) and not pd.isna(latest['BB_Lower']):
                if latest['close'] < latest['BB_Lower']:
                    signals.append("Price near lower Bollinger Band - potential BUY")
                    score += 10
                elif latest['close'] > latest['BB_Upper']:
                    signals.append("Price near upper Bollinger Band - potential SELL")
                    score -= 10
        
        # Stochastic
        if 'STOCH' in df.columns and not pd.isna(latest['STOCH']):
            if latest['STOCH'] < 20:
                signals.append("Stochastic oversold")
                score += 8
            elif latest['STOCH'] > 80:
                signals.append("Stochastic overbought")
                score -= 8
        
        # Determine overall recommendation
        if score >= 70:
            recommendation = "STRONG BUY"
        elif score >= 55:
            recommendation = "BUY"
        elif score >= 45:
            recommendation = "HOLD"
        elif score >= 30:
            recommendation = "SELL"
        else:
            recommendation = "STRONG SELL"
        
        return {
            'recommendation': recommendation,
            'score': score,
            'signals': signals,
            'latest_price': latest['close'],
            'rsi': latest.get('RSI', None),
            'macd': latest.get('MACD', None),
            'sma_20': latest.get('SMA_20', None),
            'sma_50': latest.get('SMA_50', None),
            'sma_200': latest.get('SMA_200', None)
        }
    
    def analyze_stock(self, symbol):
        """Complete analysis of a stock"""
        df = self.calculate_all_indicators(symbol)
        
        if df is None:
            return None
        
        signals = self.get_trading_signals(df)
        
        return {
            'symbol': symbol.upper(),
            'data': df,
            'analysis': signals
        }
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

    def calculate_zscore(self, df, period=50):
        """Calculate Mean Reversion Z-Score: how many std devs price is from its mean."""
        mean = df['close'].rolling(window=period).mean()
        std = df['close'].rolling(window=period).std()
        df['ZScore'] = (df['close'] - mean) / std
        return df

    def calculate_linear_regression(self, df, period=50):
        """Calculate Linear Regression slope and R² for trend quality."""
        slopes = []
        r_squared = []
        for i in range(len(df)):
            if i < period - 1:
                slopes.append(np.nan)
                r_squared.append(np.nan)
                continue
            y = df['close'].iloc[i - period + 1:i + 1].values
            x = np.arange(period)
            if np.std(y) == 0:
                slopes.append(0.0)
                r_squared.append(0.0)
                continue
            coeffs = np.polyfit(x, y, 1)
            slope = coeffs[0]
            y_pred = np.polyval(coeffs, x)
            ss_res = np.sum((y - y_pred) ** 2)
            ss_tot = np.sum((y - np.mean(y)) ** 2)
            r2 = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0
            slopes.append(slope)
            r_squared.append(r2)
        df['LinReg_Slope'] = slopes
        df['LinReg_R2'] = r_squared
        return df

    def calculate_hurst_exponent(self, df, max_lag=20):
        """Calculate Hurst Exponent to determine trending vs mean-reverting behavior.
        H > 0.5 = trending, H < 0.5 = mean-reverting, H ≈ 0.5 = random walk."""
        hurst_vals = []
        for i in range(len(df)):
            if i < max_lag * 4:
                hurst_vals.append(np.nan)
                continue
            series = df['close'].iloc[max(0, i - max_lag * 4):i + 1].values
            if len(series) < max_lag * 2:
                hurst_vals.append(np.nan)
                continue
            try:
                lags = range(2, min(max_lag + 1, len(series) // 2))
                tau = []
                lag_list = []
                for lag in lags:
                    diffs = series[lag:] - series[:-lag]
                    std = np.std(diffs)
                    if std > 0:
                        tau.append(std)
                        lag_list.append(lag)
                if len(tau) >= 4:
                    log_lags = np.log(lag_list)
                    log_tau = np.log(tau)
                    coeffs = np.polyfit(log_lags, log_tau, 1)
                    hurst_vals.append(coeffs[0])
                else:
                    hurst_vals.append(np.nan)
            except Exception:
                hurst_vals.append(np.nan)
        df['Hurst'] = hurst_vals
        return df

    def calculate_vwap(self, df):
        """Calculate Volume Weighted Average Price (rolling daily reset approximation)."""
        typical_price = (df['high'] + df['low'] + df['close']) / 3
        cum_tp_vol = (typical_price * df['volume']).cumsum()
        cum_vol = df['volume'].cumsum()
        df['VWAP'] = cum_tp_vol / cum_vol
        # Also compute a rolling 20-day VWAP for swing trading context
        tp_vol = typical_price * df['volume']
        df['VWAP_20'] = tp_vol.rolling(window=20).sum() / df['volume'].rolling(window=20).sum()
        return df

    # Map yfinance sector strings to the corresponding sector SPDR ETF.
    # Used for sector-relative strength — a stock can outperform SPY while
    # underperforming its own sector, which is a sell, not a buy.
    SECTOR_ETF_MAP = {
        'Technology': 'XLK',
        'Healthcare': 'XLV',
        'Health Care': 'XLV',
        'Financial Services': 'XLF',
        'Financial': 'XLF',
        'Consumer Cyclical': 'XLY',
        'Consumer Defensive': 'XLP',
        'Communication Services': 'XLC',
        'Energy': 'XLE',
        'Industrials': 'XLI',
        'Basic Materials': 'XLB',
        'Materials': 'XLB',
        'Real Estate': 'XLRE',
        'Utilities': 'XLU',
    }

    def _rs_against_benchmark(self, df, benchmark_symbol, prefix):
        """Compute relative strength vs an arbitrary benchmark ticker. Mutates df in place."""
        col_20 = f'{prefix}_20'
        col_50 = f'{prefix}_50'
        try:
            bench_df = self.db.get_stock_prices(benchmark_symbol)
            if bench_df is None or bench_df.empty:
                # Try yfinance directly so a brand-new ETF lookup doesn't silently fail
                import yfinance as yf
                hist = yf.Ticker(benchmark_symbol).history(period='1y', auto_adjust=True)
                if hist is None or hist.empty:
                    df[col_20] = np.nan
                    df[col_50] = np.nan
                    return df
                bench_df = hist[['Close']].rename(columns={'Close': 'close'}).reset_index()
                bench_df['date'] = bench_df['Date'] if 'Date' in bench_df.columns else bench_df.index
            bench_df = bench_df.sort_values('date').set_index('date')
            # Normalize index timezone for alignment
            try:
                bench_df.index = bench_df.index.tz_localize(None)
            except Exception:
                pass
            common = df.index.intersection(bench_df.index)
            if len(common) < 20:
                df[col_20] = np.nan
                df[col_50] = np.nan
                return df
            stock_close = df.loc[common, 'close']
            bench_close = bench_df.loc[common, 'close']
            stock_ret_20 = stock_close.pct_change(20)
            bench_ret_20 = bench_close.pct_change(20)
            df[col_20] = np.nan
            df.loc[common, col_20] = (stock_ret_20 - bench_ret_20) * 100
            stock_ret_50 = stock_close.pct_change(50)
            bench_ret_50 = bench_close.pct_change(50)
            df[col_50] = np.nan
            df.loc[common, col_50] = (stock_ret_50 - bench_ret_50) * 100
        except Exception:
            df[col_20] = np.nan
            df[col_50] = np.nan
        return df

    def calculate_relative_strength_spy(self, df, symbol):
        """Calculate Relative Strength vs SPY over 20 and 50 day windows."""
        return self._rs_against_benchmark(df, 'SPY', 'RS_SPY')

    def calculate_relative_strength_sector(self, df, symbol):
        """
        Calculate Relative Strength vs the stock's own sector ETF (XLK/XLF/etc).
        A stock can outperform SPY while underperforming its sector — that's a
        sell, not a buy. Resolves sector via yfinance Ticker.info['sector'].
        Sets RS_SECTOR_20 / RS_SECTOR_50 columns. Stores the ETF in df.attrs.
        """
        try:
            import yfinance as yf
            info = yf.Ticker(symbol).info or {}
            sector = info.get('sector') or info.get('industry')
            etf = self.SECTOR_ETF_MAP.get(sector)
            if not etf:
                df['RS_SECTOR_20'] = np.nan
                df['RS_SECTOR_50'] = np.nan
                df.attrs['sector_etf'] = None
                return df
            df.attrs['sector_etf'] = etf
            return self._rs_against_benchmark(df, etf, 'RS_SECTOR')
        except Exception:
            df['RS_SECTOR_20'] = np.nan
            df['RS_SECTOR_50'] = np.nan
            return df

    def calculate_ichimoku(self, df):
        """Calculate Ichimoku Cloud (Tenkan, Kijun, Senkou A/B, Chikou)."""
        high_9 = df['high'].rolling(window=9).max()
        low_9 = df['low'].rolling(window=9).min()
        df['Ichi_Tenkan'] = (high_9 + low_9) / 2  # Conversion line

        high_26 = df['high'].rolling(window=26).max()
        low_26 = df['low'].rolling(window=26).min()
        df['Ichi_Kijun'] = (high_26 + low_26) / 2  # Base line

        df['Ichi_SenkouA'] = ((df['Ichi_Tenkan'] + df['Ichi_Kijun']) / 2).shift(26)
        high_52 = df['high'].rolling(window=52).max()
        low_52 = df['low'].rolling(window=52).min()
        df['Ichi_SenkouB'] = ((high_52 + low_52) / 2).shift(26)

        df['Ichi_Chikou'] = df['close'].shift(-26)  # Lagging span
        return df

    def calculate_fibonacci_levels(self, df, lookback=60):
        """Calculate Fibonacci retracement levels from recent swing high/low."""
        if len(df) < lookback:
            lookback = len(df)
        recent = df.tail(lookback)
        swing_high = recent['high'].max()
        swing_low = recent['low'].min()
        diff = swing_high - swing_low
        df['Fib_0'] = swing_low
        df['Fib_236'] = swing_low + 0.236 * diff
        df['Fib_382'] = swing_low + 0.382 * diff
        df['Fib_500'] = swing_low + 0.500 * diff
        df['Fib_618'] = swing_low + 0.618 * diff
        df['Fib_786'] = swing_low + 0.786 * diff
        df['Fib_1'] = swing_high
        return df

    def calculate_cmf(self, df, period=20):
        """Calculate Chaikin Money Flow — volume-weighted buying vs selling pressure."""
        high_low = df['high'] - df['low']
        # Avoid division by zero
        high_low = high_low.replace(0, np.nan)
        mf_multiplier = ((df['close'] - df['low']) - (df['high'] - df['close'])) / high_low
        mf_multiplier = mf_multiplier.fillna(0)
        mf_volume = mf_multiplier * df['volume']
        df['CMF'] = mf_volume.rolling(window=period).sum() / df['volume'].rolling(window=period).sum()
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

        print("   📊 Calculating Z-Score...")
        df = self.calculate_zscore(df)

        print("   📊 Calculating Linear Regression...")
        df = self.calculate_linear_regression(df)

        print("   📊 Calculating Hurst Exponent...")
        df = self.calculate_hurst_exponent(df)

        print("   📊 Calculating VWAP...")
        df = self.calculate_vwap(df)

        print("   📊 Calculating Relative Strength vs SPY...")
        df = self.calculate_relative_strength_spy(df, symbol)

        print("   📊 Calculating Relative Strength vs sector ETF...")
        df = self.calculate_relative_strength_sector(df, symbol)

        print("   📊 Calculating Ichimoku Cloud...")
        df = self.calculate_ichimoku(df)

        print("   📊 Calculating Fibonacci Levels...")
        df = self.calculate_fibonacci_levels(df)

        print("   📊 Calculating Chaikin Money Flow...")
        df = self.calculate_cmf(df)

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
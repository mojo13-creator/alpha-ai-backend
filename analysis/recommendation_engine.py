# analysis/recommendation_engine.py
"""
Enhanced Recommendation Engine - More sophisticated scoring
Uses weighted indicators, trend strength, and momentum analysis
"""

import pandas as pd
from datetime import datetime

class RecommendationEngine:
    """Generate smart BUY/SELL/HOLD recommendations with detailed scoring"""
    
    def __init__(self, db_manager, analyzer):
        self.db = db_manager
        self.analyzer = analyzer
        print("🤖 Recommendation Engine initialized")
    
    def analyze_and_recommend(self, symbol):
        """
        Analyze a stock and generate recommendation with enhanced scoring
        Returns: dict with recommendation, score, reasoning, and detailed analysis
        """
        print(f"🔍 Analyzing {symbol}...")
        
        # Get technical indicators
        df = self.analyzer.calculate_all_indicators(symbol)
        
        if df is None or df.empty:
            print(f"❌ No data for {symbol}")
            return None
        
        # Get trading signals
        signals = self.analyzer.get_trading_signals(df)
        
        if signals is None:
            print(f"❌ Could not generate signals for {symbol}")
            return None
        
        # ENHANCED SCORING SYSTEM
        score = 50  # Start neutral
        reasons = []
        
        # Get latest values
        latest = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else latest
        
        rsi = latest.get('RSI', 50)
        macd = latest.get('MACD', 0)
        macd_signal = latest.get('MACD_Signal', 0)
        price = latest['close']
        sma_20 = latest.get('SMA_20', price)
        sma_50 = latest.get('SMA_50', price)
        sma_200 = latest.get('SMA_200', price)
        bb_upper = latest.get('BB_Upper', price * 1.02)
        bb_lower = latest.get('BB_Lower', price * 0.98)
        stoch = latest.get('Stochastic', 50)
        adx = latest.get('ADX', 25)
        volume = latest['volume']
        avg_volume = df['volume'].tail(20).mean()
        
        # === 1. RSI ANALYSIS (Enhanced) ===
        if rsi < 25:
            score += 20
            reasons.append(f"🟢 RSI extremely oversold ({rsi:.1f}) - strong buy signal")
        elif rsi < 35:
            score += 12
            reasons.append(f"🟢 RSI oversold ({rsi:.1f}) - buy opportunity")
        elif rsi < 45:
            score += 5
            reasons.append(f"RSI slightly bearish ({rsi:.1f})")
        elif rsi > 75:
            score -= 20
            reasons.append(f"🔴 RSI extremely overbought ({rsi:.1f}) - strong sell signal")
        elif rsi > 65:
            score -= 12
            reasons.append(f"🔴 RSI overbought ({rsi:.1f}) - sell warning")
        elif rsi > 55:
            score -= 5
            reasons.append(f"RSI slightly bullish ({rsi:.1f})")
        
        # === 2. MACD ANALYSIS (Enhanced with strength) ===
        macd_diff = macd - macd_signal
        macd_strength = abs(macd_diff)
        
        if macd > macd_signal:
            if macd_strength > 1:
                score += 15
                reasons.append(f"🟢 Strong MACD bullish signal (strength: {macd_strength:.2f})")
            else:
                score += 8
                reasons.append(f"🟢 MACD bullish crossover")
        else:
            if macd_strength > 1:
                score -= 15
                reasons.append(f"🔴 Strong MACD bearish signal (strength: {macd_strength:.2f})")
            else:
                score -= 8
                reasons.append(f"🔴 MACD bearish crossover")
        
        # === 3. MOVING AVERAGE ANALYSIS (Enhanced) ===
        # Short-term trend (20-day)
        if price > sma_20:
            distance = ((price - sma_20) / sma_20) * 100
            if distance > 5:
                score += 8
                reasons.append(f"🟢 Price {distance:.1f}% above 20-MA - strong uptrend")
            else:
                score += 4
                reasons.append(f"Price above 20-MA")
        else:
            distance = ((sma_20 - price) / sma_20) * 100
            if distance > 5:
                score -= 8
                reasons.append(f"🔴 Price {distance:.1f}% below 20-MA - strong downtrend")
            else:
                score -= 4
                reasons.append(f"Price below 20-MA")
        
        # Golden/Death Cross
        if sma_50 > sma_200:
            cross_strength = ((sma_50 - sma_200) / sma_200) * 100
            if cross_strength > 5:
                score += 12
                reasons.append(f"🟢 Strong Golden Cross ({cross_strength:.1f}% separation)")
            else:
                score += 6
                reasons.append(f"🟢 Golden Cross - bullish")
        else:
            cross_strength = ((sma_200 - sma_50) / sma_200) * 100
            if cross_strength > 5:
                score -= 12
                reasons.append(f"🔴 Strong Death Cross ({cross_strength:.1f}% separation)")
            else:
                score -= 6
                reasons.append(f"🔴 Death Cross - bearish")
        
        # === 4. BOLLINGER BANDS (Enhanced) ===
        bb_position = (price - bb_lower) / (bb_upper - bb_lower)
        
        if bb_position < 0.1:
            score += 15
            reasons.append(f"🟢 Price at lower Bollinger Band - oversold")
        elif bb_position < 0.3:
            score += 8
            reasons.append(f"🟢 Price near lower Bollinger Band")
        elif bb_position > 0.9:
            score -= 15
            reasons.append(f"🔴 Price at upper Bollinger Band - overbought")
        elif bb_position > 0.7:
            score -= 8
            reasons.append(f"🔴 Price near upper Bollinger Band")
        
        # === 5. STOCHASTIC (Enhanced) ===
        if stoch < 15:
            score += 12
            reasons.append(f"🟢 Stochastic extremely oversold ({stoch:.1f})")
        elif stoch < 25:
            score += 7
            reasons.append(f"🟢 Stochastic oversold ({stoch:.1f})")
        elif stoch > 85:
            score -= 12
            reasons.append(f"🔴 Stochastic extremely overbought ({stoch:.1f})")
        elif stoch > 75:
            score -= 7
            reasons.append(f"🔴 Stochastic overbought ({stoch:.1f})")
        
        # === 6. TREND STRENGTH (ADX) ===
        if adx > 40:
            # Strong trend - amplify other signals
            if score > 50:
                score += 8
                reasons.append(f"🟢 Very strong trend (ADX: {adx:.1f}) - confirms buy")
            elif score < 50:
                score -= 8
                reasons.append(f"🔴 Very strong trend (ADX: {adx:.1f}) - confirms sell")
        elif adx > 25:
            if score > 50:
                score += 3
                reasons.append(f"Moderate trend strength (ADX: {adx:.1f})")
        elif adx < 20:
            # Weak trend - reduce conviction
            if abs(score - 50) > 20:
                score = 50 + (score - 50) * 0.7  # Reduce score toward neutral
                reasons.append(f"⚠️ Weak trend (ADX: {adx:.1f}) - sideways market")
        
        # === 7. VOLUME ANALYSIS ===
        volume_ratio = volume / avg_volume if avg_volume > 0 else 1
        
        if volume_ratio > 2.5:
            if score > 50:
                score += 10
                reasons.append(f"🟢 Massive volume spike ({volume_ratio:.1f}x avg) - strong conviction")
            else:
                score -= 10
                reasons.append(f"🔴 Massive volume spike ({volume_ratio:.1f}x avg) - selling pressure")
        elif volume_ratio > 1.5:
            if score > 50:
                score += 5
                reasons.append(f"🟢 High volume ({volume_ratio:.1f}x avg)")
            else:
                score -= 5
                reasons.append(f"🔴 High volume ({volume_ratio:.1f}x avg)")
        elif volume_ratio < 0.5:
            score -= 3
            reasons.append(f"⚠️ Low volume - weak signal")
        
        # === 8. MOMENTUM ANALYSIS ===
        if len(df) >= 5:
            price_change_5d = ((price - df.iloc[-5]['close']) / df.iloc[-5]['close']) * 100
            
            if abs(price_change_5d) > 10:
                if price_change_5d > 0:
                    score += 6
                    reasons.append(f"🟢 Strong 5-day momentum (+{price_change_5d:.1f}%)")
                else:
                    score -= 6
                    reasons.append(f"🔴 Strong 5-day decline ({price_change_5d:.1f}%)")
        
        # === FINAL ADJUSTMENTS ===
        # Clamp score between 0 and 100
        score = max(0, min(100, score))
        score = round(score)
        
        # Determine recommendation based on score
        if score >= 75:
            recommendation = "STRONG BUY"
        elif score >= 60:
            recommendation = "BUY"
        elif score >= 45:
            recommendation = "HOLD"
        elif score >= 30:
            recommendation = "SELL"
        else:
            recommendation = "STRONG SELL"
        
        # Build reasoning text
        reasoning = f"Score: {score}/100\n"
        reasoning += f"Current Price: ${price:.2f}\n"
        reasoning += f"RSI: {rsi:.1f} | MACD: {macd:.2f} | ADX: {adx:.1f}\n"
        reasoning += f"Volume: {volume_ratio:.1f}x average\n\n"
        reasoning += "Key Signals:\n"
        for reason in reasons:
            reasoning += f"  • {reason}\n"
        
        result = {
            'symbol': symbol,
            'recommendation': recommendation,
            'score': score,
            'price': price,
            'reasoning': reasoning,
            'timestamp': datetime.now()
        }
        
        # Save to database
        self.db.save_recommendation(
            symbol=symbol,
            recommendation=recommendation,
            score=score,
            reasoning=reasoning,
            price=price
        )
        
        print(f"✅ Saved {recommendation} recommendation for {symbol}")
        print(f"✅ Recommendation: {recommendation}")
        print(f"   Score: {score}/100")
        
        return result
    
    def analyze_watchlist(self):
        """Analyze all stocks in watchlist"""
        watchlist = self.db.get_watchlist()
        
        if watchlist.empty:
            print("⚠️ Watchlist is empty")
            return []
        
        results = []
        
        for _, row in watchlist.iterrows():
            result = self.analyze_and_recommend(row['symbol'])
            if result:
                results.append(result)
        
        return results
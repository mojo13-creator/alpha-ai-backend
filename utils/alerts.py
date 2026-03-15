# utils/alerts.py
"""
Alerts System - Monitor stocks and send notifications
"""

import pandas as pd
from datetime import datetime

class AlertsManager:
    """Manage price alerts and notifications"""
    
    def __init__(self, db_manager, analyzer):
        self.db = db_manager
        self.analyzer = analyzer
        self.alerts = []
        print("🔔 Alerts Manager initialized")
    
    def add_price_alert(self, symbol, target_price, alert_type='above'):
        """
        Add a price alert
        alert_type: 'above' or 'below'
        """
        alert = {
            'symbol': symbol,
            'target_price': target_price,
            'alert_type': alert_type,
            'created': datetime.now(),
            'triggered': False
        }
        self.alerts.append(alert)
        print(f"🔔 Alert added: {symbol} {alert_type} ${target_price:.2f}")
    
    def check_price_alerts(self):
        """Check all price alerts"""
        triggered_alerts = []
        
        for alert in self.alerts:
            if alert['triggered']:
                continue
            
            current = self.db.get_latest_price(alert['symbol'])
            
            if current:
                price = current['price']
                
                if alert['alert_type'] == 'above' and price >= alert['target_price']:
                    alert['triggered'] = True
                    alert['triggered_at'] = datetime.now()
                    alert['triggered_price'] = price
                    triggered_alerts.append(alert)
                    print(f"🔔 ALERT! {alert['symbol']} reached ${price:.2f} (target: ${alert['target_price']:.2f})")
                
                elif alert['alert_type'] == 'below' and price <= alert['target_price']:
                    alert['triggered'] = True
                    alert['triggered_at'] = datetime.now()
                    alert['triggered_price'] = price
                    triggered_alerts.append(alert)
                    print(f"🔔 ALERT! {alert['symbol']} dropped to ${price:.2f} (target: ${alert['target_price']:.2f})")
        
        return triggered_alerts
    
    def check_rsi_alerts(self, oversold_threshold=30, overbought_threshold=70):
        """Check for oversold/overbought conditions"""
        all_symbols = self.db.get_all_symbols()
        alerts = []
        
        for symbol in all_symbols:
            df = self.analyzer.calculate_all_indicators(symbol)
            
            if df is not None and not df.empty and 'RSI' in df.columns:
                latest_rsi = df.iloc[-1]['RSI']
                price = df.iloc[-1]['close']
                
                if pd.notna(latest_rsi):
                    if latest_rsi < oversold_threshold:
                        alerts.append({
                            'type': 'RSI_OVERSOLD',
                            'symbol': symbol,
                            'rsi': latest_rsi,
                            'price': price,
                            'message': f'{symbol} is oversold (RSI: {latest_rsi:.1f}) - Potential BUY'
                        })
                    
                    elif latest_rsi > overbought_threshold:
                        alerts.append({
                            'type': 'RSI_OVERBOUGHT',
                            'symbol': symbol,
                            'rsi': latest_rsi,
                            'price': price,
                            'message': f'{symbol} is overbought (RSI: {latest_rsi:.1f}) - Potential SELL'
                        })
        
        return alerts
    
    def check_all_alerts(self):
        """Run all alert checks"""
        print("\n🔔 Checking all alerts...")
        
        results = {
            'price_alerts': self.check_price_alerts(),
            'rsi_alerts': self.check_rsi_alerts()
        }
        
        total = len(results['price_alerts']) + len(results['rsi_alerts'])
        print(f"✅ {total} alerts triggered")
        
        return results
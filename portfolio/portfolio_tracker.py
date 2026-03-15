# portfolio/portfolio_tracker.py
"""
Portfolio Tracker - Track real holdings and performance
"""

import pandas as pd
from datetime import datetime
import sqlite3

class PortfolioTracker:
    """Track portfolio holdings and performance"""
    
    def __init__(self, db_manager):
        self.db = db_manager
        print("💼 Portfolio Tracker initialized")
        self._init_portfolio_tables()
    
    def _init_portfolio_tables(self):
        """Initialize portfolio-specific tables"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        # Transactions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                transaction_type TEXT NOT NULL,
                shares REAL NOT NULL,
                price REAL NOT NULL,
                total_value REAL NOT NULL,
                commission REAL DEFAULT 0,
                transaction_date DATE NOT NULL,
                notes TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Current holdings table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS current_holdings (
                symbol TEXT PRIMARY KEY,
                shares REAL NOT NULL,
                avg_cost REAL NOT NULL,
                total_cost REAL NOT NULL,
                last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
        print("✅ Portfolio tables initialized")
    
    def add_transaction(self, symbol, transaction_type, shares, price, commission=0, notes=""):
        """
        Add a buy/sell transaction
        transaction_type: 'BUY' or 'SELL'
        """
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        total_value = (shares * price) + commission
        
        cursor.execute('''
            INSERT INTO transactions 
            (symbol, transaction_type, shares, price, total_value, commission, transaction_date, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            symbol.upper(),
            transaction_type.upper(),
            shares,
            price,
            total_value,
            commission,
            datetime.now().date(),
            notes
        ))
        
        conn.commit()
        conn.close()
        
        # Update holdings
        self._update_holdings()
        
        print(f"✅ {transaction_type} transaction recorded: {shares} shares of {symbol} @ ${price:.2f}")
    
    def _update_holdings(self):
        """Recalculate current holdings from transactions"""
        conn = self.db.get_connection()
        
        # Get all transactions
        transactions = pd.read_sql_query(
            "SELECT * FROM transactions ORDER BY transaction_date",
            conn
        )
        
        if transactions.empty:
            conn.close()
            return
        
        # Calculate holdings per symbol
        holdings = {}
        
        for _, txn in transactions.iterrows():
            symbol = txn['symbol']
            
            if symbol not in holdings:
                holdings[symbol] = {'shares': 0, 'total_cost': 0}
            
            if txn['transaction_type'] == 'BUY':
                holdings[symbol]['shares'] += txn['shares']
                holdings[symbol]['total_cost'] += txn['total_value']
            
            elif txn['transaction_type'] == 'SELL':
                holdings[symbol]['shares'] -= txn['shares']
                # Reduce cost proportionally
                if holdings[symbol]['shares'] > 0:
                    cost_per_share = holdings[symbol]['total_cost'] / (holdings[symbol]['shares'] + txn['shares'])
                    holdings[symbol]['total_cost'] -= (txn['shares'] * cost_per_share)
                else:
                    holdings[symbol]['total_cost'] = 0
        
        # Clear and update current_holdings table
        cursor = conn.cursor()
        cursor.execute('DELETE FROM current_holdings')
        
        for symbol, data in holdings.items():
            if data['shares'] > 0:  # Only keep active positions
                avg_cost = data['total_cost'] / data['shares']
                
                cursor.execute('''
                    INSERT INTO current_holdings (symbol, shares, avg_cost, total_cost)
                    VALUES (?, ?, ?, ?)
                ''', (symbol, data['shares'], avg_cost, data['total_cost']))
        
        conn.commit()
        conn.close()
    
    def get_holdings(self):
        """Get current holdings with current prices"""
        conn = self.db.get_connection()
        holdings = pd.read_sql_query("SELECT * FROM current_holdings", conn)
        conn.close()
        
        if holdings.empty:
            return pd.DataFrame()
        
        # Add current prices and P&L
        for idx, row in holdings.iterrows():
            current = self.db.get_latest_price(row['symbol'])
            
            if current:
                current_price = current['price']
                current_value = row['shares'] * current_price
                gain_loss = current_value - row['total_cost']
                gain_loss_pct = (gain_loss / row['total_cost']) * 100
                
                holdings.at[idx, 'current_price'] = current_price
                holdings.at[idx, 'current_value'] = current_value
                holdings.at[idx, 'gain_loss'] = gain_loss
                holdings.at[idx, 'gain_loss_pct'] = gain_loss_pct
            else:
                holdings.at[idx, 'current_price'] = 0
                holdings.at[idx, 'current_value'] = 0
                holdings.at[idx, 'gain_loss'] = 0
                holdings.at[idx, 'gain_loss_pct'] = 0
        
        return holdings
    
    def get_portfolio_value(self):
        """Get total portfolio value"""
        holdings = self.get_holdings()
        
        if holdings.empty:
            return {
                'total_cost': 0,
                'current_value': 0,
                'gain_loss': 0,
                'gain_loss_pct': 0,
                'num_positions': 0
            }
        
        total_cost = holdings['total_cost'].sum()
        current_value = holdings['current_value'].sum() if 'current_value' in holdings.columns else 0
        gain_loss = current_value - total_cost
        gain_loss_pct = (gain_loss / total_cost * 100) if total_cost > 0 else 0
        
        return {
            'total_cost': total_cost,
            'current_value': current_value,
            'gain_loss': gain_loss,
            'gain_loss_pct': gain_loss_pct,
            'num_positions': len(holdings)
        }
    
    def get_transaction_history(self, symbol=None):
        """Get transaction history"""
        conn = self.db.get_connection()
        
        if symbol:
            query = f"SELECT * FROM transactions WHERE symbol = '{symbol.upper()}' ORDER BY transaction_date DESC"
        else:
            query = "SELECT * FROM transactions ORDER BY transaction_date DESC"
        
        history = pd.read_sql_query(query, conn)
        conn.close()
        
        return history
    
    def clear_portfolio(self):
        """Clear all transactions and holdings (use with caution!)"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM transactions')
        cursor.execute('DELETE FROM current_holdings')
        
        conn.commit()
        conn.close()
        
        print("🗑️ Portfolio cleared")
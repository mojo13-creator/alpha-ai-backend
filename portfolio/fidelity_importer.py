# portfolio/fidelity_importer.py
"""
Fidelity Portfolio Importer
Import positions from Fidelity CSV export
"""

import pandas as pd
from datetime import datetime
import re

class FidelityImporter:
    """Import portfolio from Fidelity CSV files"""
    
    def __init__(self, portfolio_tracker):
        self.portfolio = portfolio_tracker
        print("📊 Fidelity Importer initialized")
    
    def parse_fidelity_csv(self, csv_path):
        """Parse Fidelity portfolio CSV"""
        print(f"\n📥 Reading Fidelity CSV: {csv_path}")
        
        try:
            # Read CSV WITHOUT using first column as index
            df = pd.read_csv(csv_path, encoding='utf-8-sig', index_col=False)
            
            print(f"✅ CSV loaded - {len(df)} rows, {len(df.columns)} columns")
            print(f"📋 Column 0: {df.columns[0]}")
            print(f"📋 Column 1: {df.columns[1]}")
            print(f"📋 Column 2: {df.columns[2]}")
            print(f"📋 Column 3: {df.columns[3]}")
            
            # Print what's ACTUALLY in the columns for first stock row
            print("\n🔍 First stock row (row 1):")
            if len(df) > 1:
                for i, col in enumerate(df.columns[:6]):
                    print(f"  Column {i} ({col}): {df.iloc[1][col]}")
            
            positions = []
            
            print("\n🔍 Processing rows:")
            
            for idx, row in df.iterrows():
                try:
                    # The TICKER is in the "Symbol" column (column index 2)
                    ticker_raw = row['Symbol']
                    
                    if pd.isna(ticker_raw) or ticker_raw == '':
                        continue
                    
                    ticker = str(ticker_raw).strip().upper()
                    
                    print(f"\n  Row {idx}: Ticker from Symbol column = '{ticker}'")
                    
                    # Skip cash, crypto, and special positions
                    if any(skip in ticker for skip in ['SPAXX', 'HELD', 'US DOLLARS', 'MONEY', 'USD', 'FCASH', 'CORE']):
                        print(f"    ⏭️  Cash position")
                        continue

                    # Skip tickers with special characters (*, **, etc. = Fidelity cash/special)
                    if '*' in ticker:
                        print(f"    ⏭️  Special position (contains *)")
                        continue

                    # Skip crypto
                    if '/' in ticker:
                        print(f"    ⏭️  Crypto position: {ticker}")
                        continue

                    # Skip junk
                    if len(ticker) > 10:
                        print(f"    ⏭️  Junk row")
                        continue

                    # Clean ticker
                    ticker = re.sub(r'[^A-Z]', '', ticker)
                    
                    # Valid ticker should be 1-5 chars
                    if len(ticker) < 1 or len(ticker) > 5:
                        print(f"    ⏭️  Invalid: {ticker}")
                        continue
                    
                    print(f"    ✓ Valid ticker: {ticker}")
                    
                    # Get quantity from "Quantity" column
                    qty_raw = row['Quantity']
                    print(f"    Quantity column: {qty_raw}")
                    
                    if pd.isna(qty_raw) or qty_raw == '':
                        print(f"    ⏭️  No quantity")
                        continue
                    
                    # Quantity might be a number or empty
                    try:
                        quantity = float(str(qty_raw).replace(',', ''))
                    except:
                        print(f"    ⏭️  Can't parse quantity")
                        continue
                    
                    if quantity <= 0:
                        print(f"    ⏭️  Zero quantity")
                        continue
                    
                    print(f"    ✓ Quantity: {quantity}")
                    
                    # Get cost from "Cost Basis Total" column
                    cost_raw = row['Cost Basis Total']
                    print(f"    Cost Basis Total column: {cost_raw}")
                    
                    if pd.isna(cost_raw) or cost_raw == '':
                        print(f"    ⏭️  No cost")
                        continue
                    
                    # Clean cost
                    cost_str = str(cost_raw).replace('$', '').replace(',', '').replace('+', '').strip()
                    if '/' in cost_str:
                        cost_str = cost_str.split('/')[0].strip()
                    
                    try:
                        total_cost = float(cost_str)
                    except:
                        print(f"    ⏭️  Can't parse cost")
                        continue
                    
                    if total_cost <= 0:
                        print(f"    ⏭️  Zero cost")
                        continue
                    
                    avg_cost = total_cost / quantity
                    
                    print(f"    ✓ Cost: ${total_cost:.2f} (avg: ${avg_cost:.2f})")
                    
                    positions.append({
                        'symbol': ticker,
                        'quantity': quantity,
                        'avg_cost': avg_cost,
                        'total_cost': total_cost
                    })
                    
                    print(f"    ✅ ADDED!")
                
                except Exception as e:
                    print(f"    ⚠️  Error: {e}")
                    import traceback
                    traceback.print_exc()
                    continue
            
            if not positions:
                print("\n❌ No positions found")
                return pd.DataFrame()
            
            result_df = pd.DataFrame(positions)
            print(f"\n🎉 SUCCESS! Parsed {len(result_df)} positions:")
            print(result_df.to_string())
            
            return result_df
            
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def import_to_portfolio(self, csv_path, clear_existing=False):
        """Import Fidelity positions to portfolio"""
        print("\n" + "="*60)
        print("📊 IMPORTING FIDELITY PORTFOLIO")
        print("="*60)
        
        positions = self.parse_fidelity_csv(csv_path)
        
        if positions is None or positions.empty:
            print("❌ No positions to import")
            return False
        
        imported_count = 0
        
        for _, pos in positions.iterrows():
            try:
                self.portfolio.add_transaction(
                    symbol=pos['symbol'],
                    transaction_type='BUY',
                    shares=pos['quantity'],
                    price=pos['avg_cost'],
                    commission=0,
                    notes=f"Imported from Fidelity - {datetime.now().strftime('%Y-%m-%d')}"
                )
                
                imported_count += 1
                print(f"✅ Imported {pos['symbol']}: {pos['quantity']:.4f} shares @ ${pos['avg_cost']:.2f}")
                
            except Exception as e:
                print(f"❌ Error importing {pos['symbol']}: {e}")
        
        print("\n" + "="*60)
        print(f"✅ IMPORT COMPLETE: {imported_count}/{len(positions)} positions imported")
        print("="*60)
        
        return True
    
    def compare_with_current(self, csv_path):
        """Compare Fidelity CSV with current portfolio"""
        fidelity_positions = self.parse_fidelity_csv(csv_path)
        current_holdings = self.portfolio.get_holdings()
        
        if fidelity_positions is None or fidelity_positions.empty:
            return pd.DataFrame()
        
        comparison = []
        
        for _, fid_pos in fidelity_positions.iterrows():
            symbol = fid_pos['symbol']
            current = current_holdings[current_holdings['symbol'] == symbol]
            
            if current.empty:
                comparison.append({
                    'symbol': symbol,
                    'fidelity_shares': fid_pos['quantity'],
                    'tracked_shares': 0,
                    'status': '❌ NOT TRACKED'
                })
            else:
                tracked_shares = current.iloc[0]['shares']
                diff = fid_pos['quantity'] - tracked_shares
                status = '✅ MATCH' if abs(diff) < 0.01 else f'⚠️ DIFF: {diff:+.4f}'
                
                comparison.append({
                    'symbol': symbol,
                    'fidelity_shares': fid_pos['quantity'],
                    'tracked_shares': tracked_shares,
                    'status': status
                })
        
        return pd.DataFrame(comparison)
    
    def sync_with_fidelity(self, csv_path):
        """Smart sync with Fidelity"""
        fidelity_positions = self.parse_fidelity_csv(csv_path)
        
        if fidelity_positions is None or fidelity_positions.empty:
            return False
        
        current_holdings = self.portfolio.get_holdings()
        synced_count = 0
        
        for _, fid_pos in fidelity_positions.iterrows():
            symbol = fid_pos['symbol']
            fid_shares = fid_pos['quantity']
            fid_cost = fid_pos['avg_cost']
            
            current = current_holdings[current_holdings['symbol'] == symbol]
            
            if current.empty:
                self.portfolio.add_transaction(
                    symbol=symbol,
                    transaction_type='BUY',
                    shares=fid_shares,
                    price=fid_cost,
                    commission=0,
                    notes="Synced from Fidelity"
                )
                synced_count += 1
            else:
                tracked_shares = current.iloc[0]['shares']
                diff = fid_shares - tracked_shares
                
                if abs(diff) > 0.01:
                    if diff > 0:
                        self.portfolio.add_transaction(
                            symbol=symbol,
                            transaction_type='BUY',
                            shares=diff,
                            price=fid_cost,
                            commission=0,
                            notes="Sync"
                        )
                    else:
                        self.portfolio.add_transaction(
                            symbol=symbol,
                            transaction_type='SELL',
                            shares=abs(diff),
                            price=fid_cost,
                            commission=0,
                            notes="Sync"
                        )
                    synced_count += 1
        
        print(f"✅ Synced {synced_count} positions")
        return True
# utils/visualizations.py
"""
Advanced Visualizations - Heatmaps, correlations, etc.
"""

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import numpy as np


class AdvancedVisualizations:
    """Create advanced charts and visualizations"""
    
    def __init__(self, db_manager):
        self.db = db_manager
        print("📊 Advanced Visualizations initialized")
    
    def create_correlation_heatmap(self, symbols, days=90):
        """Create correlation heatmap between stocks"""
        print(f"📊 Creating correlation heatmap for {len(symbols)} stocks...")
        
        # Get price data for all symbols
        price_data = {}
        
        for symbol in symbols:
            df = self.db.get_stock_prices(symbol, limit=days)
            if not df.empty:
                df = df.sort_values('date')
                price_data[symbol] = df.set_index('date')['close']
        
        if not price_data:
            return None
        
        # Create DataFrame with all prices
        prices_df = pd.DataFrame(price_data)
        
        # Calculate correlation
        correlation = prices_df.corr()
        
        # Create heatmap
        fig = go.Figure(data=go.Heatmap(
            z=correlation.values,
            x=correlation.columns,
            y=correlation.columns,
            colorscale='RdBu',
            zmid=0,
            text=correlation.values,
            texttemplate='%{text:.2f}',
            textfont={"size": 10},
            colorbar=dict(title="Correlation")
        ))
        
        fig.update_layout(
            title="Stock Price Correlation Heatmap",
            xaxis_title="Symbol",
            yaxis_title="Symbol",
            height=600
        )
        
        return fig
    
    def create_portfolio_pie_chart(self, holdings):
        """Create pie chart of portfolio allocation"""
        if holdings.empty or 'current_value' not in holdings.columns:
            return None
        
        fig = go.Figure(data=[go.Pie(
            labels=holdings['symbol'],
            values=holdings['current_value'],
            hole=0.3,
            textinfo='label+percent',
            textposition='auto'
        )])
        
        fig.update_layout(
            title="Portfolio Allocation",
            height=500
        )
        
        return fig
    
    def create_risk_reward_scatter(self, symbols, days=90):
        """Create risk vs reward scatter plot"""
        print(f"📊 Creating risk/reward analysis for {len(symbols)} stocks...")
        
        data = []
        
        for symbol in symbols:
            df = self.db.get_stock_prices(symbol, limit=days)
            
            if not df.empty and len(df) >= 30:
                df = df.sort_values('date')
                
                # Calculate returns
                returns = df['close'].pct_change().dropna()
                
                # Risk = standard deviation of returns
                risk = returns.std() * np.sqrt(252)  # Annualized
                
                # Reward = average return
                reward = returns.mean() * 252  # Annualized
                
                # Current price
                current_price = df['close'].iloc[-1]
                
                data.append({
                    'symbol': symbol,
                    'risk': risk * 100,  # Convert to percentage
                    'reward': reward * 100,
                    'price': current_price
                })
        
        if not data:
            return None
        
        df_scatter = pd.DataFrame(data)
        
        fig = go.Figure(data=go.Scatter(
            x=df_scatter['risk'],
            y=df_scatter['reward'],
            mode='markers+text',
            text=df_scatter['symbol'],
            textposition='top center',
            marker=dict(
                size=12,
                color=df_scatter['reward'],
                colorscale='RdYlGn',
                showscale=True,
                colorbar=dict(title="Return %")
            ),
            hovertemplate='<b>%{text}</b><br>Risk: %{x:.1f}%<br>Return: %{y:.1f}%<extra></extra>'
        ))
        
        fig.update_layout(
            title="Risk vs Reward Analysis",
            xaxis_title="Risk (Volatility %)",
            yaxis_title="Expected Annual Return %",
            height=600,
            showlegend=False
        )
        
        # Add quadrant lines
        fig.add_hline(y=0, line_dash="dash", line_color="gray")
        fig.add_vline(x=df_scatter['risk'].median(), line_dash="dash", line_color="gray")
        
        return fig
    
    def create_performance_comparison(self, symbols, days=180):
        """Compare performance of multiple stocks"""
        print(f"📊 Comparing performance of {len(symbols)} stocks...")
        
        fig = go.Figure()
        
        for symbol in symbols:
            df = self.db.get_stock_prices(symbol, limit=days)
            
            if not df.empty:
                df = df.sort_values('date')
                
                # Normalize to percentage change from first day
                first_price = df['close'].iloc[0]
                df['pct_change'] = ((df['close'] - first_price) / first_price) * 100
                
                fig.add_trace(go.Scatter(
                    x=df['date'],
                    y=df['pct_change'],
                    name=symbol,
                    mode='lines'
                ))
        
        fig.update_layout(
            title="Performance Comparison (% Change)",
            xaxis_title="Date",
            yaxis_title="% Change from Start",
            height=600,
            hovermode='x unified'
        )
        
        fig.add_hline(y=0, line_dash="dash", line_color="gray")
        
        return fig
    
    def create_volume_profile(self, symbol, days=90):
        """Create volume profile chart"""
        df = self.db.get_stock_prices(symbol, limit=days)
        
        if df.empty:
            return None
        
        df = df.sort_values('date')
        
        # Create figure with secondary y-axis
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        
        # Add candlestick
        fig.add_trace(go.Candlestick(
            x=df['date'],
            open=df['open'],
            high=df['high'],
            low=df['low'],
            close=df['close'],
            name='Price'
        ), secondary_y=False)
        
        # Add volume
        colors = ['red' if df['close'].iloc[i] < df['open'].iloc[i] else 'green' 
                  for i in range(len(df))]
        
        fig.add_trace(go.Bar(
            x=df['date'],
            y=df['volume'],
            name='Volume',
            marker_color=colors,
            opacity=0.5
        ), secondary_y=True)
        
        fig.update_layout(
            title=f"{symbol} - Price and Volume",
            xaxis_rangeslider_visible=False,
            height=600
        )
        
        fig.update_yaxes(title_text="Price", secondary_y=False)
        fig.update_yaxes(title_text="Volume", secondary_y=True)
        
        return fig
    
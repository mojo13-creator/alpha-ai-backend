# config.py - Configuration file for Stock Analyzer
# API keys are loaded from .env — never hardcode secrets here

import os
from dotenv import load_dotenv

load_dotenv()  # Load .env from project root

# ============= API KEYS =============
# We'll fill these in later when we get API access
REDDIT_CLIENT_ID = "your_reddit_client_id_here"
REDDIT_CLIENT_SECRET = "your_reddit_client_secret_here"
REDDIT_USER_AGENT = "stock-analyzer-mac by u/yourusername"

NEWS_API_KEY = os.environ.get("NEWS_API_KEY", "")

# Optional: Alpha Vantage API Key for backup data source
ALPHA_VANTAGE_KEY = "optional_alphavantage_key"  # Optional backup

# ============= DATABASE SETTINGS =============
DATABASE_PATH = "stock_data.db"

# ============= STOCK LISTS =============
# Tech Giants
TECH_STOCKS = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'NVDA', 'TSLA', 'AMD', 'INTC']

# AI & Emerging Tech
# AI & Tech Stocks
AI_TECH_STOCKS = [
    "AAPL", "MSFT", "GOOGL", "META", "NVDA", "AMD",
    "PLTR", "SNOW", "DDOG", "AI", "SOUN", "BBAI",
    "PATH", "UPST"  # ← ADD MORE HERE
]

# Add a completely new category:
SEMICONDUCTOR_STOCKS = [
    "NVDA", "AMD", "INTC", "TSM", "AVGO", "QCOM",
    "MU", "AMAT", "LRCX", "KLAC", "ASML"
]

# Quantum Computing & Advanced Tech
QUANTUM_TECH = ['IONQ', 'RGTI', 'QBTS', 'ARQQ']  # IonQ, Rigetti, D-Wave Quantum

# Biotech & Gene Editing (Breakthroughs)
BIOTECH_STOCKS = ['CRSP', 'NTLA', 'EDIT', 'BEAM', 'MRNA', 'BNTX', 'NVAX']  # CRISPR, Intellia, Moderna

# Space & Aerospace
SPACE_STOCKS = ['RKLB', 'ASTS', 'PL', 'LUNR']  # Rocket Lab, AST SpaceMobile, Planet Labs

# Clean Energy & EV
CLEAN_ENERGY = ['ENPH', 'SEDG', 'RUN', 'FSLR', 'RIVN', 'LCID', 'NIO', 'XPEV']

# Government Bonds & Treasury ETFs
BONDS = ['TLT', 'IEF', 'SHY', 'AGG', 'BND', 'GOVT']  # Treasury bonds, aggregate bonds

# Gold, Silver, Precious Metals
PRECIOUS_METALS = ['GLD', 'SLV', 'IAU', 'PSLV', 'PHYS', 'GOLD']  # Gold/Silver ETFs
GOLD_MINERS = ['NEM', 'GOLD', 'AEM', 'FNV', 'WPM']  # Mining companies

# Commodities
COMMODITIES = ['USO', 'UNG', 'DBA', 'CORN', 'WEAT']  # Oil, Gas, Agriculture

# Major Market ETFs
MARKET_ETFS = ['SPY', 'QQQ', 'DIA', 'IWM', 'VTI', 'VOO', 'VUG', 'VTV']

# International Markets
INTERNATIONAL = ['EEM', 'VEA', 'VWO', 'FXI', 'EWJ', 'EWZ']  # Emerging markets, China, Japan, Brazil

# Dividend Stocks
DIVIDEND_STOCKS = ['SCHD', 'VYM', 'JEPI', 'O', 'KO', 'PEP', 'JNJ', 'PG']

# Defense & Aerospace
DEFENSE_STOCKS = ['LMT', 'RTX', 'BA', 'NOC', 'GD', 'LHX']  # Lockheed, Raytheon, Boeing

# Crypto-Related (can't trade actual crypto, but companies)
CRYPTO_RELATED = ['COIN', 'MSTR', 'RIOT', 'MARA', 'CLSK']  # Coinbase, MicroStrategy, miners

# REITs (Real Estate)
REITS = ['VNQ', 'O', 'VICI', 'SPG', 'PSA', 'AMT']

# International ETFs
INTERNATIONAL_ETFS = [
    "VXUS",  # Vanguard Total International Stock
    "VEA",   # Vanguard Developed Markets
    "VWO",   # Vanguard Emerging Markets
    "IEMG",  # iShares Core MSCI Emerging Markets
    "EFA",   # iShares MSCI EAFE
    "IXUS",  # iShares Core MSCI Total International
    "IEFA",  # iShares Core MSCI EAFE
    "EEM",   # iShares MSCI Emerging Markets
    "ACWI",  # iShares MSCI ACWI
    "ACWX"   # iShares MSCI ACWI ex U.S.
]

# Default combined watchlist (you can customize)
DEFAULT_WATCHLIST = (
    TECH_STOCKS[:5] +           # Top 5 tech
    AI_TECH_STOCKS[:3] +        # Top 3 AI
    QUANTUM_TECH[:2] +          # Top 2 quantum
    BIOTECH_STOCKS[:2] +        # Top 2 biotech
    SPACE_STOCKS[:2] +          # Top 2 space
    PRECIOUS_METALS[:2] +       # Gold & Silver ETFs
    BONDS[:2] +                 # Treasury bonds
    MARKET_ETFS[:3] +           # SPY, QQQ, DIA
    CLEAN_ENERGY[:2]            # Top 2 clean energy
) 


# ============= REDDIT SETTINGS =============
SUBREDDITS = [
    'wallstreetbets',
    'stocks',
    'investing',
    'stockmarket',
    'options',
    'dividends',
    'ValueInvesting',
    'SecurityAnalysis',
    'StockMarket'
]

# How many top posts to fetch from each subreddit
REDDIT_POST_LIMIT = 25

# ============= NEWS SETTINGS =============
NEWS_SOURCES = [
    'bloomberg',
    'financial-times',
    'the-wall-street-journal',
    'cnbc',
    'reuters',
    'business-insider'
]

# ============= TECHNICAL ANALYSIS SETTINGS =============
TECHNICAL_INDICATORS = [
    'SMA_20',    # 20-day Simple Moving Average
    'SMA_50',    # 50-day Simple Moving Average
    'SMA_200',   # 200-day Simple Moving Average
    'EMA_12',    # 12-day Exponential Moving Average
    'EMA_26',    # 26-day Exponential Moving Average
    'RSI',       # Relative Strength Index (14-period)
    'MACD',      # Moving Average Convergence Divergence
    'BB_UPPER',  # Bollinger Bands Upper
    'BB_LOWER',  # Bollinger Bands Lower
    'BB_MIDDLE', # Bollinger Bands Middle
    'ATR',       # Average True Range
    'STOCH',     # Stochastic Oscillator
    'ADX'        # Average Directional Index
]

# RSI thresholds
RSI_OVERSOLD = 30   # Below this = potentially oversold (buy signal)
RSI_OVERBOUGHT = 70 # Above this = potentially overbought (sell signal)

# ============= RECOMMENDATION SETTINGS =============
# Scoring thresholds (0-100 scale)
STRONG_BUY_THRESHOLD = 85
BUY_THRESHOLD = 70
HOLD_THRESHOLD_UPPER = 60
HOLD_THRESHOLD_LOWER = 40
SELL_THRESHOLD = 30
STRONG_SELL_THRESHOLD = 15

# ============= REPORT SETTINGS =============
# When to generate reports (24-hour format)
DAILY_REPORT_TIME = "18:00"      # 6:00 PM
WEEKLY_REPORT_DAY = 5            # Friday (0=Monday, 6=Sunday)
MONTHLY_REPORT_DAY = 1           # 1st of each month

# How many stocks to include in reports
TOP_STOCKS_IN_REPORT = 10
TOP_MOVERS_COUNT = 5

# ============= PORTFOLIO SETTINGS =============
INITIAL_CAPITAL = 10000          # Starting capital for backtesting
RISK_PER_TRADE = 0.02            # 2% risk per trade
MAX_POSITION_SIZE = 0.20         # Max 20% of portfolio in one stock

# ============= DATA COLLECTION SETTINGS =============
DEFAULT_PERIOD = "1y"            # Default historical data to fetch
UPDATE_FREQUENCY = "1d"          # How often to update data

# ============= DISPLAY SETTINGS =============
CURRENCY_SYMBOL = "$"
DATE_FORMAT = "%Y-%m-%d"
DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"

# ============= FILE PATHS =============
REPORTS_DIR = "reports_archive"
EXPORTS_DIR = "exports"
LOGS_DIR = "logs"

# Create directories if they don't exist
for directory in [REPORTS_DIR, EXPORTS_DIR, LOGS_DIR]:
    os.makedirs(directory, exist_ok=True)

# ============= SENTIMENT ANALYSIS SETTINGS =============
SENTIMENT_POSITIVE_THRESHOLD = 0.1
SENTIMENT_NEGATIVE_THRESHOLD = -0.1

# ============= FEATURE FLAGS =============
ENABLE_REDDIT = True
ENABLE_NEWS = True
ENABLE_TECHNICAL_ANALYSIS = True
ENABLE_SENTIMENT_ANALYSIS = True
ENABLE_BACKTESTING = True

print("✅ Configuration loaded successfully!")

# ============================================
# AI ANALYSIS CONFIGURATION
# ============================================

# Claude API Key (get from https://console.anthropic.com/)
CLAUDE_API_KEY = os.environ.get("CLAUDE_API_KEY", "")
if not CLAUDE_API_KEY:
    raise ValueError("CLAUDE_API_KEY not set — add it to your .env file")

# Enable/Disable AI Analysis
# Set to False to use traditional technical analysis
# Set to True to use Claude AI for advanced analysis
USE_AI_ANALYSIS = True  # Change to True after adding API key above

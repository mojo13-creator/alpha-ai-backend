# ui/dashboard.py
"""
ULTIMATE Stock Analyzer Dashboard - Full Featured
All-in-one stock analysis, screening, backtesting, alerts, and portfolio tracking
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import sys
import os

def create_recommendation_card(symbol, recommendation, score, price, reasoning=""):
    """Create a beautiful recommendation card with animations"""
    
    # Color scheme based on recommendation
    if "STRONG BUY" in recommendation:
        gradient = "linear-gradient(135deg, #48bb78 0%, #38a169 100%)"
        border = "#48bb78"
        glow = "0 0 40px rgba(72, 187, 120, 0.4)"
    elif "BUY" in recommendation:
        gradient = "linear-gradient(135deg, #4299e1 0%, #3182ce 100%)"
        border = "#4299e1"
        glow = "0 0 40px rgba(66, 153, 225, 0.4)"
    elif "SELL" in recommendation:
        gradient = "linear-gradient(135deg, #f56565 0%, #e53e3e 100%)"
        border = "#f56565"
        glow = "0 0 40px rgba(245, 101, 101, 0.4)"
    else:  # HOLD
        gradient = "linear-gradient(135deg, #ed8936 0%, #dd6b20 100%)"
        border = "#ed8936"
        glow = "0 0 40px rgba(237, 137, 54, 0.4)"
    
    card_html = f"""
    <div style='
        background: rgba(255, 255, 255, 0.03);
        backdrop-filter: blur(20px);
        border: 2px solid {border};
        border-radius: 20px;
        padding: 2rem;
        margin: 1.5rem 0;
        box-shadow: {glow}, 0 8px 32px rgba(0, 0, 0, 0.2);
        transition: all 0.3s ease;
        position: relative;
        overflow: hidden;
    '>
        <!-- Gradient overlay -->
        <div style='
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 4px;
            background: {gradient};
        '></div>
        
        <!-- Header -->
        <div style='display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.5rem;'>
            <div>
                <h2 style='
                    margin: 0;
                    font-size: 2rem;
                    font-weight: 800;
                    background: {gradient};
                    -webkit-background-clip: text;
                    -webkit-text-fill-color: transparent;
                '>{symbol}</h2>
                <p style='margin: 0.5rem 0 0 0; color: #a0aec0; font-size: 1.1rem;'>${price:.2f}</p>
            </div>
            <div style='text-align: right;'>
                <div style='
                    background: {gradient};
                    padding: 12px 24px;
                    border-radius: 12px;
                    font-size: 1.2rem;
                    font-weight: 700;
                    color: white;
                    box-shadow: {glow};
                '>{recommendation}</div>
                <p style='margin: 0.5rem 0 0 0; color: #cbd5e0; font-size: 0.9rem;'>Score: {score}/100</p>
            </div>
        </div>
        
        <!-- Score Bar -->
        <div style='
            width: 100%;
            height: 12px;
            background: rgba(255, 255, 255, 0.1);
            border-radius: 10px;
            overflow: hidden;
            margin-bottom: 1rem;
        '>
            <div style='
                width: {score}%;
                height: 100%;
                background: {gradient};
                border-radius: 10px;
                box-shadow: 0 0 20px {border};
                transition: width 1s ease-out;
            '></div>
        </div>
        
        <!-- Reasoning -->
        {f"<p style='color: #e2e8f0; line-height: 1.6; margin: 0;'>{reasoning[:200]}...</p>" if reasoning else ""}
    </div>
    """
    
    return card_html

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db_manager import DatabaseManager
from data_collection.stock_data import StockDataCollector
from data_collection.news_scraper import NewsScraper
from analysis.technical_analysis import TechnicalAnalyzer
from analysis.hybrid_recommender import HybridRecommender
from analysis.stock_screener import StockScreener
from analysis.backtester import Backtester
from reports.report_generator import ReportGenerator
from portfolio.portfolio_tracker import PortfolioTracker
from utils.alerts import AlertsManager
from utils.scheduler import TaskScheduler
from utils.visualizations import AdvancedVisualizations
import config

# Page configuration
st.set_page_config(
    page_title="Stock Analyzer Pro 🚀",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    /* HIDE STREAMLIT BRANDING */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* CUSTOM DARK THEME */
    .stApp {
        background: linear-gradient(135deg, #0a0e1a 0%, #1a1f35 100%);
    }
    
    /* MAIN HEADER - GRADIENT TEXT */
    .main-header {
        font-size: 2.8rem;
        font-weight: 800;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 50%, #f093fb 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-align: center;
        padding: 2rem 1rem 1rem 1rem;
        margin-bottom: 1.5rem;
        letter-spacing: -0.5px;
    }
    
    /* SIDEBAR STYLING */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #1a1f35 0%, #0f1320 100%);
        border-right: 1px solid rgba(102, 126, 234, 0.1);
    }
    
    section[data-testid="stSidebar"] h1 {
        color: #ffffff;
        font-size: 1.3rem;
        font-weight: 700;
    }
    
    section[data-testid="stSidebar"] h3 {
        color: #a0aec0;
        font-size: 0.95rem;
        font-weight: 600;
        margin-top: 1.5rem;
    }
    
    /* SIDEBAR NAVIGATION */
    section[data-testid="stSidebar"] [role="radiogroup"] label {
        background: rgba(102, 126, 234, 0.05) !important;
        border-radius: 8px !important;
        padding: 12px 16px !important;
        margin: 4px 0 !important;
        font-size: 1rem !important;
        font-weight: 500 !important;
        color: #e2e8f0 !important;
        transition: all 0.2s ease !important;
        border-left: 3px solid transparent !important;
    }
    
    section[data-testid="stSidebar"] [role="radiogroup"] label:hover {
        background: rgba(102, 126, 234, 0.15) !important;
        border-left: 3px solid #667eea !important;
        transform: translateX(4px);
    }
    
    section[data-testid="stSidebar"] [role="radiogroup"] label[data-checked="true"] {
        background: linear-gradient(135deg, rgba(102, 126, 234, 0.25) 0%, rgba(118, 75, 162, 0.25) 100%) !important;
        border-left: 3px solid #667eea !important;
        font-weight: 600 !important;
    }
    
    /* METRIC CARDS - GLASSMORPHISM */
    [data-testid="stMetric"] {
        background: rgba(255, 255, 255, 0.03) !important;
        backdrop-filter: blur(10px) !important;
        border: 1px solid rgba(255, 255, 255, 0.08) !important;
        border-radius: 16px !important;
        padding: 24px !important;
        box-shadow: 0 8px 32px 0 rgba(31, 38, 135, 0.15) !important;
        transition: all 0.3s ease !important;
    }
    
    [data-testid="stMetric"]:hover {
        transform: translateY(-4px);
        box-shadow: 0 12px 40px 0 rgba(102, 126, 234, 0.2) !important;
        border-color: rgba(102, 126, 234, 0.3) !important;
    }
    
    /* METRIC VALUES */
    [data-testid="stMetricValue"],
    [data-testid="stMetricValue"] > div {
        color: #ffffff !important;
        font-size: 2.2rem !important;
        font-weight: 700 !important;
        letter-spacing: -0.5px !important;
    }
    
    /* METRIC LABELS */
    [data-testid="stMetricLabel"],
    [data-testid="stMetricLabel"] > div {
        color: #a0aec0 !important;
        font-size: 0.9rem !important;
        font-weight: 600 !important;
        text-transform: uppercase !important;
        letter-spacing: 0.5px !important;
    }
    
    /* METRIC DELTA */
    [data-testid="stMetricDelta"] {
        font-size: 0.95rem !important;
        font-weight: 600 !important;
    }
    
    /* SIDEBAR METRICS */
    section[data-testid="stSidebar"] [data-testid="stMetric"] {
        background: rgba(102, 126, 234, 0.1) !important;
        border: 1px solid rgba(102, 126, 234, 0.2) !important;
        padding: 16px !important;
        border-radius: 12px !important;
        margin: 8px 0 !important;
    }
    
    section[data-testid="stSidebar"] [data-testid="stMetricValue"] {
        color: #667eea !important;
        font-size: 1.6rem !important;
    }
    
    section[data-testid="stSidebar"] [data-testid="stMetricLabel"] {
        color: #e2e8f0 !important;
        font-size: 0.85rem !important;
    }
    
    /* BUTTONS - MODERN GRADIENT */
    .stButton > button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
        color: white !important;
        border: none !important;
        border-radius: 10px !important;
        padding: 12px 28px !important;
        font-weight: 600 !important;
        font-size: 1rem !important;
        transition: all 0.3s ease !important;
        box-shadow: 0 4px 15px 0 rgba(102, 126, 234, 0.3) !important;
    }
    
    .stButton > button:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 6px 25px 0 rgba(102, 126, 234, 0.5) !important;
    }
    
    .stButton > button:active {
        transform: translateY(0px) !important;
    }
    
    /* PRIMARY BUTTONS */
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%) !important;
        box-shadow: 0 4px 15px 0 rgba(245, 87, 108, 0.3) !important;
    }
    
    .stButton > button[kind="primary"]:hover {
        box-shadow: 0 6px 25px 0 rgba(245, 87, 108, 0.5) !important;
    }
    
    /* TEXT INPUTS */
    .stTextInput > div > div > input {
        background: rgba(255, 255, 255, 0.05) !important;
        border: 1px solid rgba(255, 255, 255, 0.1) !important;
        border-radius: 10px !important;
        color: #ffffff !important;
        padding: 12px 16px !important;
        font-size: 1rem !important;
    }
    
    .stTextInput > div > div > input:focus {
        border-color: #667eea !important;
        box-shadow: 0 0 0 2px rgba(102, 126, 234, 0.2) !important;
    }
    
    /* SELECT BOXES */
    .stSelectbox > div > div {
        background: rgba(255, 255, 255, 0.05) !important;
        border: 1px solid rgba(255, 255, 255, 0.1) !important;
        border-radius: 10px !important;
        color: #ffffff !important;
    }
    
    /* DATAFRAMES */
    .stDataFrame {
        background: rgba(255, 255, 255, 0.03) !important;
        border-radius: 12px !important;
        overflow: hidden !important;
    }
    
    /* TABLE HEADERS */
    .stDataFrame thead tr th {
        background: linear-gradient(135deg, rgba(102, 126, 234, 0.2) 0%, rgba(118, 75, 162, 0.2) 100%) !important;
        color: #ffffff !important;
        font-weight: 600 !important;
        border: none !important;
        padding: 16px !important;
    }
    
    /* TABLE ROWS */
    .stDataFrame tbody tr {
        background: rgba(255, 255, 255, 0.02) !important;
        border-bottom: 1px solid rgba(255, 255, 255, 0.05) !important;
    }
    
    .stDataFrame tbody tr:hover {
        background: rgba(102, 126, 234, 0.1) !important;
    }
    
    /* EXPANDER */
    .streamlit-expanderHeader {
        background: rgba(255, 255, 255, 0.05) !important;
        border-radius: 10px !important;
        color: #ffffff !important;
        font-weight: 600 !important;
    }
    
    /* TABS */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background: rgba(255, 255, 255, 0.03);
        padding: 8px;
        border-radius: 12px;
    }
    
    .stTabs [data-baseweb="tab"] {
        background: transparent !important;
        border-radius: 8px !important;
        color: #a0aec0 !important;
        font-weight: 600 !important;
        padding: 12px 24px !important;
    }
    
    .stTabs [data-baseweb="tab"]:hover {
        background: rgba(102, 126, 234, 0.1) !important;
        color: #ffffff !important;
    }
    
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, rgba(102, 126, 234, 0.3) 0%, rgba(118, 75, 162, 0.3) 100%) !important;
        color: #ffffff !important;
    }
    
    /* INFO/SUCCESS/WARNING/ERROR BOXES */
    .stAlert {
        border-radius: 12px !important;
        border: none !important;
        backdrop-filter: blur(10px) !important;
    }
    
    /* SPINNER */
    .stSpinner > div {
        border-top-color: #667eea !important;
    }
    
    /* SCROLLBAR */
    ::-webkit-scrollbar {
        width: 10px;
        height: 10px;
    }
    
    ::-webkit-scrollbar-track {
        background: rgba(255, 255, 255, 0.05);
        border-radius: 10px;
    }
    
    ::-webkit-scrollbar-thumb {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border-radius: 10px;
    }
    
    ::-webkit-scrollbar-thumb:hover {
        background: linear-gradient(135deg, #764ba2 0%, #f093fb 100%);
    }
    
    /* DIVIDERS */
    hr {
        border: none;
        height: 1px;
        background: linear-gradient(90deg, transparent 0%, rgba(102, 126, 234, 0.3) 50%, transparent 100%);
        margin: 2rem 0;
    }
    
    /* HEADINGS */
    h1, h2, h3 {
        color: #ffffff !important;
        font-weight: 700 !important;
    }
    
    /* PARAGRAPHS */
    p {
        color: #cbd5e0 !important;
    }
    
    /* CAPTIONS */
    .caption {
        color: #a0aec0 !important;
        font-size: 0.9rem !important;
    }

    /* ===== ANIMATED GRADIENT BACKGROUND ===== */
    @keyframes gradient-shift {
        0% {
            background-position: 0% 50%;
        }
        50% {
            background-position: 100% 50%;
        }
        100% {
            background-position: 0% 50%;
        }
    }
    
    .stApp {
        background: linear-gradient(135deg, #0a0e1a 0%, #1a1f35 50%, #0f1429 100%);
        background-size: 200% 200%;
        animation: gradient-shift 15s ease infinite;
    }
    
    /* ===== FLOATING PARTICLES EFFECT ===== */
    .stApp::before {
        content: '';
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background-image: 
            radial-gradient(2px 2px at 20% 30%, rgba(102, 126, 234, 0.3), transparent),
            radial-gradient(2px 2px at 60% 70%, rgba(118, 75, 162, 0.3), transparent),
            radial-gradient(1px 1px at 50% 50%, rgba(240, 147, 251, 0.2), transparent),
            radial-gradient(1px 1px at 80% 10%, rgba(102, 126, 234, 0.2), transparent);
        background-size: 200% 200%;
        animation: float-particles 20s ease-in-out infinite;
        pointer-events: none;
        z-index: 0;
    }
    
    @keyframes float-particles {
        0%, 100% {
            background-position: 0% 0%, 100% 100%, 50% 50%, 80% 20%;
        }
        50% {
            background-position: 100% 100%, 0% 0%, 30% 70%, 20% 80%;
        }
    }
    
    /* ===== GLOW EFFECTS ON CARDS ===== */
    @keyframes glow-pulse {
        0%, 100% {
            box-shadow: 
                0 0 20px rgba(102, 126, 234, 0.2),
                0 0 40px rgba(102, 126, 234, 0.1),
                inset 0 0 20px rgba(102, 126, 234, 0.05);
        }
        50% {
            box-shadow: 
                0 0 30px rgba(102, 126, 234, 0.4),
                0 0 60px rgba(102, 126, 234, 0.2),
                inset 0 0 30px rgba(102, 126, 234, 0.1);
        }
    }
    
    [data-testid="stMetric"] {
        animation: glow-pulse 4s ease-in-out infinite;
    }
    
    /* ===== CARD REVEAL ANIMATION ===== */
    @keyframes slideInUp {
        from {
            opacity: 0;
            transform: translateY(30px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }
    
    [data-testid="stMetric"] {
        animation: slideInUp 0.6s ease-out, glow-pulse 4s ease-in-out infinite 0.6s;
    }
    
    /* Stagger animation for multiple cards */
    [data-testid="column"]:nth-child(1) [data-testid="stMetric"] {
        animation-delay: 0s, 0.6s;
    }
    [data-testid="column"]:nth-child(2) [data-testid="stMetric"] {
        animation-delay: 0.1s, 0.7s;
    }
    [data-testid="column"]:nth-child(3) [data-testid="stMetric"] {
        animation-delay: 0.2s, 0.8s;
    }
    [data-testid="column"]:nth-child(4) [data-testid="stMetric"] {
        animation-delay: 0.3s, 0.9s;
    }
    [data-testid="column"]:nth-child(5) [data-testid="stMetric"] {
        animation-delay: 0.4s, 1s;
    }
    
    /* ===== NEON BORDER EFFECT ===== */
    .neon-box {
        position: relative;
        background: rgba(255, 255, 255, 0.03);
        border-radius: 16px;
        padding: 24px;
        overflow: hidden;
    }
    
    .neon-box::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        border-radius: 16px;
        padding: 2px;
        background: linear-gradient(135deg, #667eea, #764ba2, #f093fb);
        -webkit-mask: 
            linear-gradient(#fff 0 0) content-box, 
            linear-gradient(#fff 0 0);
        -webkit-mask-composite: xor;
        mask-composite: exclude;
        animation: rotate-border 4s linear infinite;
    }
    
    @keyframes rotate-border {
        0% {
            filter: hue-rotate(0deg);
        }
        100% {
            filter: hue-rotate(360deg);
        }
    }
    
    /* ===== SHIMMER LOADING EFFECT ===== */
    @keyframes shimmer {
        0% {
            background-position: -1000px 0;
        }
        100% {
            background-position: 1000px 0;
        }
    }
    
    .loading-shimmer {
        background: linear-gradient(
            90deg,
            rgba(255, 255, 255, 0.0) 0%,
            rgba(255, 255, 255, 0.1) 50%,
            rgba(255, 255, 255, 0.0) 100%
        );
        background-size: 1000px 100%;
        animation: shimmer 2s infinite;
    }
    
    /* ===== BUTTON RIPPLE EFFECT ===== */
    .stButton > button {
        position: relative;
        overflow: hidden;
    }
    
    .stButton > button::after {
        content: '';
        position: absolute;
        top: 50%;
        left: 50%;
        width: 0;
        height: 0;
        border-radius: 50%;
        background: rgba(255, 255, 255, 0.3);
        transform: translate(-50%, -50%);
        transition: width 0.6s, height 0.6s;
    }
    
    .stButton > button:active::after {
        width: 300px;
        height: 300px;
    }
    
    /* ===== SIDEBAR SLIDE-IN ANIMATION ===== */
    @keyframes slideInLeft {
        from {
            transform: translateX(-100%);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }
    
    section[data-testid="stSidebar"] {
        animation: slideInLeft 0.5s ease-out;
    }
    
    /* ===== BADGE/PILL COMPONENTS ===== */
    .badge {
        display: inline-block;
        padding: 6px 14px;
        border-radius: 20px;
        font-size: 0.85rem;
        font-weight: 600;
        background: linear-gradient(135deg, rgba(102, 126, 234, 0.2), rgba(118, 75, 162, 0.2));
        color: #ffffff;
        border: 1px solid rgba(102, 126, 234, 0.3);
        margin: 4px;
    }
    
    .badge-success {
        background: linear-gradient(135deg, rgba(72, 187, 120, 0.2), rgba(56, 161, 105, 0.2));
        border-color: rgba(72, 187, 120, 0.3);
    }
    
    .badge-warning {
        background: linear-gradient(135deg, rgba(237, 137, 54, 0.2), rgba(221, 107, 32, 0.2));
        border-color: rgba(237, 137, 54, 0.3);
    }
    
    .badge-danger {
        background: linear-gradient(135deg, rgba(245, 101, 101, 0.2), rgba(229, 62, 62, 0.2));
        border-color: rgba(245, 101, 101, 0.3);
    }
    
    /* ===== PROGRESS BARS ===== */
    .stProgress > div > div > div {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 50%, #f093fb 100%) !important;
        border-radius: 10px !important;
    }
    
    /* ===== TOOLTIP STYLE ===== */
    [data-baseweb="tooltip"] {
        background: rgba(26, 31, 53, 0.95) !important;
        backdrop-filter: blur(10px) !important;
        border: 1px solid rgba(102, 126, 234, 0.3) !important;
        border-radius: 8px !important;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3) !important;
    }
    
    /* ===== CHECKBOX/RADIO CUSTOM ===== */
    input[type="checkbox"],
    input[type="radio"] {
        accent-color: #667eea !important;
    }
    
    /* ===== NUMBER INPUT ARROWS ===== */
    input[type="number"]::-webkit-inner-spin-button,
    input[type="number"]::-webkit-outer-spin-button {
        background: linear-gradient(135deg, #667eea, #764ba2);
        border-radius: 4px;
    }
    
    /* ===== SKELETON LOADING FOR EMPTY STATES ===== */
    @keyframes skeleton-loading {
        0% {
            background-position: -200px 0;
        }
        100% {
            background-position: calc(200px + 100%) 0;
        }
    }
    
    .skeleton {
        background: linear-gradient(
            90deg,
            rgba(255, 255, 255, 0.05) 0px,
            rgba(255, 255, 255, 0.15) 40px,
            rgba(255, 255, 255, 0.05) 80px
        );
        background-size: 200px 100%;
        animation: skeleton-loading 1.5s infinite;
        border-radius: 8px;
    }
    
    /* ===== SECTION DIVIDERS WITH GRADIENT ===== */
    .gradient-divider {
        height: 2px;
        background: linear-gradient(
            90deg,
            transparent 0%,
            #667eea 20%,
            #764ba2 50%,
            #f093fb 80%,
            transparent 100%
        );
        margin: 2rem 0;
        border: none;
    }
    
    /* ===== FLOATING ACTION BUTTON STYLE ===== */
    .fab {
        position: fixed;
        bottom: 2rem;
        right: 2rem;
        width: 60px;
        height: 60px;
        border-radius: 50%;
        background: linear-gradient(135deg, #667eea, #764ba2);
        box-shadow: 0 8px 32px rgba(102, 126, 234, 0.4);
        display: flex;
        align-items: center;
        justify-content: center;
        cursor: pointer;
        transition: all 0.3s ease;
        z-index: 999;
    }
    
    .fab:hover {
        transform: scale(1.1) rotate(90deg);
        box-shadow: 0 12px 48px rgba(102, 126, 234, 0.6);
    }
    
    /* ===== TEXT GRADIENT EFFECT ===== */
    .gradient-text {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 50%, #f093fb 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 700;
    }
    
    /* ===== BLUR BACKDROP PANELS ===== */
    .glass-panel {
        background: rgba(255, 255, 255, 0.05);
        backdrop-filter: blur(20px);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 20px;
        padding: 2rem;
        box-shadow: 
            0 8px 32px 0 rgba(31, 38, 135, 0.2),
            inset 0 0 0 1px rgba(255, 255, 255, 0.05);
    }
    
    /* ===== HOVER LIFT EFFECT ===== */
    .lift-on-hover {
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    }
    
    .lift-on-hover:hover {
        transform: translateY(-8px) scale(1.02);
        box-shadow: 0 20px 60px rgba(102, 126, 234, 0.3);
    }
    
    /* ===== PULSING DOT INDICATOR ===== */
    @keyframes pulse-dot {
        0%, 100% {
            opacity: 1;
            transform: scale(1);
        }
        50% {
            opacity: 0.5;
            transform: scale(1.2);
        }
    }
    
    .status-dot {
        width: 10px;
        height: 10px;
        border-radius: 50%;
        display: inline-block;
        margin-right: 8px;
        animation: pulse-dot 2s ease-in-out infinite;
    }
    
    .status-dot.active {
        background: #48bb78;
        box-shadow: 0 0 10px #48bb78;
    }
    
    .status-dot.inactive {
        background: #f56565;
        box-shadow: 0 0 10px #f56565;
    }
    
    /* ===== CORNER ACCENT DECORATIONS ===== */
    .corner-accent::before,
    .corner-accent::after {
        content: '';
        position: absolute;
        width: 20px;
        height: 20px;
        border: 2px solid #667eea;
    }
    
    .corner-accent::before {
        top: 0;
        left: 0;
        border-right: none;
        border-bottom: none;
        border-radius: 8px 0 0 0;
    }
    
    .corner-accent::after {
        bottom: 0;
        right: 0;
        border-left: none;
        border-top: none;
        border-radius: 0 0 8px 0;
    }      


</style>
""", unsafe_allow_html=True)


# Initialize session state
# Initialize session state
if 'db' not in st.session_state:
    st.session_state.db = DatabaseManager()
    st.session_state.collector = StockDataCollector(st.session_state.db)
    st.session_state.analyzer = TechnicalAnalyzer(st.session_state.db)
    st.session_state.news_scraper = NewsScraper(st.session_state.db)  # MOVED UP - BEFORE recommender
    st.session_state.recommender = HybridRecommender(
        st.session_state.db, 
        st.session_state.analyzer,
        st.session_state.news_scraper
    )
    st.session_state.reporter = ReportGenerator(
        st.session_state.db, 
        st.session_state.analyzer, 
        st.session_state.recommender,
        st.session_state.news_scraper
    )
    st.session_state.screener = StockScreener(st.session_state.db, st.session_state.analyzer)
    st.session_state.backtester = Backtester(st.session_state.db)
    st.session_state.portfolio = PortfolioTracker(st.session_state.db)
    st.session_state.alerts = AlertsManager(st.session_state.db, st.session_state.analyzer)
    st.session_state.scheduler = TaskScheduler(
        st.session_state.db, 
        st.session_state.collector, 
        st.session_state.recommender, 
        st.session_state.reporter
    )
    st.session_state.visualizer = AdvancedVisualizations(st.session_state.db)

# Assign to shorter variables
db = st.session_state.db
collector = st.session_state.collector
analyzer = st.session_state.analyzer
recommender = st.session_state.recommender
news_scraper = st.session_state.news_scraper
reporter = st.session_state.reporter
screener = st.session_state.screener
backtester = st.session_state.backtester
portfolio = st.session_state.portfolio
alerts = st.session_state.alerts
scheduler = st.session_state.scheduler
visualizer = st.session_state.visualizer

# ==================== SIDEBAR ====================
st.sidebar.title("📊 Stock Analyzer Pro")
st.sidebar.markdown("### 🚀 Ultimate Edition")
st.sidebar.markdown("---")

st.sidebar.markdown("""
<style>
.big-radio {
    font-size: 1.2rem !important;
    padding: 15px !important;
    font-weight: 600 !important;
}
</style>
""", unsafe_allow_html=True)

# The radio still works the same but with custom styling
page = st.sidebar.radio(
    "Navigation",
    [
        "🏠 Dashboard",
        "📈 Stock Analysis",
        "⭐ Watchlist",
        "🏆 Stock Categories",
        "🎯 Recommendations",
        "🔍 Stock Screener",
        "📊 Backtesting",
        "💼 Portfolio Tracker",
        "🔔 Alerts",
        "📰 News",
        "📋 Reports",
        "📈 Advanced Charts",
        "⏰ Scheduler",
        "⚙️ Settings"
    ],
    label_visibility="visible"
)
# Check if we need to navigate to settings from AI button
if 'navigate_to_settings' in st.session_state and st.session_state.navigate_to_settings:
    page = "⚙️ Settings"
    st.session_state.navigate_to_settings = False

st.sidebar.markdown("---")
st.sidebar.markdown("### ⚡ Quick Actions")

# Quick add to watchlist
col1, col2 = st.sidebar.columns([3, 1])
with col1:
    new_symbol = st.text_input("Add Stock", placeholder="AAPL", label_visibility="collapsed")
with col2:
    if st.button("➕"):
        if new_symbol:
            db.add_to_watchlist(new_symbol.upper())
            st.success(f"✅ {new_symbol.upper()}")
            st.rerun()

# Quick actions
if st.sidebar.button("🔄 Update Watchlist"):
    with st.spinner("Updating..."):
        collector.update_all_watchlist_stocks(period="1mo")
    st.sidebar.success("✅ Updated!")

if st.sidebar.button("🎯 Analyze All"):
    with st.spinner("Analyzing..."):
        recommender.analyze_watchlist()
    st.sidebar.success("✅ Done!")

st.sidebar.markdown("---")
st.sidebar.markdown("### 📊 Statistics")
st.sidebar.markdown("---")
portfolio_value = portfolio.get_portfolio_value()
if portfolio_value['current_value'] > 0:
    st.sidebar.markdown("---")
    pf_val = f"${portfolio_value['current_value']:,.2f}"
    pf_pct = f"{portfolio_value['gain_loss_pct']:+.2f}%"
    pf_color = "#00ff00" if portfolio_value['gain_loss_pct'] >= 0 else "#ff6b6b"
    
    st.sidebar.markdown(f"""
    <div style='background: rgba(0,0,0,0.5); padding: 15px; border-radius: 10px; margin: 10px 0; text-align: center;'>
        <div style='color: #ffffff; font-size: 0.9rem; margin-bottom: 5px;'>💼 Portfolio</div>
        <div style='color: #00ff00; font-size: 1.5rem; font-weight: 700;'>{pf_val}</div>
        <div style='color: {pf_color}; font-size: 1rem; margin-top: 5px;'>{pf_pct}</div>
    </div>
    """, unsafe_allow_html=True)

# ============ ADD THIS AI STATUS SECTION ============
# ============ AI STATUS WITH CLICKABLE LINK ============
st.sidebar.markdown("---")

import config

ai_enabled = hasattr(config, 'USE_AI_ANALYSIS') and config.USE_AI_ANALYSIS

if ai_enabled:
    st.sidebar.markdown("""
    <div style='background: rgba(0,200,0,0.2); padding: 15px; border-radius: 10px; border: 2px solid #00ff00;'>
        <div style='color: #00ff00; font-size: 1.1rem; font-weight: 700; text-align: center;'>
            🤖 AI-POWERED
        </div>
        <div style='color: #ffffff; font-size: 0.85rem; text-align: center; margin-top: 5px;'>
            Using Claude AI
        </div>
    </div>
    """, unsafe_allow_html=True)
else:
    st.sidebar.markdown("""
    <div style='background: rgba(100,100,100,0.2); padding: 15px; border-radius: 10px; border: 1px solid rgba(255,255,255,0.2);'>
        <div style='color: #ffffff; font-size: 1.1rem; font-weight: 600; text-align: center;'>
            📊 TECHNICAL ANALYSIS
        </div>
        <div style='color: #cccccc; font-size: 0.85rem; text-align: center; margin-top: 5px;'>
            Traditional indicators
        </div>
    </div>
    """, unsafe_allow_html=True)

# Add clickable button to change mode
if st.sidebar.button("⚙️ Configure AI", key='ai_settings_btn'):
    # This will navigate to settings by setting the page
    st.session_state.navigate_to_settings = True
    st.rerun()
# ============ END AI STATUS SECTION ============

# ==================== PAGE: DASHBOARD ====================
# Copy this ENTIRE section and replace the Dashboard page in ui/dashboard.py

if page == "🏠 Dashboard":
    st.markdown('<div class="main-header">🚀 Stock Analyzer Dashboard</div>', unsafe_allow_html=True)
    
    # Top metrics row with custom HTML for white text
    col1, col2, col3, col4, col5 = st.columns(5)
    
    watchlist = db.get_watchlist()
    recent_recs = db.get_latest_recommendations(days=7)
    
    with col1:
        st.markdown(f"""
        <div style='background: rgba(0,0,0,0.3); padding: 20px; border-radius: 12px; text-align: center; border: 1px solid rgba(255,255,255,0.15);'>
            <div style='color: #ffffff; font-size: 1rem; font-weight: 500; margin-bottom: 10px;'>📋 Watchlist</div>
            <div style='color: #ffffff; font-size: 2rem; font-weight: 700;'>{len(watchlist)}</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"""
        <div style='background: rgba(0,0,0,0.3); padding: 20px; border-radius: 12px; text-align: center; border: 1px solid rgba(255,255,255,0.15);'>
            <div style='color: #ffffff; font-size: 1rem; font-weight: 500; margin-bottom: 10px;'>🎯 Recs (7d)</div>
            <div style='color: #ffffff; font-size: 2rem; font-weight: 700;'>{len(recent_recs)}</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        buy_count = len(recent_recs[recent_recs['recommendation'].str.contains('BUY')]) if not recent_recs.empty else 0
        st.markdown(f"""
        <div style='background: rgba(0,0,0,0.3); padding: 20px; border-radius: 12px; text-align: center; border: 1px solid rgba(255,255,255,0.15);'>
            <div style='color: #ffffff; font-size: 1rem; font-weight: 500; margin-bottom: 10px;'>✅ Buys</div>
            <div style='color: #ffffff; font-size: 2rem; font-weight: 700;'>{buy_count}</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        sell_count = len(recent_recs[recent_recs['recommendation'].str.contains('SELL')]) if not recent_recs.empty else 0
        st.markdown(f"""
        <div style='background: rgba(0,0,0,0.3); padding: 20px; border-radius: 12px; text-align: center; border: 1px solid rgba(255,255,255,0.15);'>
            <div style='color: #ffffff; font-size: 1rem; font-weight: 500; margin-bottom: 10px;'>⚠️ Sells</div>
            <div style='color: #ffffff; font-size: 2rem; font-weight: 700;'>{sell_count}</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col5:
        pf = portfolio.get_portfolio_value()
        pf_value = f"${pf['current_value']:,.0f}" if pf['current_value'] > 0 else "$0.00"
        pf_change = f"{pf['gain_loss_pct']:+.1f}%" if pf['current_value'] > 0 else ""
        change_color = "#00ff00" if pf.get('gain_loss_pct', 0) >= 0 else "#ff6b6b"
        
        st.markdown(f"""
        <div style='background: rgba(0,0,0,0.3); padding: 20px; border-radius: 12px; text-align: center; border: 1px solid rgba(255,255,255,0.15);'>
            <div style='color: #ffffff; font-size: 1rem; font-weight: 500; margin-bottom: 10px;'>💼 Portfolio</div>
            <div style='color: #ffffff; font-size: 1.8rem; font-weight: 700;'>{pf_value}</div>
            <div style='color: {change_color}; font-size: 1rem; margin-top: 5px;'>{pf_change}</div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Continue with the rest of the dashboard (Opportunities and Alerts sections)
    
    # Opportunities and Alerts
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("🔥 Top Opportunities")
        if not recent_recs.empty:
            top_buys = recent_recs[recent_recs['recommendation'].str.contains('BUY')].nlargest(5, 'score')
            
            if not top_buys.empty:
                for _, rec in top_buys.iterrows():
                    st.markdown(f"""
                    <div style='background-color: #d4edda; border-left: 6px solid #28a745; 
                                padding: 15px; border-radius: 8px; margin: 10px 0;'>
                        <div style='color: #155724; font-size: 1.1rem; font-weight: 600;'>
                            {rec['symbol']} - {rec['recommendation']}
                        </div>
                        <div style='color: #155724; font-size: 0.9rem; margin-top: 5px;'>
                            Score: {rec['score']:.0f}/100 | Price: ${rec['price_at_recommendation']:.2f}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.info("No buy recommendations yet")
        else:
            st.info("Analyze stocks to see opportunities")
    
    with col2:
        st.subheader("⚠️ Risk Alerts")
        if not recent_recs.empty:
            sells = recent_recs[recent_recs['recommendation'].str.contains('SELL')].head(5)
            
            if not sells.empty:
                for _, rec in sells.iterrows():
                    st.markdown(f"""
                    <div style='background-color: #f8d7da; border-left: 6px solid #dc3545; 
                                padding: 15px; border-radius: 8px; margin: 10px 0;'>
                        <div style='color: #721c24; font-size: 1.1rem; font-weight: 600;'>
                            {rec['symbol']} - {rec['recommendation']}
                        </div>
                        <div style='color: #721c24; font-size: 0.9rem; margin-top: 5px;'>
                            Score: {rec['score']:.0f}/100 | Price: ${rec['price_at_recommendation']:.2f}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.success("✅ No sell signals - portfolio looks good!")
        else:
            st.info("Generate recommendations to see alerts")
# ==================== PAGE: STOCK ANALYSIS ====================
elif page == "📈 Stock Analysis":
    st.markdown('<div class="main-header">📈 Deep Stock Analysis</div>', unsafe_allow_html=True)
    
    # Info box
    with st.expander("ℹ️ How This Analysis Works", expanded=False):
        st.markdown("""
        ### 📊 What You're Analyzing:
        
        **✅ CURRENT CONDITIONS** (as of today):
        - Today's stock price
        - Recent technical indicators (RSI, MACD, Moving Averages)
        - Last 7 days of news and catalysts
        - Current momentum and trend direction
        
        **📅 Historical Data Period:**
        This setting controls how far back we look to calculate trends:
        - **1 month:** Good for spotting very recent momentum
        - **3 months:** Captures swing trade patterns
        - **6 months:** Balanced view (recommended)
        - **1 year:** Full technical picture with all indicators
        - **2 years:** Sees major trend reversals (golden/death crosses)
        
        **🎯 Time Horizons (AI Mode):**
        The AI recommends when you should expect results:
        - **SHORT-TERM (3-10 days):** Quick momentum trades
        - **SWING TRADE (2-8 weeks):** Catalyst-driven moves
        - **LONG-TERM (6-18 months):** Major breakthrough plays
        
        💡 *You can analyze ANY publicly traded US stock!*
        """)
    
    st.markdown("---")
    
    col1, col2, col3 = st.columns([2, 2, 1])
    
    with col1:
        symbol = st.text_input(
            "Stock Symbol",
            placeholder="Enter any ticker: TSLA, META, SHOP, NVDA, COIN...",
            help="Type any valid US stock ticker symbol",
            key="stock_symbol_input"
        ).upper()
        
        # Get previously analyzed stocks FIRST (before using it)
        all_symbols = db.get_all_symbols()
        
        # Show quick select buttons for previously analyzed
        if all_symbols and not symbol:
            st.caption("💡 Quick select from recently analyzed:")
            
            # CSS to make buttons fit better
            st.markdown("""
            <style>
            div[data-testid="column"] > div > div > button {
                font-size: 0.8rem !important;
                padding: 0.25rem 0.5rem !important;
                white-space: nowrap !important;
                min-width: px !important;
            }
            </style>
            """, unsafe_allow_html=True)
            
            # Use more columns for better spacing
            num_stocks = min(len(all_symbols), 8)
            quick_cols = st.columns(num_stocks)
            
            for idx in range(num_stocks):
                stock = all_symbols[idx]
                with quick_cols[idx]:
                    if st.button(
                        stock, 
                        key=f"quick_select_{stock}",
                        use_container_width=True
                    ):
                        st.session_state.selected_symbol = stock
                        st.rerun()
        
        # Check if symbol was selected via button
        if 'selected_symbol' in st.session_state:
            symbol = st.session_state.selected_symbol
            del st.session_state.selected_symbol
    
    with col2:
        period = st.selectbox(
            "Historical Data Period",
            ["5d", "1mo", "3mo", "6mo", "1y", "2y", "5y"],
            index=3,
            help="How much price history to download for analysis"
        )
        
        period_descriptions = {
            "5d": "📊 5 Days - Ultra short-term",
            "1mo": "📊 1 Month - Recent trends",
            "3mo": "📊 3 Months - Swing trades",
            "6mo": "📊 6 Months - Balanced (recommended)",
            "1y": "📊 1 Year - Full technical picture",
            "2y": "📊 2 Years - Long-term trends",
            "5y": "📊 5 Years - Complete history"
        }
        st.caption(period_descriptions[period])
    
    with col3:
        st.write("")
        st.write("")
        analyze_btn = st.button("🔍 Analyze", type="primary")
    
    if symbol and analyze_btn:
        with st.spinner(f"Analyzing {symbol}..."):
            collector.fetch_and_save(symbol, period=period)
            result = recommender.analyze_and_recommend(symbol)
            
# Instead of the old markdown card, use:
            if result:
                card_html = create_recommendation_card(
                        symbol=symbol,
                        rec=result['recommendation'],
                        score=result['score'],
                        price=result['price'],
                        reasoning=result.get('reasoning', '')
                )
                st.markdown(card_html, unsafe_allow_html=True)
            if result:
                rec = result['recommendation']
                score = result['score']
                
                if "BUY" in rec:
                    color = "#00cc00"
                elif "SELL" in rec:
                    color = "#ff0000"
                else:
                    color = "#ffaa00"
                
                # Check if AI provided time horizon
                time_horizon = result.get('time_horizon', 'Not specified')
                confidence = result.get('confidence', 'Not specified')
                
                st.markdown(f"""
                <div style='background: linear-gradient(135deg, {color}30, {color}10); 
                            padding: 30px; border-radius: 15px; border-left: 8px solid {color};'>
                    <h1 style='color: {color}; margin: 0;'>{rec}</h1>
                    <h2 style='margin: 10px 0;'>Score: {score}/100</h2>
                    <p style='font-size: 1.3rem; margin: 0;'>💰 ${result['price']:.2f}</p>
                </div>
                """, unsafe_allow_html=True)
                
                # Show time horizon and confidence if AI analysis
                if time_horizon != 'Not specified':
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        horizon_emoji = {
                            'SHORT-TERM': '⚡',
                            'SWING': '📈',
                            'LONG-TERM': '🎯'
                        }
                        emoji = horizon_emoji.get(time_horizon.upper(), '📊')
                        
                        st.info(f"{emoji} **Time Horizon:** {time_horizon}")
                        
                        horizon_desc = {
                            'SHORT-TERM': "3-10 days - Quick momentum play",
                            'SWING': "2-8 weeks - Medium-term catalyst",
                            'LONG-TERM': "6-18 months - Major breakthrough potential"
                        }
                        st.caption(horizon_desc.get(time_horizon.upper(), "Based on current analysis"))
                    
                    with col2:
                        conf_color = {
                            'HIGH': '🟢',
                            'MEDIUM': '🟡',
                            'LOW': '🟠'
                        }
                        conf_emoji = conf_color.get(confidence.upper(), '⚪')
                        
                        st.info(f"{conf_emoji} **Confidence:** {confidence}")
                
                st.markdown("---")
                
                st.subheader("📊 Analysis Details")
                st.text(result['reasoning'])

                with st.expander("📖 How This Score Was Calculated"):
                 st.markdown("""
    ### Technical Analysis Scoring System
    
    **Starting Score:** 50 (Neutral)
    
    **Indicators That Can Increase Score (Bullish):**
    - RSI < 30 (Oversold): +15 points
    - MACD Bullish Crossover: +10 points
    - Golden Cross (50-MA > 200-MA): +10 points
    - Price Near Lower Bollinger Band: +10 points
    - Stochastic < 20: +8 points
    - Price Above 20-day MA: +5 points
    
    **Indicators That Can Decrease Score (Bearish):**
    - RSI > 70 (Overbought): -15 points
    - MACD Bearish Crossover: -10 points
    - Death Cross (50-MA < 200-MA): -10 points
    - Price Near Upper Bollinger Band: -10 points
    - Stochastic > 80: -8 points
    - Price Below 20-day MA: -5 points
    
    **Final Rating:**
    - 70-100: STRONG BUY 🟢
    - 55-69: BUY 🟢
    - 45-54: HOLD 🟡
    - 30-44: SELL 🔴
    - 0-29: STRONG SELL 🔴
    """)
                
                st.markdown("---")
                
                df = analyzer.calculate_all_indicators(symbol)
                
                if df is not None and not df.empty:
                    st.subheader("📈 Technical Charts")
                    
                    fig = make_subplots(
                        rows=4, cols=1,
                        shared_xaxes=True,
                        vertical_spacing=0.03,
                        row_heights=[0.4, 0.2, 0.2, 0.2],
                        subplot_titles=('Price & Indicators', 'Volume', 'RSI', 'MACD')
                    )
                    
                    fig.add_trace(go.Candlestick(
                        x=df.index,
                        open=df['open'],
                        high=df['high'],
                        low=df['low'],
                        close=df['close'],
                        name='Price'
                    ), row=1, col=1)
                    
                    colors_ma = {'SMA_20': 'orange', 'SMA_50': 'blue', 'SMA_200': 'red'}
                    for ma in ['SMA_20', 'SMA_50', 'SMA_200']:
                        if ma in df.columns:
                            fig.add_trace(go.Scatter(
                                x=df.index, y=df[ma], 
                                name=ma, line=dict(color=colors_ma[ma])
                            ), row=1, col=1)
                    
                    if 'BB_Upper' in df.columns:
                        fig.add_trace(go.Scatter(
                            x=df.index, y=df['BB_Upper'],
                            name='BB Upper', line=dict(color='gray', dash='dash')
                        ), row=1, col=1)
                        fig.add_trace(go.Scatter(
                            x=df.index, y=df['BB_Lower'],
                            name='BB Lower', line=dict(color='gray', dash='dash'),
                            fill='tonexty', fillcolor='rgba(128,128,128,0.1)'
                        ), row=1, col=1)
                    
                    colors_vol = ['red' if df['close'].iloc[i] < df['open'].iloc[i] else 'green' 
                                  for i in range(len(df))]
                    fig.add_trace(go.Bar(
                        x=df.index, y=df['volume'],
                        name='Volume', marker_color=colors_vol
                    ), row=2, col=1)
                    
                    if 'RSI' in df.columns:
                        fig.add_trace(go.Scatter(
                            x=df.index, y=df['RSI'],
                            name='RSI', line=dict(color='purple')
                        ), row=3, col=1)
                        fig.add_hline(y=70, line_dash="dash", line_color="red", row=3, col=1)
                        fig.add_hline(y=30, line_dash="dash", line_color="green", row=3, col=1)
                    
                    if 'MACD' in df.columns:
                        fig.add_trace(go.Scatter(
                            x=df.index, y=df['MACD'],
                            name='MACD', line=dict(color='blue')
                        ), row=4, col=1)
                        fig.add_trace(go.Scatter(
                            x=df.index, y=df['MACD_Signal'],
                            name='Signal', line=dict(color='orange')
                        ), row=4, col=1)
                    
                    fig.update_layout(
                        height=1000,
                        showlegend=True,
                        xaxis_rangeslider_visible=False,
                        hovermode='x unified'
                    )
                    
                    st.plotly_chart(fig, use_container_width=True)
                
                        
    

# ==================== PAGE: WATCHLIST ====================
elif page == "⭐ Watchlist":
    st.markdown('<div class="main-header">⭐ Your Watchlist</div>', unsafe_allow_html=True)
    
    watchlist = db.get_watchlist()
    
    if watchlist.empty:
        st.info("Your watchlist is empty. Add stocks from the Stock Categories page!")
    else:
        st.write(f"**Watching {len(watchlist)} stocks**")
        
        st.markdown("---")
        st.subheader("⚡ Bulk Actions")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("📊 Analyze All Stocks", type="primary", key='analyze_all_watchlist'):
                with st.spinner(f"Analyzing {len(watchlist)} stocks... This may take 2-3 minutes..."):
                    try:
                        # Show progress
                        progress_text = st.empty()
                        
                        for idx, symbol in enumerate(watchlist['symbol'].tolist()):
                            progress_text.text(f"Analyzing {symbol}... ({idx+1}/{len(watchlist)})")
                            
                            # Analyze this stock
                            result = recommender.analyze_and_recommend(symbol)
                            
                            if result:
                                st.success(f"✅ {symbol}: {result['recommendation']} ({result['score']:.0f}/100)")
                        
                        progress_text.empty()
                        st.success(f"✅ Analysis complete! Analyzed {len(watchlist)} stocks.")
                        st.info("💡 Go to the 🎯 Recommendations page to see all results!")
                        
                    except Exception as e:
                        st.error(f"Error during analysis: {str(e)}")
        
        with col2:
            if st.button("🔄 Update All Prices", key='update_all_watchlist'):
                with st.spinner(f"Updating prices for {len(watchlist)} stocks..."):
                    try:
                        collector.update_all_watchlist_stocks(period="1mo")
                        st.success("✅ Prices updated!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {str(e)}")
        
        with col3:
            if st.button("📰 Fetch All News", key='fetch_all_news'):
                with st.spinner("Fetching news..."):
                    try:
                        count = 0
                        for symbol in watchlist['symbol'].tolist()[:5]:  # Limit to 5 to avoid rate limits
                            articles = news_scraper.fetch_stock_news(symbol, days=7)
                            news_scraper.save_news(articles)
                            count += len(articles)
                        st.success(f"✅ Fetched {count} articles!")
                    except Exception as e:
                        st.error(f"Error: {str(e)}")
        
        st.markdown("---")
        st.subheader("📋 Your Stocks")
        
        # Display watchlist
        for idx, row in watchlist.iterrows():
            col1, col2, col3, col4, col5 = st.columns([2, 2, 3, 1, 1])
            
            with col1:
                st.write(f"**{row['symbol']}**")
            
            with col2:
                latest = db.get_latest_price(row['symbol'])
                if latest:
                    st.write(f"${latest['price']:.2f}")
                else:
                    st.write("—")
            
            with col3:
                st.write(row['notes'] if row['notes'] else "—")
            
            with col4:
                if st.button("📊", key=f"analyze_single_{row['symbol']}", help=f"Analyze {row['symbol']}"):
                    with st.spinner(f"Analyzing {row['symbol']}..."):
                        result = recommender.analyze_and_recommend(row['symbol'])
                        if result:
                            st.success(f"{result['recommendation']} ({result['score']:.0f}/100)")
            
            with col5:
                if st.button("🗑️", key=f"del_{row['symbol']}", help="Remove"):
                    db.remove_from_watchlist(row['symbol'])
                    st.rerun()

# ==================== PAGE: STOCK CATEGORIES ====================
elif page == "🏆 Stock Categories":
    st.markdown('<div class="main-header">🏆 Stock Categories</div>', unsafe_allow_html=True)
    
    st.markdown("""
    Browse stocks by category and add them to your watchlist with one click.
    Categories are organized by sector and investment theme.
    """)
    
    st.markdown("---")
    
    # Organize categories into tabs
    tab1, tab2, tab3, tab4 = st.tabs(["🚀 Growth & Tech", "💰 Defensive & Income", "🌍 Emerging Sectors", "📊 Index Funds"])
    
    with tab1:
        st.subheader("Growth & Technology")
    
        growth_categories = {
        "💻 Tech Giants": config.TECH_STOCKS,
        "🤖 AI & Machine Learning": config.AI_TECH_STOCKS,
        "⚛️ Quantum Computing": config.QUANTUM_TECH,
        "🎮 Gaming & Metaverse": ["RBLX", "U", "TTWO", "EA", "ATVI"],
        "🔬 Semiconductors": config.SEMICONDUCTOR_STOCKS,  # ← NEW CATEGORY
    }
        
        for category, stocks in growth_categories.items():
            with st.expander(f"{category} ({len(stocks)} stocks)"):
                cols = st.columns(5)
                for i, stock in enumerate(stocks):
                    with cols[i % 5]:
                        if st.button(f"➕ {stock}", key=f"add_{category}_{stock}_{i}"):
                            db.add_to_watchlist(stock, notes=category)
                            st.success(f"✅ Added {stock}")
                            st.rerun()
    
    with tab2:
        st.subheader("Defensive & Income")
        
        defensive_categories = {
            "💰 Dividend Aristocrats": config.DIVIDEND_STOCKS,
            "🏅 Precious Metals": config.PRECIOUS_METALS + config.GOLD_MINERS,
            "📈 Government Bonds": config.BONDS,
            "🏢 REITs": ["VNQ", "O", "VICI", "SPG", "PSA"],
        }
        
        for category, stocks in defensive_categories.items():
            with st.expander(f"{category} ({len(stocks)} stocks)"):
                cols = st.columns(5)
                for i, stock in enumerate(stocks):
                    with cols[i % 5]:
                        if st.button(f"➕ {stock}", key=f"add_{category}_{stock}_{i}"):
                            db.add_to_watchlist(stock, notes=category)
                            st.success(f"✅ Added {stock}")
                            st.rerun()
    
    with tab3:
        st.subheader("Emerging Sectors")
        
        emerging_categories = {
            "🧬 Biotech & Genomics": config.BIOTECH_STOCKS,
            "🚀 Space & Aerospace": config.SPACE_STOCKS,
            "🌱 Clean Energy": config.CLEAN_ENERGY,
            "🛡️ Defense Technology": config.DEFENSE_STOCKS,
            "₿ Crypto-Related": config.CRYPTO_RELATED,
        }
        
        for category, stocks in emerging_categories.items():
            with st.expander(f"{category} ({len(stocks)} stocks)"):
                cols = st.columns(5)
                for i, stock in enumerate(stocks):
                    with cols[i % 5]:
                        if st.button(f"➕ {stock}", key=f"add_{category}_{stock}_{i}"):
                            db.add_to_watchlist(stock, notes=category)
                            st.success(f"✅ Added {stock}")
                            st.rerun()
    
    with tab4:
        st.subheader("Index Funds & ETFs")
        
        index_categories = {
            "🏢 Market Indices": config.MARKET_ETFS,
            "🌍 International": config.INTERNATIONAL_ETFS,
        }
        
        for category, stocks in index_categories.items():
            with st.expander(f"{category} ({len(stocks)} stocks)"):
                cols = st.columns(5)
                for i, stock in enumerate(stocks):
                    with cols[i % 5]:
                        if st.button(f"➕ {stock}", key=f"add_{category}_{stock}_{i}"):
                            db.add_to_watchlist(stock, notes=category)
                            st.success(f"✅ Added {stock}")
                            st.rerun()

# ==================== PAGE: RECOMMENDATIONS ====================
elif page == "🎯 Recommendations":
    st.markdown('<div class="main-header">🎯 Recommendations</div>', unsafe_allow_html=True)
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        days = st.slider("Show last N days", 1, 90, 30)
    
    with col2:
        st.write("")
        if st.button("🔄 Refresh"):
            with st.spinner("Analyzing..."):
                recommender.analyze_watchlist()
            st.success("Done!")
            st.rerun()
    
    recs = db.get_latest_recommendations(days=days)
    
    if recs.empty:
        st.info("No recommendations. Analyze stocks first!")
    else:
        filter_type = st.multiselect(
            "Filter by recommendation type",
            ["STRONG BUY", "BUY", "HOLD", "SELL", "STRONG SELL"],
            default=None,  # No default - show all
            help="Leave empty to show all recommendations"
            )
        
        
        filtered = recs[recs['recommendation'].isin(filter_type)] if filter_type else recs
        
        st.write(f"**{len(filtered)} recommendations**")
        
        for _, rec in filtered.iterrows():
            with st.expander(f"**{rec['symbol']}** - {rec['recommendation']} ({rec['date']})"):
                col1, col2 = st.columns(2)
                
                with col1:
                    st.metric("Score", f"{rec['score']:.0f}/100")
                    st.metric("Price", f"${rec['price_at_recommendation']:.2f}")
                
                with col2:
                    current = db.get_latest_price(rec['symbol'])
                    if current:
                        change = ((current['price'] - rec['price_at_recommendation']) / rec['price_at_recommendation']) * 100
                        st.metric("Current", f"${current['price']:.2f}", f"{change:+.2f}%")
                
                st.text(rec['reasoning'])

# ==================== PAGE: STOCK SCREENER ====================
elif page == "🔍 Stock Screener":
    st.markdown('<div class="main-header">🔍 Advanced Stock Screener</div>', unsafe_allow_html=True)
    
    st.markdown("""
    Find stocks matching specific technical patterns and criteria.
    All screens use **current market data** to find opportunities.
    """)
    
    # Check if we have enough data
    scannable_stocks = screener.get_scannable_stocks()
    
    if not scannable_stocks or len(scannable_stocks) < 3:
        st.warning("⚠️ You need at least 3 stocks with data to use the screener.")
        st.info("💡 Go to Watchlist → Update All Prices to fetch data first!")
    else:
        st.success(f"✅ Ready to screen {len(scannable_stocks)} stocks")
        
        st.markdown("---")
        
        # Create tabs for different screening modes
        tab1, tab2, tab3, tab4, tab5 = st.tabs([
            "🎯 Quick Screens", 
            "🔥 Momentum & Trends",
            "📊 Technical Patterns",
            "🎨 Custom Screen",
            "⚡ Scan All"
        ])
        
        # ========== TAB 1: QUICK SCREENS ==========
        with tab1:
            st.subheader("🎯 Quick Pre-Built Screens")
            st.write("Fast screening strategies for common opportunities")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("### 🟢 Buying Opportunities")
                
                # Oversold stocks
                if st.button("🔍 Find Oversold Stocks", key="btn_oversold", use_container_width=True):
                    with st.spinner("Scanning for oversold stocks..."):
                        results = screener.screen_oversold_stocks(rsi_threshold=30)
                    
                    if not results.empty:
                        st.success(f"✅ Found {len(results)} oversold stocks")
                        
                        # Format for display
                        display_df = results[['symbol', 'price', 'rsi', 'signal']].copy()
                        display_df['price'] = display_df['price'].apply(lambda x: f"${x:.2f}")
                        display_df['rsi'] = display_df['rsi'].apply(lambda x: f"{x:.1f}")
                        display_df.columns = ['Symbol', 'Price', 'RSI', 'Signal']
                        
                        st.dataframe(display_df, use_container_width=True, hide_index=True)
                        
                        # Quick action buttons
                        st.markdown("**Quick Actions:**")
                        action_cols = st.columns(len(results[:5]))
                        for idx, (_, row) in enumerate(results[:5].iterrows()):
                            with action_cols[idx]:
                                if st.button(f"Analyze {row['symbol']}", key=f"analyze_oversold_{row['symbol']}"):
                                    st.session_state.navigate_to_analysis = row['symbol']
                                    st.rerun()
                    else:
                        st.info("No oversold stocks found with current criteria")
                
                st.markdown("---")
                
                # Near 52-week lows
                if st.button("🔍 Near 52-Week Lows", key="btn_52w_low", use_container_width=True):
                    with st.spinner("Scanning for value opportunities..."):
                        results = screener.screen_price_near_52w_low(threshold_pct=5)
                    
                    if not results.empty:
                        st.success(f"✅ Found {len(results)} stocks near 52-week lows")
                        
                        display_df = results[['symbol', 'price', '52w_low', 'distance_pct']].copy()
                        display_df['price'] = display_df['price'].apply(lambda x: f"${x:.2f}")
                        display_df['52w_low'] = display_df['52w_low'].apply(lambda x: f"${x:.2f}")
                        display_df['distance_pct'] = display_df['distance_pct'].apply(lambda x: f"{x:.1f}%")
                        display_df.columns = ['Symbol', 'Current Price', '52W Low', 'Distance']
                        
                        st.dataframe(display_df, use_container_width=True, hide_index=True)
                    else:
                        st.info("No stocks near 52-week lows found")
                
                st.markdown("---")
                
                # MACD Bullish Crossover
                if st.button("🔍 MACD Bullish Signals", key="btn_macd", use_container_width=True):
                    with st.spinner("Scanning for MACD crossovers..."):
                        results = screener.screen_macd_bullish_crossover()
                    
                    if not results.empty:
                        st.success(f"✅ Found {len(results)} MACD bullish crossovers")
                        
                        display_df = results[['symbol', 'price', 'macd', 'signal_line']].copy()
                        display_df['price'] = display_df['price'].apply(lambda x: f"${x:.2f}")
                        display_df['macd'] = display_df['macd'].apply(lambda x: f"{x:.2f}")
                        display_df['signal_line'] = display_df['signal_line'].apply(lambda x: f"{x:.2f}")
                        display_df.columns = ['Symbol', 'Price', 'MACD', 'Signal Line']
                        
                        st.dataframe(display_df, use_container_width=True, hide_index=True)
                    else:
                        st.info("No MACD crossovers detected")
            
            with col2:
                st.markdown("### 🔴 Warning Signals")
                
                # Overbought stocks
                if st.button("🔍 Find Overbought Stocks", key="btn_overbought", use_container_width=True):
                    with st.spinner("Scanning for overbought stocks..."):
                        results = screener.screen_overbought_stocks(rsi_threshold=70)
                    
                    if not results.empty:
                        st.warning(f"⚠️ Found {len(results)} overbought stocks")
                        
                        display_df = results[['symbol', 'price', 'rsi', 'signal']].copy()
                        display_df['price'] = display_df['price'].apply(lambda x: f"${x:.2f}")
                        display_df['rsi'] = display_df['rsi'].apply(lambda x: f"{x:.1f}")
                        display_df.columns = ['Symbol', 'Price', 'RSI', 'Signal']
                        
                        st.dataframe(display_df, use_container_width=True, hide_index=True)
                    else:
                        st.info("No overbought stocks found")
                
                st.markdown("---")
                
                # Near 52-week highs
                if st.button("🔍 Near 52-Week Highs", key="btn_52w_high", use_container_width=True):
                    with st.spinner("Scanning..."):
                        results = screener.screen_price_near_52w_high(threshold_pct=5)
                    
                    if not results.empty:
                        st.info(f"📊 Found {len(results)} stocks near 52-week highs")
                        
                        display_df = results[['symbol', 'price', '52w_high', 'distance_pct']].copy()
                        display_df['price'] = display_df['price'].apply(lambda x: f"${x:.2f}")
                        display_df['52w_high'] = display_df['52w_high'].apply(lambda x: f"${x:.2f}")
                        display_df['distance_pct'] = display_df['distance_pct'].apply(lambda x: f"{x:.1f}%")
                        display_df.columns = ['Symbol', 'Current Price', '52W High', 'Distance']
                        
                        st.dataframe(display_df, use_container_width=True, hide_index=True)
                    else:
                        st.info("No stocks near 52-week highs found")
                
                st.markdown("---")
                
                # Death Cross
                if st.button("🔍 Death Cross Patterns", key="btn_death", use_container_width=True):
                    with st.spinner("Scanning for death crosses..."):
                        results = screener.screen_death_cross()
                    
                    if not results.empty:
                        st.warning(f"⚠️ Found {len(results)} death cross patterns")
                        
                        display_df = results[['symbol', 'price', 'sma_50', 'sma_200', 'strength']].copy()
                        display_df['price'] = display_df['price'].apply(lambda x: f"${x:.2f}")
                        display_df['sma_50'] = display_df['sma_50'].apply(lambda x: f"${x:.2f}")
                        display_df['sma_200'] = display_df['sma_200'].apply(lambda x: f"${x:.2f}")
                        display_df['strength'] = display_df['strength'].apply(lambda x: f"{x:.1f}%")
                        display_df.columns = ['Symbol', 'Price', '50-MA', '200-MA', 'Strength']
                        
                        st.dataframe(display_df, use_container_width=True, hide_index=True)
                    else:
                        st.info("No death cross patterns found")
        
        # ========== TAB 2: MOMENTUM & TRENDS ==========
        with tab2:
            st.subheader("🔥 Momentum & Trend Screens")
            
            col1, col2 = st.columns(2)
            
            with col1:
                # Golden Cross
                if st.button("🟢 Golden Cross Stocks", key="btn_golden", type="primary", use_container_width=True):
                    with st.spinner("Scanning for golden crosses..."):
                        results = screener.screen_golden_cross()
                    
                    if not results.empty:
                        st.success(f"✅ Found {len(results)} golden cross stocks")
                        
                        display_df = results[['symbol', 'price', 'strength', 'signal']].copy()
                        display_df['price'] = display_df['price'].apply(lambda x: f"${x:.2f}")
                        display_df['strength'] = display_df['strength'].apply(lambda x: f"{x:.1f}%")
                        display_df.columns = ['Symbol', 'Price', 'Separation', 'Signal']
                        
                        st.dataframe(display_df, use_container_width=True, hide_index=True)
                        
                        # Download button
                        csv = results.to_csv(index=False)
                        st.download_button(
                            "📥 Download Results",
                            csv,
                            "golden_cross_stocks.csv",
                            "text/csv"
                        )
                    else:
                        st.info("No golden cross patterns found")
            
            with col2:
                # High Momentum
                if st.button("⚡ High Momentum Stocks", key="btn_momentum", type="primary", use_container_width=True):
                    with st.spinner("Scanning for momentum..."):
                        results = screener.screen_high_momentum()
                    
                    if not results.empty:
                        st.success(f"✅ Found {len(results)} high momentum stocks")
                        
                        display_df = results[['symbol', 'price', 'momentum_20d', 'rsi']].copy()
                        display_df['price'] = display_df['price'].apply(lambda x: f"${x:.2f}")
                        display_df['momentum_20d'] = display_df['momentum_20d'].apply(lambda x: f"{x:+.1f}%")
                        display_df['rsi'] = display_df['rsi'].apply(lambda x: f"{x:.1f}")
                        display_df.columns = ['Symbol', 'Price', '20-Day Gain', 'RSI']
                        
                        st.dataframe(display_df, use_container_width=True, hide_index=True)
                    else:
                        st.info("No high momentum stocks found")
            
            st.markdown("---")
            
            # Strong Uptrend
            if st.button("📈 Strong Uptrend Stocks", key="btn_uptrend", use_container_width=True):
                with st.spinner("Scanning for strong uptrends..."):
                    results = screener.screen_strong_uptrend()
                
                if not results.empty:
                    st.success(f"✅ Found {len(results)} stocks in strong uptrends")
                    
                    st.markdown("""
                    **Strong Uptrend Criteria:**
                    - Price > 20-day MA > 50-day MA > 200-day MA
                    - All moving averages aligned bullishly
                    """)
                    
                    display_df = results[['symbol', 'price', 'sma_20', 'sma_50', 'sma_200', 'strength']].copy()
                    display_df['price'] = display_df['price'].apply(lambda x: f"${x:.2f}")
                    display_df['sma_20'] = display_df['sma_20'].apply(lambda x: f"${x:.2f}")
                    display_df['sma_50'] = display_df['sma_50'].apply(lambda x: f"${x:.2f}")
                    display_df['sma_200'] = display_df['sma_200'].apply(lambda x: f"${x:.2f}")
                    display_df['strength'] = display_df['strength'].apply(lambda x: f"{x:.1f}%")
                    display_df.columns = ['Symbol', 'Price', '20-MA', '50-MA', '200-MA', 'Strength']
                    
                    st.dataframe(display_df, use_container_width=True, hide_index=True)
                else:
                    st.info("No stocks in strong uptrends found")
        
        # ========== TAB 3: TECHNICAL PATTERNS ==========
        with tab3:
            st.subheader("📊 Technical Pattern Screens")
            
            # Volume Spike
            vol_multiplier = st.slider("Volume Spike Threshold", 1.5, 5.0, 2.0, 0.5, 
                                       help="Find stocks with volume X times higher than average")
            
            if st.button("🔊 Find Volume Spikes", key="btn_volume", type="primary"):
                with st.spinner(f"Scanning for {vol_multiplier}x volume spikes..."):
                    results = screener.screen_volume_spike(volume_multiplier=vol_multiplier)
                
                if not results.empty:
                    st.success(f"✅ Found {len(results)} stocks with volume spikes")
                    
                    display_df = results[['symbol', 'price', 'volume', 'volume_ratio', 'signal']].copy()
                    display_df['price'] = display_df['price'].apply(lambda x: f"${x:.2f}")
                    display_df['volume'] = display_df['volume'].apply(lambda x: f"{x:,.0f}")
                    display_df['volume_ratio'] = display_df['volume_ratio'].apply(lambda x: f"{x:.1f}x")
                    display_df.columns = ['Symbol', 'Price', 'Volume', 'Ratio', 'Signal']
                    
                    st.dataframe(display_df, use_container_width=True, hide_index=True)
                    
                    st.info("💡 High volume can indicate strong conviction - check the news for these stocks!")
                else:
                    st.info("No significant volume spikes detected")
        
        # ========== TAB 4: CUSTOM SCREEN ==========
        with tab4:
            st.subheader("🎨 Build Your Custom Screen")
            st.write("Combine multiple criteria to find exactly what you're looking for")
            
            with st.form("custom_screen_form"):
                st.markdown("### Price Range")
                col1, col2 = st.columns(2)
                with col1:
                    price_min = st.number_input("Minimum Price", min_value=0.0, value=10.0, step=1.0)
                with col2:
                    price_max = st.number_input("Maximum Price", min_value=0.0, value=500.0, step=10.0)
                
                st.markdown("### RSI Range")
                col1, col2 = st.columns(2)
                with col1:
                    rsi_min = st.number_input("Minimum RSI", min_value=0, max_value=100, value=30)
                with col2:
                    rsi_max = st.number_input("Maximum RSI", min_value=0, max_value=100, value=70)
                
                st.markdown("### Volume")
                volume_min = st.number_input("Minimum Volume", min_value=0, value=1000000, step=100000,
                                             help="Filter out low-volume stocks")
                
                st.markdown("### Trend Filters")
                above_sma_200 = st.checkbox("Price above 200-day MA", value=False)
                golden_cross = st.checkbox("Golden Cross pattern", value=False)
                
                submit = st.form_submit_button("🔍 Run Custom Screen", type="primary", use_container_width=True)
                
                if submit:
                    criteria = {
                        'price_min': price_min,
                        'price_max': price_max,
                        'rsi_min': rsi_min,
                        'rsi_max': rsi_max,
                        'volume_min': volume_min,
                        'above_sma_200': above_sma_200,
                        'golden_cross': golden_cross
                    }
                    
                    with st.spinner("Running custom screen..."):
                        results = screener.screen_custom(criteria)
                    
                    if not results.empty:
                        st.success(f"✅ Found {len(results)} stocks matching your criteria")
                        
                        display_df = results[['symbol', 'price', 'rsi', 'volume']].copy()
                        display_df['price'] = display_df['price'].apply(lambda x: f"${x:.2f}")
                        display_df['rsi'] = display_df['rsi'].apply(lambda x: f"{x:.1f}")
                        display_df['volume'] = display_df['volume'].apply(lambda x: f"{x:,.0f}")
                        display_df.columns = ['Symbol', 'Price', 'RSI', 'Volume']
                        
                        st.dataframe(display_df, use_container_width=True, hide_index=True)
                        
                        # Download
                        csv = results.to_csv(index=False)
                        st.download_button(
                            "📥 Download Results",
                            csv,
                            "custom_screen_results.csv",
                            "text/csv"
                        )
                    else:
                        st.warning("No stocks match your criteria. Try loosening the filters.")
        
        # ========== TAB 5: SCAN ALL ==========
        with tab5:
            st.subheader("⚡ Run All Screens at Once")
            st.write(f"Scan all {len(scannable_stocks)} stocks across all strategies")
            
            if st.button("🚀 Run Complete Scan", type="primary", use_container_width=True):
                with st.spinner("Running all screening strategies... This may take a minute..."):
                    all_results = screener.run_all_screens()
                
                st.success("✅ Complete scan finished!")
                
                # Display summary
                st.markdown("### 📊 Scan Results Summary")
                
                summary_data = []
                for strategy, results in all_results.items():
                    summary_data.append({
                        'Strategy': strategy.replace('_', ' ').title(),
                        'Stocks Found': len(results) if not results.empty else 0
                    })
                
                summary_df = pd.DataFrame(summary_data)
                st.dataframe(summary_df, use_container_width=True, hide_index=True)
                
                st.markdown("---")
                
                # Show results for each strategy
                for strategy, results in all_results.items():
                    if not results.empty:
                        with st.expander(f"📋 {strategy.replace('_', ' ').title()} ({len(results)} stocks)"):
                            st.dataframe(results.head(10), use_container_width=True, hide_index=True)
# ==================== PAGE: BACKTESTING ====================
elif page == "📊 Backtesting":
    st.markdown('<div class="main-header">📊 Backtesting Engine</div>', unsafe_allow_html=True)
    
    st.write("Test how well past recommendations performed")
    
    days = st.slider("Test recommendations from last N days", 7, 90, 30, key='backtest_days_slider')
    
    if st.button("📊 Run Backtest", type="primary", key='run_backtest_btn'):
        with st.spinner(f"Running backtest on last {days} days..."):
            results = backtester.test_recommendation_performance(days_back=days)
        
        if results:
            stats = results['stats']
            
            st.markdown("---")
            st.markdown(f"### Results for Last {days} Days")
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Total Trades", stats['total_trades'])
            
            with col2:
                st.metric("Win Rate", f"{stats['win_rate']:.1f}%")
            
            with col3:
                st.metric("Avg Return", f"{stats['avg_return']:.2f}%")
            
            with col4:
                st.metric("Buy Avg", f"{stats['avg_buy_return']:.2f}%")
            
            st.markdown("---")
            
            # Show results table
            st.subheader("Individual Trade Results")
            results_df = results['results']
            
            if not results_df.empty:
                # Format for display
                display_df = results_df[['symbol', 'date', 'recommendation', 'entry_price', 'exit_price', 'returns_pct', 'days_held']].copy()
                display_df['entry_price'] = display_df['entry_price'].apply(lambda x: f"${x:.2f}")
                display_df['exit_price'] = display_df['exit_price'].apply(lambda x: f"${x:.2f}")
                display_df['returns_pct'] = display_df['returns_pct'].apply(lambda x: f"{x:+.2f}%")
                
                st.dataframe(display_df, use_container_width=True, hide_index=True)
            
            # Best/Worst with proper styling
            if stats['best_trade'] is not None and stats['worst_trade'] is not None:
                st.markdown("---")
                col1, col2 = st.columns(2)
                
                with col1:
                    best = stats['best_trade']
                    st.markdown(f"""
                    <div style='background-color: #d4edda; border-left: 6px solid #28a745; 
                                padding: 20px; border-radius: 10px;'>
                        <h4 style='color: #155724; margin: 0;'>🏆 Best Trade</h4>
                        <p style='color: #155724; font-size: 1.1rem; margin: 10px 0 5px 0;'>
                            <strong>{best['symbol']}</strong> - {best['recommendation']}
                        </p>
                        <p style='color: #155724; margin: 5px 0;'>
                            Return: <strong>{best['returns_pct']:.2f}%</strong><br>
                            Entry: ${best['entry_price']:.2f} → Exit: ${best['exit_price']:.2f}<br>
                            Held for {best['days_held']} days
                        </p>
                    </div>
                    """, unsafe_allow_html=True)
                
                with col2:
                    worst = stats['worst_trade']
                    st.markdown(f"""
                    <div style='background-color: #f8d7da; border-left: 6px solid #dc3545; 
                                padding: 20px; border-radius: 10px;'>
                        <h4 style='color: #721c24; margin: 0;'>📉 Worst Trade</h4>
                        <p style='color: #721c24; font-size: 1.1rem; margin: 10px 0 5px 0;'>
                            <strong>{worst['symbol']}</strong> - {worst['recommendation']}
                        </p>
                        <p style='color: #721c24; margin: 5px 0;'>
                            Return: <strong>{worst['returns_pct']:.2f}%</strong><br>
                            Entry: ${worst['entry_price']:.2f} → Exit: ${worst['exit_price']:.2f}<br>
                            Held for {worst['days_held']} days
                        </p>
                    </div>
                    """, unsafe_allow_html=True)
        else:
            st.info(f"No recommendations found in the last {days} days. Analyze some stocks first!")

# ==================== PAGE: PORTFOLIO TRACKER ====================
elif page == "💼 Portfolio Tracker":
    st.markdown('<div class="main-header">💼 Portfolio Tracker</div>', unsafe_allow_html=True)
    
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Overview", "➕ Add Transaction", "📜 History", "📊 Fidelity Import"])
    
    with tab1:
        st.subheader("Portfolio Overview")
        
        
        pf_value = portfolio.get_portfolio_value()
        
        if pf_value['current_value'] > 0:
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Total Cost", f"${pf_value['total_cost']:,.2f}")
            
            with col2:
                st.metric("Current Value", f"${pf_value['current_value']:,.2f}")
            
            with col3:
                st.metric("Gain/Loss", f"${pf_value['gain_loss']:+,.2f}")
            
            with col4:
                st.metric("Return %", f"{pf_value['gain_loss_pct']:+.2f}%")
            
            st.markdown("---")
            
            holdings = portfolio.get_holdings()
            
            if not holdings.empty:
                st.subheader("Holdings")
                st.dataframe(holdings, use_container_width=True)
        else:
            st.info("No holdings yet. Add transactions!")

    
    
    with tab2:
        st.subheader("Add Transaction")
        
        col1, col2 = st.columns(2)
        
        with col1:
            txn_type = st.selectbox("Type", ["BUY", "SELL"])
            txn_symbol = st.text_input("Symbol", placeholder="AAPL")
            txn_shares = st.number_input("Shares", min_value=0.01, value=1.0)
        
        with col2:
            txn_price = st.number_input("Price ($)", min_value=0.01, value=100.0)
            txn_commission = st.number_input("Commission ($)", min_value=0.0, value=0.0)
            txn_notes = st.text_input("Notes", placeholder="Optional")
        
        if st.button("➕ Add", type="primary"):
            if txn_symbol:
                portfolio.add_transaction(
                    symbol=txn_symbol,
                    transaction_type=txn_type,
                    shares=txn_shares,
                    price=txn_price,
                    commission=txn_commission,
                    notes=txn_notes
                )
                st.success(f"✅ {txn_type} added!")
                st.rerun()
    
    with tab3:
        st.subheader("History")
        
        history = portfolio.get_transaction_history()
        
        if not history.empty:
            st.dataframe(history, use_container_width=True)
        else:
            st.info("No transactions")
    
    with tab4:
        st.subheader("📊 Import from Fidelity")
        
        st.markdown("""
        ### How to export from Fidelity:
        1. Log in to Fidelity.com
        2. Go to **Accounts & Trade** → **Portfolio**
        3. Click **Download** or **Export Positions**
        4. Save as CSV
        5. Upload below
        """)
        
        st.markdown("---")
        
        from portfolio.fidelity_importer import FidelityImporter
        
        if 'fidelity_importer' not in st.session_state:
            st.session_state.fidelity_importer = FidelityImporter(portfolio)
        
        fid_importer = st.session_state.fidelity_importer
        
        uploaded_file = st.file_uploader("Upload Fidelity CSV", type=['csv'], key='fidelity_uploader')
        
        if uploaded_file is not None:
            # Read the file
            try:
                import tempfile
                import os
                
                # Create temp file
                with tempfile.NamedTemporaryFile(delete=False, suffix='.csv', mode='wb') as tmp_file:
                    tmp_file.write(uploaded_file.getvalue())
                    tmp_path = tmp_file.name
                
                st.success("✅ File uploaded successfully!")
                
                # Store path in session state
                st.session_state.fidelity_csv_path = tmp_path
                
                st.markdown("---")
                
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    if st.button("👀 Preview Positions", key='preview_btn'):
                        try:
                            st.info("📊 Parsing CSV... (check terminal for details)")
                            positions = fid_importer.parse_fidelity_csv(st.session_state.fidelity_csv_path)
                            
                            if positions is not None:
                                if not positions.empty:
                                    st.success(f"✅ Found {len(positions)} positions")
                                    st.dataframe(positions, use_container_width=True)
                                else:
                                    st.warning("⚠️ CSV parsed but no valid positions found")
                                    st.info("Check the terminal output for details on why positions were skipped")
                            else:
                                st.error("❌ Failed to parse CSV")
                                st.info("Check the terminal output for error details")
                        except Exception as e:
                            st.error(f"❌ Error: {str(e)}")
                            import traceback
                            st.code(traceback.format_exc())
                
                with col2:
                    if st.button("🔄 Compare with Current", key='compare_btn'):
                        try:
                            comparison = fid_importer.compare_with_current(st.session_state.fidelity_csv_path)
                            
                            if comparison is not None and not comparison.empty:
                                st.success("✅ Comparison complete")
                                st.dataframe(comparison, use_container_width=True)
                            else:
                                st.info("No comparison data available")
                        except Exception as e:
                            st.error(f"Error comparing: {str(e)}")
                
                with col3:
                    if st.button("📥 Import All", type="primary", key='import_btn'):
                        try:
                            with st.spinner("Importing positions..."):
                                success = fid_importer.import_to_portfolio(st.session_state.fidelity_csv_path, clear_existing=False)
                            
                            if success:
                                st.success("✅ Import complete!")
                                st.balloons()
                                
                                # Clean up temp file
                                try:
                                    os.unlink(st.session_state.fidelity_csv_path)
                                except:
                                    pass
                                
                                # Wait a moment then rerun
                                import time
                                time.sleep(2)
                                st.rerun()
                            else:
                                st.error("❌ Import failed. Check the console for errors.")
                        except Exception as e:
                            st.error(f"Error importing: {str(e)}")
                
                st.markdown("---")
                
                if st.button("🔄 Smart Sync (Update Differences Only)", key='sync_btn'):
                    try:
                        with st.spinner("Syncing with Fidelity..."):
                            success = fid_importer.sync_with_fidelity(st.session_state.fidelity_csv_path)
                        
                        if success:
                            st.success("✅ Sync complete!")
                            
                            # Clean up
                            try:
                                os.unlink(st.session_state.fidelity_csv_path)
                            except:
                                pass
                            
                            import time
                            time.sleep(2)
                            st.rerun()
                        else:
                            st.error("❌ Sync failed")
                    except Exception as e:
                        st.error(f"Error syncing: {str(e)}")
                
            except Exception as e:
                st.error(f"❌ Error reading file: {str(e)}")
        else:
            st.info("👆 Upload a CSV file to get started")
            
# ==================== PAGE: ALERTS ====================
elif page == "🔔 Alerts":
    st.markdown('<div class="main-header">🔔 Alerts</div>', unsafe_allow_html=True)
    
    st.subheader("Create Price Alert")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        alert_symbol = st.text_input("Symbol", placeholder="AAPL")
    
    with col2:
        alert_price = st.number_input("Target Price", min_value=0.01, value=100.0)
    
    with col3:
        alert_type = st.selectbox("When", ["Above", "Below"])
    
    if st.button("🔔 Create"):
        if alert_symbol:
            alerts.add_price_alert(
                symbol=alert_symbol.upper(),
                target_price=alert_price,
                alert_type=alert_type.lower()
            )
            st.success("Alert created!")
    
    st.markdown("---")
    
    if st.button("🔍 Check Alerts"):
        with st.spinner("Checking..."):
            triggered = alerts.check_all_alerts()
        
        total = len(triggered['price_alerts']) + len(triggered['rsi_alerts'])
        st.info(f"Total alerts: {total}")

    

# ==================== PAGE: NEWS ====================
elif page == "📰 News":
    st.markdown('<div class="main-header">📰 News</div>', unsafe_allow_html=True)
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        news_symbol = st.text_input("Stock Symbol", placeholder="AAPL")
    
    with col2:
        st.write("")
        if st.button("🔍 Fetch"):
            if news_symbol:
                with st.spinner("Fetching..."):
                    articles = news_scraper.fetch_stock_news(news_symbol.upper(), days=7)
                    news_scraper.save_news(articles)
                st.success(f"Found {len(articles)} articles!")
                st.rerun()
    
    if news_symbol:
        recent_news = db.get_recent_news(symbol=news_symbol.upper(), days=30, limit=20)
        
        if not recent_news.empty:
            for _, article in recent_news.iterrows():
                with st.expander(f"📰 {article['title']} - {article['source']}"):
                    st.write(article['description'])
                    st.write(f"[Read more]({article['url']})")
                    st.caption(f"{article['published_at']}")

# ==================== PAGE: REPORTS ====================
elif page == "📋 Reports":
    st.markdown('<div class="main-header">📋 Analysis Reports</div>', unsafe_allow_html=True)
    
    st.write("Generate comprehensive analysis reports for your portfolio")
    
    tab1, tab2, tab3, tab4 = st.tabs(["📅 Daily", "📆 Weekly", "📊 Monthly", "📜 Report History"])
    
    with tab1:
        st.subheader("Daily Report")
        st.write("Comprehensive daily analysis of your watchlist and recommendations")
        
        if st.button("📝 Generate Daily Report", type="primary", key='gen_daily'):
            with st.spinner("Generating daily report..."):
                try:
                    report = reporter.generate_daily_report()
                    st.success("✅ Daily report generated!")
                    st.text_area("Report Content", report, height=500, key='daily_report_text')
                    
                    # Option to download
                    st.download_button(
                        label="📥 Download Report",
                        data=report,
                        file_name=f"daily_report_{datetime.now().strftime('%Y-%m-%d')}.txt",
                        mime="text/plain"
                    )
                except Exception as e:
                    st.error(f"Error generating report: {str(e)}")
                    import traceback
                    st.code(traceback.format_exc())
        
        # Show last generated daily report
        st.markdown("---")
        st.subheader("Last Generated Daily Report")
        last_daily = db.get_latest_report('DAILY')
        
        if not last_daily.empty:
            st.caption(f"Generated: {last_daily.iloc[0]['created_at']}")
            st.text_area("", last_daily.iloc[0]['content'], height=400, key='last_daily_display')
        else:
            st.info("No daily reports generated yet. Click the button above to generate one!")
    
    with tab2:
        st.subheader("Weekly Report")
        st.write("7-day summary of market activity and recommendations")
        
        if st.button("📝 Generate Weekly Report", type="primary", key='gen_weekly'):
            with st.spinner("Generating weekly report..."):
                try:
                    report = reporter.generate_weekly_report()
                    st.success("✅ Weekly report generated!")
                    st.text_area("Report Content", report, height=500, key='weekly_report_text')
                    
                    st.download_button(
                        label="📥 Download Report",
                        data=report,
                        file_name=f"weekly_report_{datetime.now().strftime('%Y-%m-%d')}.txt",
                        mime="text/plain"
                    )
                except Exception as e:
                    st.error(f"Error generating report: {str(e)}")
                    import traceback
                    st.code(traceback.format_exc())
        
        st.markdown("---")
        st.subheader("Last Generated Weekly Report")
        last_weekly = db.get_latest_report('WEEKLY')
        
        if not last_weekly.empty:
            st.caption(f"Generated: {last_weekly.iloc[0]['created_at']}")
            st.text_area("", last_weekly.iloc[0]['content'], height=400, key='last_weekly_display')
        else:
            st.info("No weekly reports generated yet.")
    
    with tab3:
        st.subheader("Monthly Report")
        st.write("30-day comprehensive analysis with top opportunities")
        
        if st.button("📝 Generate Monthly Report", type="primary", key='gen_monthly'):
            with st.spinner("Generating monthly report..."):
                try:
                    report = reporter.generate_monthly_report()
                    st.success("✅ Monthly report generated!")
                    st.text_area("Report Content", report, height=600, key='monthly_report_text')
                    
                    st.download_button(
                        label="📥 Download Report",
                        data=report,
                        file_name=f"monthly_report_{datetime.now().strftime('%Y-%m-%d')}.txt",
                        mime="text/plain"
                    )
                except Exception as e:
                    st.error(f"Error generating report: {str(e)}")
                    import traceback
                    st.code(traceback.format_exc())
        
        st.markdown("---")
        st.subheader("Last Generated Monthly Report")
        last_monthly = db.get_latest_report('MONTHLY')
        
        if not last_monthly.empty:
            st.caption(f"Generated: {last_monthly.iloc[0]['created_at']}")
            st.text_area("", last_monthly.iloc[0]['content'], height=500, key='last_monthly_display')
        else:
            st.info("No monthly reports generated yet.")
    
    with tab4:
        st.subheader("📜 Report History")
        
        # Get all reports
        conn = db.get_connection()
        all_reports = pd.read_sql_query(
            "SELECT report_type, date, created_at FROM reports ORDER BY created_at DESC LIMIT 20",
            conn
        )
        conn.close()
        
        if not all_reports.empty:
            st.dataframe(all_reports, use_container_width=True, hide_index=True)
        else:
            st.info("No reports in history yet. Generate some reports!")

# ==================== PAGE: ADVANCED CHARTS ====================
elif page == "📈 Advanced Charts":
    st.markdown('<div class="main-header">📈 Advanced Charts</div>', unsafe_allow_html=True)
    
    watchlist = db.get_watchlist()
    
    if not watchlist.empty:
        selected = st.multiselect(
            "Select stocks",
            watchlist['symbol'].tolist(),
            default=watchlist['symbol'].tolist()[:min(5, len(watchlist))]
        )
        
        if selected and st.button("📊 Generate Correlation Heatmap"):
            with st.spinner("Creating..."):
                fig = visualizer.create_correlation_heatmap(selected, days=90)
            
            if fig:
                st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Add stocks to watchlist first")

# ==================== PAGE: SCHEDULER ====================
elif page == "⏰ Scheduler":
    st.markdown('<div class="main-header">⏰ Scheduler</div>', unsafe_allow_html=True)
    
    st.markdown("""
    ### Run Tasks Manually
    
    Click buttons below to run tasks immediately:
    """)
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🔄 Update Data"):
            scheduler.run_now('update_data')
            st.success("Done!")
        
        if st.button("📊 Analyze"):
            scheduler.run_now('analyze')
            st.success("Done!")
    
    with col2:
        if st.button("📋 Daily Report"):
            scheduler.run_now('daily_report')
            st.success("Done!")
        
        if st.button("🗑️ Cleanup"):
            scheduler.run_now('cleanup')
            st.success("Done!")

# ==================== PAGE: SETTINGS ====================
elif page == "⚙️ Settings":
    st.markdown('<div class="main-header">⚙️ Settings</div>', unsafe_allow_html=True)
    
    # ========== AI SETTINGS ==========
    st.subheader("🤖 AI Analysis Settings")
    
    import config
    
    # Show current mode
    ai_enabled = hasattr(config, 'USE_AI_ANALYSIS') and config.USE_AI_ANALYSIS
    has_api_key = hasattr(config, 'CLAUDE_API_KEY') and config.CLAUDE_API_KEY and len(config.CLAUDE_API_KEY) > 10
    
    if ai_enabled:
        st.success("✅ **Current Mode:** AI-Powered Analysis")
    else:
        st.info("📊 **Current Mode:** Traditional Technical Analysis")
    
    st.markdown("---")
    
    # API Key Status
    col1, col2 = st.columns(2)
    
    with col1:
        if has_api_key:
            masked_key = config.CLAUDE_API_KEY[:8] + "..." + config.CLAUDE_API_KEY[-4:]
            st.success(f"🔑 **API Key:** {masked_key}")
        else:
            st.warning("⚠️ **No API Key Configured**")
            st.info("Get your free API key at: https://console.anthropic.com/")
    
    with col2:
        if ai_enabled and has_api_key:
            st.metric("Status", "ACTIVE", "🟢")
        elif has_api_key:
            st.metric("Status", "READY", "🟡")
        else:
            st.metric("Status", "INACTIVE", "🔴")
    
    st.markdown("---")
    
    # Toggle buttons
    st.subheader("⚙️ Toggle Analysis Mode")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🤖 Enable AI Analysis", type="primary", disabled=not has_api_key):
            # Modify config at runtime
            import importlib
            config.USE_AI_ANALYSIS = True
            st.success("✅ AI Analysis ENABLED!")
            st.balloons()
            st.rerun()
        
        if not has_api_key:
            st.caption("⚠️ Add API key to config.py first")
    
    with col2:
        if st.button("📊 Use Technical Analysis"):
            config.USE_AI_ANALYSIS = False
            st.info("📊 Switched to Technical Analysis")
            st.rerun()
    
    st.markdown("---")
    
    # Feature comparison
    st.subheader("📊 Feature Comparison")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        ### 🤖 AI-Powered Analysis
        
       ### 🤖 AI-Powered Analysis

        **Advantages:**
        - 🧠 **Intelligent reasoning** - Understands context
        - 📰 **News integration** - Analyzes recent catalysts (last 7 days)
        - 🎯 **Unique scores** - Every stock analyzed differently
        - 📝 **Detailed explanations** - Full reasoning provided
        - ⚠️ **Risk assessment** - Identifies specific risks
        - ⏰ **Time horizons** - Recommends when to expect results:
            - ⚡ SHORT-TERM (3-10 days): Quick plays
            - 📈 SWING (2-8 weeks): Catalyst trades  
            - 🎯 LONG-TERM (6-18 months): Breakthrough opportunities
        - 🔥 **Catalyst detection** - Finds recent breakthrough news
        - 💯 **Confidence levels** - HIGH/MEDIUM/LOW conviction ratings

        **What it analyzes:**
        - Current price and TODAY's conditions
        - Technical indicators from recent history
        - News from the last 7 days
        - Trend strength and momentum
        
        **Requirements:**
        - Claude API key ($5 free credit)
        - ~$0.002 per analysis (~500 analyses per dollar)
        """)
    
    with col2:
        st.markdown("""
        ### 📊 Technical Analysis
        
        **Advantages:**
        - ⚡ **Fast** - Instant results
        - 🆓 **Free** - No API costs
        - 📡 **Offline** - Works without internet
        - ✅ **Reliable** - Proven algorithms
        - 📈 **14 indicators** - RSI, MACD, Moving Averages, etc.
        
        **Limitations:**
        - Same scoring logic for all stocks
        - No news/catalyst consideration  
        - No detailed reasoning
        - Limited context understanding
        """)
    
    st.markdown("---")
    
    # How to get API key
    with st.expander("🔑 How to Get Claude API Key (Free $5 Credit)"):
        st.markdown("""
        ### Step-by-Step Guide:
        
        1. **Go to:** https://console.anthropic.com/
        2. **Sign up** for a free account (email + password)
        3. **Verify your email**
        4. **Go to "API Keys"** in the left menu
        5. **Click "Create Key"**
        6. **Copy the key** (starts with `sk-ant-...`)
        7. **Open `config.py`** in your project
        8. **Find the line:** `CLAUDE_API_KEY = ""`
        9. **Paste your key:** `CLAUDE_API_KEY = "sk-ant-your-key-here"`
        10. **Save the file**
        11. **Restart the dashboard**
        12. **Come back here and enable AI!**
        
        ### 💰 Pricing:
        - **Free tier:** $5 credit (enough for ~2,500 analyses)
        - **After free tier:** $3 per 1,000 analyses (0.3¢ each)
        - **Average user:** $5-10/month for heavy usage
        
        ### ⚡ Performance:
        - Analysis takes 5-10 seconds (AI is thinking)
        - Results are unique every time
        - Much more detailed than technical analysis
        """)
    
    st.markdown("---")
    
    # ========== DATABASE SETTINGS ==========
    st.subheader("🗄️ Database Management")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("🗑️ Clear Old Data"):
            db.clear_old_data(days=365)
            st.success("✅ Cleared data older than 365 days")
    
    with col2:
        if st.button("📊 View Statistics"):
            stats = db.get_database_stats()
            st.json(stats)
    
    with col3:
        if st.button("🔄 Refresh"):
            st.rerun()
    
    st.markdown("---")
    
    # System info
    st.subheader("ℹ️ System Information")
    
    stats = db.get_database_stats()
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Stocks", stats.get('unique_symbols', 0))
    
    with col2:
        st.metric("Price Records", f"{stats.get('stock_prices', 0):,}")
    
    with col3:
        st.metric("Recommendations", stats.get('recommendations', 0))
    
    with col4:
        st.metric("Watchlist Size", stats.get('watchlist', 0))
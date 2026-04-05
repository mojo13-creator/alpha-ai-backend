# CLAUDE.md — Alpha AI Backend

This file is the persistent context for all Claude Code sessions on this repo.
Read this file at the start of every session before touching any code.

---

## Project Identity

**Alpha AI** is a real, revenue-intended AI stock analysis SaaS.
- Owner: Connor (Fidelity account XXXXX4416)
- Status: Personal use before public launch
- Pricing at launch: $29/month Pro, $79/month Elite
- This is NOT a tutorial or demo project. Every decision should be production-quality.

---

## Live URLs

| Service | URL |
|---|---|
| Frontend (Vercel) | https://alpha-ai-app-pied.vercel.app |
| Backend (Railway) | https://web-production-27e7e9.up.railway.app |
| GitHub (frontend) | https://github.com/mojo13-creator/alpha-ai-app |
| GitHub (backend) | https://github.com/mojo13-creator/alpha-ai-backend |

---

## Local File Paths

| Repo | Path |
|---|---|
| Backend | ~/Desktop/stock-analyzer |
| Frontend | ~/Desktop/alpha-ai-app |
| Landing page | ~/Desktop/alpha-ai-landing |
| Python venv | ~/Desktop/stock-analyzer/venv |

---

## Tech Stack

### Backend
- Python 3.13 (Railway), 3.14 (local)
- FastAPI + Uvicorn
- SQLite (local) / PostgreSQL (Railway) — db_manager handles both automatically
- python-dotenv for env var loading
- slowapi for rate limiting
- anthropic SDK (Claude Sonnet `claude-sonnet-4-20250514`)
- yfinance, newsapi-python, finvizfinance, praw

### Frontend
- Next.js 14 (App Router), TypeScript
- Tailwind CSS
- Framer Motion (animations)
- shadcn/ui (component library)
- Recharts (charts)
- Clerk (auth — dev keys, needs production keys before launch)

### AI / Data
- Claude Sonnet (`claude-sonnet-4-20250514`) — primary AI engine
- Gemini API — planned (Feature 5, key not yet provided)
- Perplexity API — planned (Feature 6, key not yet provided)
- NewsAPI, Reddit public JSON, Finviz

---

## File Structure — Backend

```
stock-analyzer/
├── api.py                          # FastAPI app — all endpoints live here
├── config.py                       # All settings; keys loaded from .env via os.environ
├── .env                            # Local secrets — NEVER commit
├── .env.example                    # Safe template — committed
├── requirements.txt                # Python dependencies
├── SECURITY.md                     # Security rules and env var reference
├── CLAUDE.md                       # This file
│
├── analysis/
│   ├── ai_analyzer.py              # Claude AI stock analysis engine
│   ├── ai.analyzer.py              # Legacy/duplicate — do not use for new work
│   ├── hybrid_recommender.py       # Combines technical + AI signals
│   ├── technical_analysis.py       # RSI, MACD, Bollinger Bands, SMA, etc.
│   ├── recommendation_engine.py
│   ├── stock_screener.py
│   ├── discovery_engine.py
│   └── backtester.py
│
├── data_collection/
│   ├── stock_data.py               # yfinance wrapper (StockDataCollector)
│   ├── news_scraper.py             # NewsAPI wrapper (NewsScraper)
│   ├── reddit_scraper.py           # Reddit scraper (RedditScraper class)
│   └── finviz_scraper.py           # Finviz screener (FinvizScraper)
│
├── database/
│   └── db_manager.py               # SQLite/PostgreSQL abstraction (DatabaseManager)
│
├── portfolio/
│   ├── fidelity_importer.py
│   └── portfolio_tracker.py
│
├── reports/
│   └── report_generator.py         # ReportGenerator class
│
├── utils/
│   ├── alerts.py
│   ├── scheduler.py
│   └── visualizations.py
│
└── ui/
    └── dashboard.py                # Legacy Streamlit UI — not used in production
```

---

## Critical Import Rules — NEVER Change These

```python
from data_collection.stock_data import StockDataCollector
from analysis.technical_analysis import TechnicalAnalyzer
from data_collection.news_scraper import NewsScraper
from data_collection.reddit_scraper import RedditScraper       # class, NOT fetch_reddit_sentiment
from analysis.hybrid_recommender import HybridRecommender
from data_collection.finviz_scraper import FinvizScraper
from reports.report_generator import ReportGenerator
```

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| POST | /api/analyze | Full AI stock analysis |
| GET | /api/dashboard | Dashboard data |
| GET/POST/DELETE | /api/portfolio | Portfolio CRUD |
| GET | /api/portfolio/history | Portfolio value history |
| GET/POST/DELETE | /api/watchlist | Watchlist CRUD |
| GET | /api/alerts | Technical alerts |
| GET | /api/reports/daily | Daily AI report |
| GET | /api/reports/weekly | Weekly AI report |
| GET | /api/reports/monthly | Monthly AI report |
| GET | /api/finviz/screener | Finviz screener signals |
| GET | /api/finviz/strong-buys | Finviz strong buys |
| GET | /api/news/feed | AI-analyzed news feed |
| GET/POST | /api/portfolio/pending | Fidelity import queue |
| POST | /api/portfolio/pending/confirm | Confirm imported trade |
| DELETE | /api/portfolio/pending/{id} | Dismiss pending import |

---

## Environment Variables

### .env location: ~/Desktop/stock-analyzer/.env (NEVER commit this file)

| Variable | Description | Required |
|---|---|---|
| `CLAUDE_API_KEY` | Anthropic Claude API key | Yes |
| `NEWS_API_KEY` | NewsAPI key | Yes |
| `FIDELITY_USERNAME` | Fidelity username | Future |
| `FIDELITY_PASSWORD` | Fidelity password | Future |
| `GEMINI_API_KEY` | Google Gemini key | Future (Feature 5) |
| `PERPLEXITY_API_KEY` | Perplexity key | Future (Feature 6) |

### How keys are loaded — always use this pattern:
```python
from dotenv import load_dotenv
import os
load_dotenv()
api_key = os.environ.get("KEY_NAME")
if not api_key:
    raise ValueError("KEY_NAME not set — add it to your .env file")
```

### Railway (production) env vars — set in Railway dashboard:
- `CLAUDE_API_KEY`
- `NEWS_API_KEY`
- `DATABASE_URL` (set automatically by Railway PostgreSQL plugin)

---

## Security Rules — Permanent, Apply Every Session

1. **NEVER hardcode any API key, token, password, or secret in any file.**
2. **NEVER commit `.env` or `.env.*` files.** The `.gitignore` blocks `.env*` (except `.env.example`).
3. **Before every `git add` or commit**, scan for exposed secrets:
   ```bash
   grep -rn "sk-ant-\|sk_test_\|pk_test_" --include="*.py" --exclude-dir=venv .
   ```
4. **All new API integrations** (Gemini, Perplexity, Fidelity) must load keys from env vars only.
5. **Never log API keys** in print statements, error messages, or tracebacks.
6. **Never include API keys in comments, prompts, or documentation.**
7. **All ticker/symbol inputs** must be validated through `validate_ticker()` in `api.py` before use.
8. **CORS** is restricted to `https://alpha-ai-app-pied.vercel.app` and `localhost:3000` only.
9. **Rate limits**: `/api/analyze` → 20/min, `/api/reports/*` → 5/min, `/api/news/feed` → 15/min, default → 60/min.

---

## Python Coding Rules

- **NEVER use `if df:`** on pandas DataFrames — use `if df is None or df.empty:`
- **ALWAYS use `safe_float()`** for float conversions from technical indicators
- **NEVER use `sed`** for file edits — use the Edit tool or Python
- **NEVER use heredoc (`cat >`)** for writing long files — use the Write tool or Python
- **pip installs outside venv**: use `--break-system-packages`

### safe_float definition (in api.py):
```python
def safe_float(val, default=0.0):
    try:
        v = float(val)
        return default if math.isnan(v) or math.isinf(v) else v
    except:
        return default
```

---

## How to Run Locally

```bash
# Kill any existing backend
lsof -ti:8000 | xargs kill -9

# Start backend
cd ~/Desktop/stock-analyzer
source venv/bin/activate
uvicorn api:app --reload --port 8000
```

---

## Deployment Process

### Backend → Railway
```bash
cd ~/Desktop/stock-analyzer
git add <specific files>          # Never use git add -A or git add .
git commit -m "message"
git push origin main              # Railway auto-deploys on push
```

### Frontend → Vercel
```bash
cd ~/Desktop/alpha-ai-app
git add <specific files>
git commit -m "message"
git push origin main              # Vercel auto-deploys on push
```

### Before every push — run this checklist:
```bash
# 1. No .env files staged
git status | grep ".env"

# 2. No hardcoded secrets
grep -rn "sk-ant-\|sk_test_" --include="*.py" --exclude-dir=venv .

# 3. Syntax check
python3 -c "import ast; ast.parse(open('api.py').read()); print('OK')"
```

### Git identity:
```bash
git config --global user.name "mojo13-creator"
```

---

## Build Roadmap

Work through these in order unless Connor instructs otherwise.

| # | Feature | Status |
|---|---|---|
| 1 | News Intelligence Tab (`/news`) | ✅ Complete |
| 2 | Rebuilt Daily Reports (`/reports`) | ⬜ Next |
| 3 | Portfolio Tiers + Daily Scoring | ⬜ Pending |
| 4 | Paper Trading Tab (`/paper-trading`) | ⬜ Pending |
| 5 | Gemini API Integration | ⬜ Waiting on key |
| 6 | Perplexity API Integration | ⬜ Waiting on key |

### Stop and ask Connor before continuing when:
- A database migration is required
- A new paid API needs a key that hasn't been provided
- Two valid implementation paths exist and the choice affects the architecture
- An error cannot be resolved in 2 attempts
- A feature is complete and ready for review
- Any file deletion is required

---

## Checkpoint Format

After each major step output: `✅ [what was completed and which files were changed]`
After each full feature: output a summary of every file added or modified.

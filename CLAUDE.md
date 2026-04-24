# CLAUDE.md — Alpha AI Backend

---

## Project Identity

**Alpha AI** — revenue-intended AI stock analysis SaaS. NOT a tutorial.
- Owner: Connor | Fidelity XXXXX4416
- Pricing: $29/mo Pro, $79/mo Elite
- Every decision should be production-quality.

## URLs & Paths

| | URL / Path |
|---|---|
| Frontend | https://alpha-ai-app-pied.vercel.app |
| Backend | https://web-production-27e7e9.up.railway.app |
| GitHub FE | github.com/mojo13-creator/alpha-ai-app |
| GitHub BE | github.com/mojo13-creator/alpha-ai-backend |
| Local BE | ~/Desktop/stock-analyzer |
| Local FE | ~/Desktop/alpha-ai-app |
| Venv | ~/Desktop/stock-analyzer/venv |

## Tech Stack

**Backend:** Python 3.13 (Railway) / 3.14 (local), FastAPI, SQLite (local) / PostgreSQL (Railway), slowapi, anthropic SDK, yfinance, newsapi.ai (Event Registry, via requests), finvizfinance, praw

**Frontend:** Next.js 14 (App Router), TypeScript, Tailwind, Framer Motion, shadcn/ui, Recharts, Clerk auth (dev keys)

**AI Models:** Claude Sonnet (`claude-sonnet-4-20250514`), Gemini (`gemini-2.5-flash`), GPT-4o — 3-model consensus. Perplexity planned (no key yet).

---

## File Structure

```
analysis/
  ai_analyzer.py          # Claude AI engine
  gemini_analyzer.py       # Gemini engine
  chatgpt_analyzer.py      # GPT-4o engine
  composite_scorer.py      # Master scorer: sub-scores + 3-model AI consensus
  technical_scorer.py      # Quant technical score (0-100)
  fundamental_scorer.py    # Quant fundamental score (0-100)
  sentiment_scorer.py      # Quant sentiment score (0-100)
  horizon_screener.py      # 3-horizon screener (short/mid/long) — NO AI calls
  technical_analysis.py    # RSI, MACD, Bollinger, SMA, indicators
  hybrid_recommender.py    # Technical + AI signal combiner
  stock_screener.py        # Preset screening strategies
  discovery_engine.py      # Hidden gem / catalyst discovery
  ai.analyzer.py           # LEGACY — do not use

data_collection/
  stock_data.py            # yfinance wrapper (StockDataCollector)
  news_scraper.py          # NewsAPI (NewsScraper)
  reddit_scraper.py        # Reddit (RedditScraper class)
  finviz_scraper.py        # Finviz (FinvizScraper)
  berkeley/                # Institutional data (CapIQ, WRDS, IBISWorld, Orbis, Statista)

reports/
  report_generator.py      # Personalized portfolio reports
  report_scheduler.py      # Daily report orchestration
  daily_screener.py        # 3-stage pipeline: gather → filter → analyze

database/db_manager.py     # SQLite/PostgreSQL abstraction
portfolio/                 # fidelity_importer.py, portfolio_tracker.py
trading/paper_trader.py    # Paper trading engine
```

## Critical Imports — NEVER Change

```python
from data_collection.stock_data import StockDataCollector
from analysis.technical_analysis import TechnicalAnalyzer
from data_collection.news_scraper import NewsScraper
from data_collection.reddit_scraper import RedditScraper
from analysis.hybrid_recommender import HybridRecommender
from data_collection.finviz_scraper import FinvizScraper
from reports.report_generator import ReportGenerator
```

## API Endpoints

| Method | Path | Description |
|---|---|---|
| POST | /api/analyze | Full AI analysis (3-model consensus) |
| GET | /api/dashboard | Dashboard data |
| GET/POST/DELETE | /api/portfolio | Portfolio CRUD |
| GET | /api/portfolio/history | Portfolio value history |
| POST | /api/portfolio/from-report | Add screener pick to portfolio |
| GET/POST/DELETE | /api/watchlist | Watchlist CRUD |
| GET | /api/alerts | Technical alerts |
| GET | /api/market/summary | Index prices + sector outlook (no AI) |
| GET | /api/screener/all | 3-horizon screen + AI top 3 (cached 60 min) |
| GET | /api/screener/short-term | Momentum picks, 1-2 days (no AI) |
| GET | /api/screener/mid-term | Swing trades, 2-8 weeks (no AI) |
| GET | /api/screener/long-term | Core holdings, 3+ months (no AI) |
| GET | /api/analysis/{ticker}/history | Last 30 analyses for trend chart |
| GET | /api/reports/daily | Legacy daily AI report |
| GET | /api/reports/weekly | Weekly report |
| GET | /api/reports/monthly | Monthly report |
| GET | /api/finviz/screener | Finviz signals |
| GET | /api/news/feed | AI-analyzed news feed |
| GET/POST | /api/portfolio/pending | Fidelity import queue |

---

## Security — ALWAYS Enforce

1. **NEVER hardcode secrets.** All keys from env vars only.
2. **NEVER commit `.env`.** `.gitignore` blocks `.env*` (except `.env.example`).
3. **Before every commit:** `grep -rn "sk-ant-\|sk_test_\|pk_test_" --include="*.py" --exclude-dir=venv .`
4. **Never log keys** in print/error/traceback.
5. **Validate all ticker inputs** via `validate_ticker()` in `api.py`.
6. **CORS:** `alpha-ai-app-pied.vercel.app` + `localhost:3000` only.
7. **Rate limits:** `/api/analyze` 20/min, `/api/reports/*` 5/min, `/api/news/feed` 15/min, default 60/min.

## Env Vars

`.env` at `~/Desktop/stock-analyzer/.env` — load with `os.environ.get()` after `load_dotenv()`.

| Variable | Required |
|---|---|
| `CLAUDE_API_KEY` | Yes |
| `NEWS_API_KEY` | Yes |
| `GEMINI_API_KEY` | Yes |
| `OPENAI_API_KEY` | Yes |
| `PERPLEXITY_API_KEY` | Future |

Railway also has `DATABASE_URL` (auto-set by PostgreSQL plugin).

---

## Coding Rules

- **NEVER `if df:`** on DataFrames — use `if df is None or df.empty:`
- **ALWAYS `safe_float()`** for float conversions from indicators
- **NEVER use `sed`** — use Edit tool or Python
- **NEVER `git add -A` or `git add .`** — always add specific files
- **pip outside venv:** `--break-system-packages`

## Run Locally

```bash
lsof -ti:8000 | xargs kill -9
cd ~/Desktop/stock-analyzer && source venv/bin/activate
uvicorn api:app --reload --port 8000
```

## Deploy

Backend: `git push origin main` → Railway auto-deploys
Frontend: `git push origin main` (from ~/Desktop/alpha-ai-app) → Vercel auto-deploys

Pre-push: check no `.env` staged, no hardcoded secrets, `python3 -c "import ast; ast.parse(open('api.py').read())"`.

Git user: `mojo13-creator`

---

## Build Roadmap

| # | Feature | Status |
|---|---|---|
| 1 | News Intelligence (`/news`) | Done |
| 2 | Unified Reports + Screener (`/reports`) | Done — 3-horizon + AI top 3 |
| 3 | Portfolio Tiers + Daily Scoring | Next |
| 4 | Paper Trading (`/paper-trading`) | Pending |
| 5 | Gemini Integration | Done — 2nd AI model in composite scorer |
| 6 | Perplexity Integration | Waiting on key |

### Ask Connor before:
- Database migrations
- New paid API keys not yet provided
- Architectural forks with multiple valid paths
- After 2 failed attempts at an error
- When a feature is complete and ready for review
- Any file deletion

---

## Session End Protocol

Before ending any session or when context is getting long:
- Update this file if file structure, endpoints, or roadmap changed
- Save non-obvious decisions or user preferences to memory
- Summarize what was done and what's next

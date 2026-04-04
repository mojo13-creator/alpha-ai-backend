# Security Guide — Alpha AI Backend

## Required Environment Variables

Copy `.env.example` to `.env` and fill in all values before running locally.

| Variable | Description | Required |
|---|---|---|
| `CLAUDE_API_KEY` | Anthropic Claude API key (`sk-ant-...`) | Yes |
| `NEWS_API_KEY` | NewsAPI key | Yes |
| `FIDELITY_USERNAME` | Fidelity brokerage username | No (future) |
| `FIDELITY_PASSWORD` | Fidelity brokerage password | No (future) |
| `GEMINI_API_KEY` | Google Gemini API key | No (future) |
| `PERPLEXITY_API_KEY` | Perplexity API key | No (future) |

## Local Setup

```bash
cd ~/Desktop/stock-analyzer
cp .env.example .env   # then fill in your keys
source venv/bin/activate
pip install -r requirements.txt
uvicorn api:app --reload --port 8000
```

## Railway (Production) Environment Variables

Set these in the Railway dashboard under your service → Variables:

- [ ] `CLAUDE_API_KEY`
- [ ] `NEWS_API_KEY`

## Rules — Never Break These

1. **Never hardcode any key, token, or password in any file.**
2. **Never commit `.env` or `.env.*` to git.** The `.gitignore` blocks this.
3. **Never log API keys** in print statements, error messages, or debug output.
4. **All new API integrations** must load keys via `os.environ.get("KEY_NAME")`.
5. **Brokerage credentials** must never be stored in plaintext beyond `.env`.

## Pre-Push Checklist

Before every `git push`, verify:

```bash
# 1. Check no .env files are staged
git status | grep ".env"

# 2. Scan for accidental key exposure
grep -rn "sk-ant-\|sk_test_\|pk_test_" --include="*.py" --exclude-dir=venv .

# 3. Confirm .gitignore is committed
git ls-files .gitignore
```

## Keys That Need Rotation After Any Accidental Commit

If a key is ever committed to git history, rotate it immediately:
- Claude: https://console.anthropic.com → API Keys
- NewsAPI: https://newsapi.org/account
- Clerk: https://dashboard.clerk.com → API Keys

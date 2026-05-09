# analysis/earnings_sentiment.py
"""
Score the most recent earnings press release (8-K Item 2.02) for management
tone, guidance hedging, and surprise factor — signals that show up *before*
the news cycle digests the print.

Free signal source: SEC EDGAR. We feed the prepared management commentary to
Claude Haiku with a structured JSON prompt and inject the result into the
sentiment scorer as a separate sub-signal.

A press release is not a full transcript (no analyst Q&A), so we can score
prepared statements and guidance language but not pushback. Future upgrade:
plug in a transcript source for QoQ tone delta and analyst pressure.
"""

import json
import os
import re

# Module-level cache: by (ticker, release_date) -> result. Press releases don't
# change once filed, so we only score each one once per process.
_cache = {}


def score_earnings_release(release, symbol):
    """
    Score an earnings press release dict (from sec_edgar.get_latest_earnings_release).
    Returns dict on success, None on any failure (caller treats as no-signal).

    Output:
      {
        score: float in [-1, 1]    # overall press release sentiment for the ticker
        hedging: 'low'|'medium'|'high'  # qualifier density in forward statements
        surprise: float in [-1, 1] # whether results beat/missed implied expectations
        guidance_direction: 'raised'|'maintained'|'lowered'|'absent'
        key_points: list[str]      # 2-3 short bullets
        release_date: str
      }
    """
    if not release or not release.get("text"):
        return None

    cache_key = (symbol.upper(), release.get("date", ""))
    if cache_key in _cache:
        return _cache[cache_key]

    try:
        import config
        import anthropic
    except Exception:
        return None

    api_key = getattr(config, "CLAUDE_API_KEY", None) or os.environ.get("CLAUDE_API_KEY")
    if not api_key:
        return None

    text = release["text"]
    prompt = (
        f"You are reading the earnings press release for {symbol} filed on "
        f"{release.get('date', 'unknown')}. Score the prepared statements.\n\n"
        f"Return ONLY a JSON object with these exact keys (no markdown, no prose):\n"
        f"  score: number in [-1.0, 1.0]  // overall sentiment for the stock; "
        f"factor in beat/miss, guidance, tone\n"
        f"  hedging: \"low\" | \"medium\" | \"high\"  // density of qualifiers like "
        f"\"could\", \"may\", \"subject to\" in forward statements\n"
        f"  surprise: number in [-1.0, 1.0]  // results vs the language used to "
        f"frame them; positive if confident/beats implied, negative if defensive\n"
        f"  guidance_direction: \"raised\" | \"maintained\" | \"lowered\" | \"absent\"\n"
        f"  key_points: array of 2-3 short strings (max 80 chars each), each "
        f"capturing a specific data point or statement\n\n"
        f"Critical: judge from the {symbol} shareholder's view. Boilerplate "
        f"\"forward-looking statements\" disclaimers do not count as hedging — "
        f"only qualifiers attached to specific guidance.\n\n"
        f"Press release text:\n{text}"
    )

    try:
        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}],
        )
        out_text = message.content[0].text.strip()
        out_text = re.sub(r"^```(?:json)?\s*|\s*```$", "", out_text, flags=re.MULTILINE).strip()
        parsed = json.loads(out_text)
    except Exception as e:
        print(f"  ⚠️  Earnings press release scoring failed for {symbol}: {e}")
        return None

    score = max(-1.0, min(1.0, float(parsed.get("score", 0.0))))
    hedging = str(parsed.get("hedging", "medium")).lower()
    if hedging not in ("low", "medium", "high"):
        hedging = "medium"
    surprise = max(-1.0, min(1.0, float(parsed.get("surprise", 0.0))))
    guidance = str(parsed.get("guidance_direction", "absent")).lower()
    if guidance not in ("raised", "maintained", "lowered", "absent"):
        guidance = "absent"
    key_points = parsed.get("key_points", [])
    if not isinstance(key_points, list):
        key_points = []
    key_points = [str(p)[:120] for p in key_points[:3]]

    result = {
        "score": round(score, 3),
        "hedging": hedging,
        "surprise": round(surprise, 3),
        "guidance_direction": guidance,
        "key_points": key_points,
        "release_date": release.get("date", ""),
    }
    _cache[cache_key] = result
    return result


def earnings_signal_to_adjustment(signal):
    """
    Convert a scored earnings release into a sentiment-score adjustment in points
    (range roughly -12 to +12). Caller adds this to the 0-100 sentiment score.

    Weighting:
      - score (overall) is the primary driver (up to +-8 points)
      - guidance_direction adds +-3 (raised/lowered)
      - hedging=high subtracts 1 (uncertainty is mildly bearish)
    """
    if not signal:
        return 0, []

    score = signal.get("score", 0.0)
    guidance = signal.get("guidance_direction", "absent")
    hedging = signal.get("hedging", "medium")

    adj = score * 8.0
    if guidance == "raised":
        adj += 3.0
    elif guidance == "lowered":
        adj -= 3.0
    if hedging == "high":
        adj -= 1.0

    notes = []
    if signal.get("release_date"):
        notes.append(f"Earnings release {signal['release_date']}: tone={score:+.2f}, guidance={guidance}, hedging={hedging}")
    for kp in signal.get("key_points", [])[:2]:
        notes.append(f"  • {kp}")

    return round(adj, 1), notes

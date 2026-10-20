# PS-06: Social Media Sentiment & Response Agent

A multi-agent brand intelligence system. It monitors mentions, classifies them, reads sentiment and emotion, scores influence, discovers trending topics, detects PR crises early, drafts replies for **human approval**, and reports everything on an executive dashboard.

The system runs on **real tweets** (Twitter US Airline Sentiment, ~14.6k tweets, 16–24 Feb 2015) replayed hour by hour. On launch you **choose a workspace**, one of the 6 airlines. That airline becomes "our brand" and the other 5 become its competitors. Each workspace keeps its own replay clock, alerts, topics, reply queue and crisis scenario. The URL `?brand=Delta` keeps you in a workspace across refreshes.

## Architecture (LangGraph)

```
listening → sentiment_emotion → classification → influence → trend_discovery → brand_risk
      ──(High/Critical or forecast)──▶ escalation
      → response_generation → approval_queue (human, interrupt) → campaign_intel → executive_report
```

| # | Agent | File | How it works |
|---|---|---|---|
| 1 | Social Listening | `agents/listening.py` | Pulls each hour's mentions; tracks brands, products, executives, hashtags |
| 2 | Mention Classification | `agents/classifier.py` | Groq Llama 3.1 8B, batched 20 per call (keyword rules as fallback) |
| 3 | Sentiment & Emotion | `agents/sentiment.py` | `twitter-roberta-sentiment` + `go_emotions` mapped to Angry/Frustrated/Confused/… |
| 4 | Influence Scoring | `agents/influence.py` | Impact 0-100 from reach, engagement, verified, intensity; viral score |
| 5 | Trend Discovery | `agents/trends.py` | MiniLM embeddings + HDBSCAN clusters, c-TF-IDF terms, LLM names, 2h growth % |
| 6 | Brand Risk | `agents/risk.py` | z-score vs rolling baseline + cluster growth + impact + emotion; 2h forecast |
| 7 | Response Generation | `agents/responder.py` | Tone-aware drafts (friendly/professional/luxury/startup) with customer history |
| 8 | Approval Workflow | `agents/approval.py` | One LangGraph thread per draft, paused with `interrupt()`, SQLite checkpoints |
| 9 | Campaign Intelligence | `agents/campaign.py` | Reach, engagement, sentiment, conversions, giving a success score |
| 10 | Executive Reporting | `agents/reporter.py` | Brand Health 0-100, competitor benchmark, LLM briefing |
| 11 | Master Orchestrator | `graph/orchestrator.py` | The compiled StateGraph, run once per replay hour |

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
```

This team repo already includes everything needed to run straight away:
- `data/raw/Tweets.csv`: the dataset
- `data/brand.db`: all tweets pre-scored by the local models, which saves the ~35-minute prep step
- `.env`: shared settings (model names, Reddit placeholders)

**Add your own Groq key** (free at <https://console.groq.com/keys>, and each teammate should use their own, because the free tier's rate limits apply per Groq account). Create a file named `.env.local` in the project folder containing one line:

```
GROQ_API_KEY=gsk_your_key_here
```

`.env.local` is git-ignored, so the key is never pushed. Without a key, the app still runs on keyword rules and templates.

Then:

1. Run the dashboard: `streamlit run app.py`. The first launch downloads the three HuggingFace models (~1 GB) once.
2. Evaluate against the human labels: `python -m eval.evaluate` (writes `eval/results.md`).

To rebuild the data from scratch, delete `data/brand.db` and run `python -m scripts.prepare` (add `--llm` to Groq-classify United's posts up front). `python -m scripts.prepare --reset` clears every workspace's replay progress but keeps the scored data.

## Demo script

1. **Run 24 hours** from the sidebar. The KPIs, clusters and competitor view fill with real data.
2. Keep going into 22–23 Feb. Real cancellation and delay complaints form issue clusters with growth %.
3. Click **🚨 Inject crisis**, then advance 3 hours. An "App check-in failures" cluster grows (12 → 45 → 140 posts/h). Risk goes to High/Critical, an alert recommends *Escalate to Product / Engineering + PR*, and the forecast warns ahead of time.
4. Open **Approval Queue**. Edit, approve or reject the drafted replies. Nothing is auto-posted.
5. **Executive Summary → Generate briefing** produces a written summary for leadership.

## Live mode

Every workspace also has a **Live now** mode that monitors today's public posts:

| Source | Key | What it adds |
|---|---|---|
| Bluesky search | none | Posts with **real** follower, like and repost counts |
| Google News RSS | none | Headlines about the airline from the last day |
| Mastodon hashtags | none | Posts from mastodon.social |
| Reddit API | free app keys in `.env` | Airline subreddits plus site-wide search (the busiest source) |

A background engine polls every 90 s, scores new posts immediately, and re-runs all 11 agents every 10 minutes over the last hour. The first time a live workspace opens, it backfills 24 hours. Pages refresh on their own. US Airways and Virgin America no longer fly, so they go live as **US Airways (now American Airlines)** and **Virgin America (now Alaska Airlines)**. Live posts have no ground-truth labels, so accuracy figures come from the 2015 dataset only.

## Real vs synthetic data (be upfront about this)

| Real (from the dataset) | Synthetic (seeded, reproducible, flagged `is_synthetic`) |
|---|---|
| Tweet text, airline, handle, timestamp, retweets, location | Follower counts and verified status (long-tail distribution per handle) |
| Human sentiment and negative-reason labels (**evaluation only**) | Likes (derived from real retweets + follower tier) |
| Hashtags found in the text | `#FlyUnited2015` campaign posts; clicks and conversions |
| | Crisis-injector posts (demo button) |

The original tweets have no follower data, and real 2015 follower counts would need the paid X API.

## Notes
- Groq free tier: all LLM calls are cached in SQLite and batched. The sidebar shows call and token counts.
- `python -m scripts.prepare --reset` clears replay results so you can restart the demo.

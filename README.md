# QuantFlow

**An AI-powered trading workflow for the German DAX 40 market.**
Eight specialized agents that cover every stage of the trading day — pre-market analysis, strategy backtesting, human-in-the-loop execution, and post-trade review — orchestrated through Claude, Yahoo Finance data, and email.

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)
![Claude](https://img.shields.io/badge/Claude-Sonnet%204-FF6B35?style=flat-square)
![FastAPI](https://img.shields.io/badge/FastAPI-Backend-009688?style=flat-square&logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-Frontend-61DAFB?style=flat-square&logo=react&logoColor=black)
![Market](https://img.shields.io/badge/Market-DAX%2040%20XETRA-009933?style=flat-square)
![Agents](https://img.shields.io/badge/Agents-8%20Active-brightgreen?style=flat-square)
![License](https://img.shields.io/badge/License-MIT-lightgrey?style=flat-square)

---

## Table of Contents

- [Overview](#overview)
- [The Agents](#the-agents)
- [Daily Workflow](#daily-workflow)
- [Featured — Strategy Builder](#featured--strategy-builder)
- [Repository Structure](#repository-structure)
- [Quick Start](#quick-start)
- [Agent Guide](#agent-guide)
- [Tech Stack](#tech-stack)
- [Environment & Secrets](#environment--secrets)
- [Development Conventions](#development-conventions)
- [Roadmap](#roadmap)
- [Disclaimer](#disclaimer)

---

## Overview

Most retail traders open their platform at 09:00 CET with no plan, no watchlist, and no risk framework. QuantFlow closes those gaps by wiring together eight independent agents into a single, auditable trading workflow:

- **Pre-market** — AI-written market briefing, technical setup scan across DAX 40, human-in-the-loop approval workflow for every setup.
- **Strategy research** — plain-English strategy builder with a full React dashboard, backtested across 54 instruments (DAX, indexes, crypto, commodities).
- **Trade execution** — pre-trade security guardrails block rule violations, a live risk monitor watches open positions, trade journal logs every fill.
- **Post-trade** — AI-powered chart analysis and coaching against your full trade history.

Each agent runs independently; together they form a pipeline that mirrors the workflow of a professional trading desk.

---

## The Agents

| # | Agent | Purpose | Trigger |
|---|---|---|---|
| 1 | **Morning Briefing** | AI-written DAX market email before the open | Scheduled — 08:30 CET weekdays |
| 2 | **Trade Journal** | Interactive trade logging, stats, AI coaching | Manual — after each trade |
| 3 | **Chart Analysis** | Validates trades against real historical charts | Manual — weekly review |
| 4 | **Setup Scanner** | Ranks DAX 40 for breakout / pullback / reversal setups | Scheduled — 08:30 CET |
| 5 | **Risk Monitor** | Watches open positions, emails breach alerts | Manual — during market hours |
| 6 | **Trade Executor** | Emails setup approvals, reads YES/NO replies | Scheduled — 08:30 CET |
| 7 | **Security Guardrails** | Seven-rule pre-trade risk check | Every trade |
| 8 | **Strategy Builder** | Plain-English → backtested strategy, React dashboard | On-demand — web app |

---

## Daily Workflow

```
08:30 CET  ── Morning briefing email arrives
           ── Setup scanner generates ranked HTML report
           ── Trade executor emails setup approvals
                     │
                     ▼
08:30 → 09:00 ── Review reports, reply YES/NO to setup emails
                     │
                     ▼
09:00 CET  ── XETRA opens — trade with a clear, pre-approved plan
                     │
                     ▼
Every trade ── Security guardrails runs 7 rule checks before logging
                     │
                     ▼
During day  ── Risk monitor watches all positions every 5 minutes
                     │
                     ▼
End of day  ── Journal agent logs the trade with AI coaching
                     │
                     ▼
Weekly      ── Chart analysis agent reviews your full history
                     │
                     ▼
Ad hoc      ── Strategy builder dashboard for new idea research
```

---

## Featured — Strategy Builder

![Strategy Builder Dashboard](docs/screenshots/strategy-builder.png)

The Strategy Builder is the flagship agent: a full-stack web dashboard where you describe a trading strategy in plain English and get a multi-instrument backtest report, live-streamed as it runs.

**What it does:**
- Parses your plain-English rule description with Claude into a structured JSON strategy
- Backtests across **54 instruments** — 40 DAX stocks, 4 German indexes, 5 major cryptocurrencies, 5 commodities
- Streams per-ticker results over Server-Sent Events while the backtest is running
- Renders a professional editorial-style dashboard with Performance KPIs (Win Rate, Profit Factor, Avg Hold, Lead Performer), horizontal bar charts for returns and win rate per instrument, a sortable full-results table, and collapsible per-instrument trade detail

**Design system:** Editorial Financial Terminal — Fraunces serif display, JetBrains Mono for all numerals, Instrument Sans for UI, warm near-black paper with amber signature accent.

**Run it locally:**
```bash
cd Strategy_builder
py -3.14 -m uvicorn app:app --host 0.0.0.0 --port 8000
# open http://localhost:8000
```

**Rebuild the frontend after editing React source:**
```bash
cd Strategy_builder/frontend
npm run build
```

---

## Repository Structure

```
quantflow/
├── README.md                     ← you are here
├── requirements.txt              ← shared Python dependencies
├── .env.example                  ← template for API keys and email creds
├── .claude/
│   └── skills/frontend-design/   ← Anthropic frontend-design skill (installed)
│
├── Morning_briefing_Agent/
│   ├── briefing_agent.py         ← fetch → AI analysis → email (scheduled)
│   ├── briefing_agent_once.py    ← one-shot version for manual runs
│   ├── config.py                 ← watchlist, thresholds
│   └── main.py
│
├── Trade_Journal_Agent/
│   ├── journal_agent.py          ← interactive trade entry
│   ├── stats.py                  ← performance summary
│   ├── chart_agent.py            ← AI coaching with chart validation
│   ├── trades.csv                ← persistent trade log
│   └── config.py
│
├── Technical_setup_scanner/
│   ├── setup_scanner.py          ← scan → rank → HTML report
│   └── main.py
│
├── risk_monitoring_agent/
│   ├── risk_monitor.py           ← 5-rule position monitor with email alerts
│   └── main.py
│
├── Trader_Executer Agent/
│   ├── trade_ecexuter.py         ← setup scan → email approval → IMAP read → log
│   ├── decisions_log.csv         ← approval/rejection history
│   ├── pending_trades.json       ← in-flight approvals
│   └── main.py
│
├── Security_Guardrails/
│   ├── guardrail_agent.py        ← 7-rule pre-trade check
│   ├── daily_state.json          ← running daily trade/loss counters
│   └── sample_trades.csv         ← sample input for batch mode
│
└── Strategy_builder/
    ├── app.py                    ← FastAPI backend + SSE streaming
    ├── strategy_builder.py       ← Claude parser, backtest engine, indicators
    ├── frontend/                 ← Vite + React + Recharts dashboard
    │   ├── src/
    │   │   ├── App.jsx
    │   │   ├── index.css         ← editorial design system
    │   │   ├── hooks/useStrategyStream.js
    │   │   └── components/       ← Header, ChatPanel, KPICards, charts, ...
    │   └── package.json
    └── static/                   ← production React build (served by FastAPI)
```

---

## Quick Start

**Prerequisites**
- Python 3.11+ (the Strategy Builder is tested on Python 3.14)
- Node.js 18+ (required only for the Strategy Builder frontend)
- An Anthropic API key — [console.anthropic.com](https://console.anthropic.com)
- A Gmail account with an App Password (for the email-based agents)

```bash
# 1. Clone
git clone https://github.com/<your-handle>/quantflow.git
cd quantflow

# 2. Install shared Python dependencies
pip install -r requirements.txt

# 3. Configure secrets
cp .env.example .env
# edit .env and fill in ANTHROPIC_API_KEY, EMAIL_SENDER, EMAIL_PASSWORD, EMAIL_RECEIVER

# 4. Smoke-test the simplest agent
python Morning_briefing_Agent/briefing_agent_once.py

# 5. Launch the Strategy Builder dashboard
cd Strategy_builder
python -m uvicorn app:app --host 0.0.0.0 --port 8000
# open http://localhost:8000
```

> **Gmail App Password:** Google Account → Security → 2-Step Verification → App Passwords → Generate.

---

## Agent Guide

### 1 — Morning Briefing

Sends an AI-written DAX market briefing at 08:30 CET each weekday. Covers the full watchlist with live prices, volume flags, key technical levels, and analysis written in the voice of a senior Frankfurt trader.

```bash
python Morning_briefing_Agent/briefing_agent_once.py   # send immediately
python Morning_briefing_Agent/main.py                  # run under scheduler
```

### 2 & 3 — Trade Journal + Chart Analysis

Three integrated tools for logging trades, tracking performance, and getting AI coaching against the chart.

```bash
python Trade_Journal_Agent/main.py          # log a trade interactively
python Trade_Journal_Agent/stats.py         # performance summary
python Trade_Journal_Agent/chart_agent.py   # generate HTML coaching report
```

The coaching report evaluates each trade on setup confirmation, entry/exit timing quality, a discipline score out of 10, sector alignment, and a skill-vs-luck assessment with specific lessons.

### 4 — Setup Scanner

Scans all 37 active DAX constituents, calculates RSI, EMA21/50/200, MACD, ATR, and volume surge, detects five setup archetypes, and ranks them with AI commentary, entry/stop/target zones.

```bash
python Technical_setup_scanner/setup_scanner.py            # default top 10
python Technical_setup_scanner/setup_scanner.py --top 5    # limit to top 5
```

**Setup archetypes:** Breakout · Pullback · Momentum · Breakdown · Reversal.

### 5 — Risk Monitor

Monitors open positions every five minutes and emails alerts on rule breaches.

```bash
python risk_monitoring_agent/risk_monitor.py --account 10000
python risk_monitoring_agent/risk_monitor.py --csv open_positions.csv
```

**Rules:** daily loss limit, position size > 2% of account, missing stop loss, single-trade drawdown, daily profit target.

### 6 — Trade Executor

The human-in-the-loop approval layer. Scans for setups, emails you for approval before XETRA opens, reads your YES/NO replies via IMAP, logs decisions automatically.

```bash
python "Trader_Executer Agent/trade_ecexuter.py"              # run once
python "Trader_Executer Agent/trade_ecexuter.py" --schedule   # auto at 08:30 weekdays
python "Trader_Executer Agent/trade_ecexuter.py" --check      # poll replies now
```

**Reply format:** `YES SAP` or `NO SAP` — the agent parses replies within two minutes and logs every decision to `decisions_log.csv`.

### 7 — Security Guardrails

A pre-trade checker that runs seven automated rules before any trade is logged or executed. Blocks violations and emails alerts.

```bash
python Security_Guardrails/guardrail_agent.py                          # one-trade interactive
python Security_Guardrails/guardrail_agent.py --csv sample_trades.csv  # batch mode
python Security_Guardrails/guardrail_agent.py --report                 # print active rule set
```

**Rules:** stop loss defined · position size within account risk · R/R meets minimum · daily loss limit · daily trade count · ticker not on blocklist · no duplicate position.

### 8 — Strategy Builder

See [Featured — Strategy Builder](#featured--strategy-builder) above.

---

## Tech Stack

### Core

| Layer | Technology | Used In |
|---|---|---|
| LLM | **Anthropic Claude Sonnet 4** (direct SDK, no framework) | All agents for analysis, coaching, ranking, strategy parsing |
| Market data | **yfinance** | Every agent that touches prices |
| Data processing | **pandas, NumPy** | Indicator math, trade journal, backtest engine |
| Charting (Python) | **matplotlib, mplfinance** | Chart validation, setup scanner, report images |
| Email I/O | **smtplib, imaplib** (stdlib) | All scheduled agents, trade executor IMAP polling |
| Scheduling | **schedule** | Morning briefing, trade executor |
| Config | **python-dotenv** | Every agent reads `.env` |

### Strategy Builder Web App

| Layer | Technology |
|---|---|
| Backend | **FastAPI** with Server-Sent Events |
| ASGI server | **uvicorn** |
| Frontend framework | **React 18** (functional, hooks) |
| Build tool | **Vite** |
| Charts | **Recharts** |
| Typography | **Fraunces** (serif), **Instrument Sans**, **JetBrains Mono** |

### Persistence

QuantFlow deliberately uses **file-based persistence** — CSVs for trade logs and position data, JSON for ephemeral state, HTML for generated reports. No database is required. This keeps every agent independently runnable and every data file directly auditable in a text editor.

---

## Environment & Secrets

All configuration flows through environment variables loaded from `.env` by `python-dotenv`. Never hardcode keys.

```env
# --- AI ---
ANTHROPIC_API_KEY=sk-ant-...

# --- Email (Gmail App Password, not your real password) ---
EMAIL_SENDER=your_account@gmail.com
EMAIL_PASSWORD=xxxx xxxx xxxx xxxx
EMAIL_RECEIVER=destination@example.com
```

**Security notes**
- `.env` is in `.gitignore` — never commit it.
- Gmail App Passwords are scoped and revocable — never use your primary password.
- No broker API keys live in this repo. The system is designed for paper trading and human-approved execution.
- Every scheduled agent logs its actions to a CSV or JSON file for full auditability.

---

## Development Conventions

### Python

- **Style**: single-file agents for clarity. Each agent is self-contained in its own folder — no cross-imports between agents.
- **Indicators**: RSI (Wilder, period 14 via EWM with `com=13`), EMA21/50/200, MACD (12/26/9), 20-day volume SMA for surge detection, 20-day high/low for breakouts.
- **AI output**: every Claude response that the code acts on is validated — the strategy parser has a defensive fallback schema, and JSON is stripped of markdown fences before parsing.
- **Unicode**: all `print()` statements use ASCII characters so the CLI works on Windows `cp1252` terminals. No emoji or box-drawing characters in runtime output.
- **Error handling**: network/data errors are caught at the boundary (ticker fetch, LLM call, IMAP read) and logged with context rather than silently swallowed.

### Frontend (Strategy Builder only)

- **No Tailwind / no CSS-in-JS library** — plain CSS custom properties via `index.css`, inline styles for component specifics. Keeps the bundle small and the design system readable.
- **Typography** is intentional, not default — see the `frontend-design` skill output.
- **State**: a single `useStrategyStream` hook owns the SSE connection and all backtest state. Components are pure presentation.

### Git

- Conventional Commits (`feat:`, `fix:`, `refactor:`, `docs:`, `chore:`) for every commit.
- Commit message body explains **why**, not what — the diff already shows what.

---

## Roadmap

- [x] Plain-English strategy builder with full dashboard (shipped)
- [x] Multi-asset backtest coverage — DAX 40, indexes, crypto, commodities
- [x] Editorial redesign using the Anthropic `frontend-design` skill
- [ ] Broker API integration (Interactive Brokers, Alpaca, Trade Republic)
- [ ] Additional markets — S&P 500, FTSE 100, Nifty 50
- [ ] Telegram alert channel (complement to email)
- [ ] ML-based conviction score for setup scanner
- [ ] Portfolio-level risk aggregation across all open agents
- [ ] Historical strategy replay mode (step through past days)

---

## Disclaimer

This project is built for educational and portfolio demonstration purposes only. Nothing here constitutes financial advice. Past performance of any strategy shown does not guarantee future results. Always do your own research and consult a qualified financial advisor before making any trading decisions.

---

## License

MIT — free to use, modify, and distribute with attribution.

---

<div align="center">
  <sub>QuantFlow · Built in Stuttgart · Trading discipline meets agentic AI</sub>
</div>

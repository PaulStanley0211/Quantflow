# ⚡ QuantFlow — AI Trading Agent System

> A production-grade AI-powered trading workflow system for the German DAX 40 market.
> Built with Python, Claude AI, and Yahoo Finance — covering every stage of the trading day.

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat&logo=python&logoColor=white)
![Claude AI](https://img.shields.io/badge/Claude-Sonnet%204-FF6B35?style=flat)
![Market](https://img.shields.io/badge/Market-DAX%2040%20XETRA-009933?style=flat)
![License](https://img.shields.io/badge/License-MIT-lightgrey?style=flat)
![Status](https://img.shields.io/badge/Status-Active-brightgreen?style=flat)

---

## 🧠 Overview

QuantFlow is a complete end-to-end AI trading assistant system built for the German DAX 40 market. It combines real swing and day trading experience with AI agent automation to cover every stage of the trading day — from pre-market preparation to post-trade performance coaching.

Most retail traders open their platform at 09:00 with no plan and trade on impulse. QuantFlow gives you the same systematic workflow used by professional trading desks — automated, intelligent, and fully auditable.

---

## 🤖 The 6 Agents

| # | Agent | What It Does | Trigger |
|---|---|---|---|
| 1 | **Morning Briefing** | AI-written DAX market email before open | Auto — 08:30 CET |
| 2 | **Trade Journal** | Logs trades with AI coaching and R-multiple | Manual — after trade |
| 3 | **Chart Analysis** | Validates every trade against real charts | Manual — weekly review |
| 4 | **Setup Scanner** | Scans 37 DAX stocks for technical setups | Auto — 08:30 CET |
| 5 | **Risk Monitor** | Watches open positions and sends risk alerts | Manual — during trading |
| 6 | **Trade Executor** | Emails setup approvals — logs YES/NO decisions | Auto — 08:30 CET |

---

## 📅 Daily Workflow

```
08:30 CET ─── Morning briefing email arrives automatically
08:30 CET ─── Setup scanner generates HTML report
08:30 CET ─── Trade executor emails setup approvals
              │
              ▼
08:30–09:00 ── You review reports, reply YES/NO to setups
              │
              ▼
09:00 CET ─── XETRA opens — you trade with a clear plan
              │
              ▼
During day ─── Risk monitor watches all open positions
              │
              ▼
End of day ─── Journal agent logs each trade with AI coaching
              │
              ▼
Weekly ──────── Chart analysis agent reviews your full trade history
```

---

## 🏗️ Project Structure

```
quantflow/
│
├── README.md                        ← you are here
├── requirements.txt                 ← install everything with one command
├── .env.example                     ← API key template
├── .gitignore
│
├── Morning_briefing_Agent/
│   ├── briefing_agent.py            ← fetch → AI analysis → email
│   ├── briefing_agent_once.py
│   ├── config.py                    ← watchlist and settings
│   └── main.py
│
├── Trade_Journal_Agent/
│   ├── journal_agent.py             ← interactive trade logging
│   ├── stats.py                     ← performance summary
│   ├── chart_agent.py               ← chart validation and coaching
│   ├── config.py
│   └── main.py
│
├── Technical_setup_scanner/
│   ├── setup_scanner.py             ← scan → rank → HTML report
│   └── main.py
│
├── risk_monitoring_agent/
│   ├── risk_monitor.py              ← monitor → alert → email
│   └── main.py
│
└── Trader_Executer Agent/
    ├── trade_ecexuter.py            ← scan → email → read reply → log
    └── main.py
```

---

## ⚙️ Tech Stack

| Technology | Purpose |
|---|---|
| **Python 3.10+** | Core language |
| **Claude Sonnet 4 (Anthropic)** | AI trade analysis, coaching, and ranking |
| **Yahoo Finance (yfinance)** | Free real-time and historical DAX market data |
| **pandas** | Technical indicator calculations |
| **matplotlib** | Candlestick chart generation |
| **smtplib / imaplib** | Email sending and reply detection |
| **schedule** | Automated daily execution at 08:30 CET |
| **python-dotenv** | Secure API key management |

---

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- Anthropic API key — [get one at console.anthropic.com](https://console.anthropic.com)
- Gmail account with App Password enabled

### 1. Clone the repository
```bash
git clone https://github.com/yourusername/quantflow.git
cd quantflow
```

### 2. Install all dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure your environment
```bash
cp .env.example .env
```
Open `.env` and fill in:
```env
ANTHROPIC_API_KEY=sk-ant-your-key-here
EMAIL_SENDER=your_gmail@gmail.com
EMAIL_PASSWORD=your_16_char_app_password
EMAIL_RECEIVER=your_email@example.com
```

> **Gmail App Password:** Google Account → Security → 2-Step Verification → App Passwords → Generate

### 4. Run your first agent
```bash
python Morning_briefing_Agent/briefing_agent_once.py
```

---

## 💡 Agent Details

### 01 — Morning Briefing Agent
Sends a professional DAX market briefing email every weekday at 08:30 CET. Covers your full watchlist with live prices, volume flags, technical levels, and an AI-written analysis in the style of a senior Frankfurt trader.

```bash
python Morning_briefing_Agent/briefing_agent_once.py    # send now
python Morning_briefing_Agent/main.py                   # run with scheduler
```

---

### 02 & 03 — Trade Journal + Chart Analysis Agent
Three tools in one — log trades interactively, view performance stats, and validate trades against real historical charts with AI coaching.

```bash
python Trade_Journal_Agent/main.py          # log a trade
python Trade_Journal_Agent/stats.py         # view performance summary
python Trade_Journal_Agent/chart_agent.py   # generate HTML chart coaching report
```

**What the chart analysis report gives you for every trade:**
- ✅ Setup confirmed or not
- ⏱️ Entry and exit timing quality
- 🎲 Skill vs luck assessment
- 📈 Discipline score out of 10
- 🎭 Sector alignment check
- 💡 Specific coaching lessons

---

### 04 — Setup Scanner
Scans all 37 DAX 40 stocks, calculates RSI, EMA21/50/200, MACD, ATR, and volume surge, detects 5 setup types, and generates a ranked HTML report with AI commentary, entry zones, stops, and targets.

```bash
python Technical_setup_scanner/setup_scanner.py           # run once
python Technical_setup_scanner/setup_scanner.py --top 5   # show top 5 instead of 10
```

**Setup types detected:** Breakout · Pullback · Momentum · Breakdown · Reversal

---

### 05 — Risk Monitor Agent
Watches your open positions every 5 minutes and sends instant email alerts when any risk rule is breached.

```bash
python risk_monitoring_agent/risk_monitor.py --account 10000             # manual entry
python risk_monitoring_agent/risk_monitor.py --csv open_positions.csv    # load from CSV
```

**5 rules monitored:**
- 🔴 Daily loss limit (default €500)
- 🟡 Position size > 2% of account
- 🟡 Stop loss missing on any position
- 🟠 Single trade drawdown > €100
- 🟢 Daily profit target hit (default €300)

---

### 06 — Trade Executor
Human-in-the-loop approval system. Scans for setups, emails you for approval before XETRA opens, reads your YES/NO replies, and logs everything automatically.

```bash
python "Trader_Executer Agent/trade_ecexuter.py"            # run once
python "Trader_Executer Agent/trade_ecexuter.py" --schedule # auto-run at 08:30 weekdays
python "Trader_Executer Agent/trade_ecexuter.py" --check    # check email replies now
```

**Reply format:** `YES SAP` or `NO SAP` — the agent reads your reply within 2 minutes and logs the decision.

---

## 📊 Sample Outputs

### Morning Briefing Email
```
📧 Morgen Markt Briefing — DAX / XETRA
Tuesday April 22 2026 · XETRA öffnet 09:00 CET

SAP.DE   €185.20  ▲ 1.2%   🔥 2.3x volume
SIE.DE   €189.40  ▲ 0.8%   Normal volume
BMW.DE   €92.10   ▼ 0.5%   Normal volume

AI Analysis: The DAX opens with broad technology strength
led by SAP. Focus list: SAP breakout continuation, SIE
volume surge watch, BMW support test at €92...
```

### Performance Stats
```
🏆 Trading Performance Summary
Total trades    : 12    Win rate : 66.7% (8W/4L)
Total P&L       : +€1,382    Avg R : 1.8R

🛡️ Stop Loss Discipline
With stop : 11/12 ██████████████████████ (91.7%)

📊 P&L by Setup Type
Momentum      +€694  (2 trades)  ████████████████████
Breakout      +€631  (2 trades)  █████████████████████
Trend-Follow  +€535  (2 trades)  ███████████████████
News-Play     -€345  (1 trade)   ████████████
```

### Risk Alert Email
```
🚨 Risk Monitor Alert — 2 alert(s) — P&L -€245.00

CRITICAL — Stop Loss Hit — SAP.DE
SAP.DE hit stop at €175.50. Current: €173.20. EXIT NOW.

WARNING — No Stop Loss — BAYN.DE
BAYN.DE has no stop loss defined. Define one immediately.
```

### Trade Approval Email
```
📧 Trade Approval — 2 setup(s) — April 22 2026

SAP — Breakout — BUY  84/100
Entry €185.50 | Stop €182.00 | Target €192.00 | R/R 2.1:1
→ Reply YES SAP to approve / NO SAP to reject
```

---

## 🔒 Security

- All API keys stored in `.env` — never hardcoded in any file
- `.gitignore` prevents secrets from being committed to GitHub
- Gmail App Passwords used — real password never stored
- No broker API connection — fully safe for paper trading
- Human approval required before any trade is logged

---

## 🗺️ Roadmap

- [ ] Broker API integration (Interactive Brokers, Alpaca, Trade Republic)
- [ ] Multi-market support (S&P 500, FTSE 100, Nifty 50, Crypto)
- [ ] Telegram alert integration
- [ ] Backtesting module for historical setup validation
- [ ] Web dashboard for full portfolio overview
- [ ] Pre-trade checklist agent

---

## 📚 Certifications & Learning

Built alongside formal study in:
- AI in Finance — Simplilearn SkillUp
- Financial Markets — Yale University / Coursera
- Technical Analysis — Corporate Finance Institute (CFI)
- Algorithmic Trading — QuantInsti / Quantra

---

## 👤 About

Built by a trader and AI agent developer based in Stuttgart, Germany.

Combining hands-on swing trading and day trading experience in German markets with AI automation to build professional-grade trading infrastructure. This project demonstrates the intersection of quantitative finance and agentic AI systems.

**Skills demonstrated:**
- AI agent design and orchestration
- Financial data engineering
- Technical analysis automation
- Risk management systems
- Human-in-the-loop AI governance

---

## ⚠️ Disclaimer

This project is built for educational and portfolio demonstration purposes only. Nothing in this repository constitutes financial advice. Past performance of any strategy shown does not guarantee future results. Always conduct your own research and consult a qualified financial advisor before making any trading decisions.

---

## 📝 License

MIT License — free to use, modify, and distribute with attribution.

---

<div align="center">
  <b>⚡ QuantFlow — Built in Stuttgart, Germany</b><br>
  <sub>Trading knowledge + AI automation = professional edge</sub>
</div>

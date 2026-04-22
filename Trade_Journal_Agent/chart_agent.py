"""
chart_agent.py — Trade Chart Analysis Agent
=============================================
Reads your trades CSV, fetches real historical charts,
generates candlestick charts with entry/exit markers,
runs Claude AI analysis on each trade, and produces
a full HTML coaching report.

Usage:
    python chart_agent.py
    python chart_agent.py --csv my_trades.csv
    python chart_agent.py --csv my_trades.csv --email

Requirements:
    pip install -r requirements.txt
"""

import os
import csv
import json
import base64
import argparse
import smtplib
from io import BytesIO
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import re

import anthropic
import yfinance as yf
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
EMAIL_SENDER      = os.getenv("EMAIL_SENDER", "")
EMAIL_PASSWORD    = os.getenv("EMAIL_PASSWORD", "")
EMAIL_RECEIVER    = os.getenv("EMAIL_RECEIVER", "")

# ─────────────────────────────────────────────
# GERMAN SECTOR MAP
# ─────────────────────────────────────────────
SECTOR_MAP = {
    "SAP.DE":   ("Technology",    "^TECDAX"),
    "SIE.DE":   ("Industrials",   "^MDAX"),
    "BMW.DE":   ("Automotive",    "^GDAXI"),
    "VOW3.DE":  ("Automotive",    "^GDAXI"),
    "MBG.DE":   ("Automotive",    "^GDAXI"),
    "ALV.DE":   ("Finance",       "^GDAXI"),
    "DBK.DE":   ("Finance",       "^GDAXI"),
    "BAS.DE":   ("Chemicals",     "^GDAXI"),
    "BAYN.DE":  ("Pharma",        "^MDAX"),
    "ADS.DE":   ("Consumer",      "^GDAXI"),
    "DTE.DE":   ("Telecom",       "^GDAXI"),
}


def _strip_markdown_fences(text: str) -> str:
    """Remove optional ```json ... ``` wrapping that the model may add."""
    text = text.strip()
    match = re.match(r"^```(?:json)?\s*([\s\S]*?)\s*```$", text)
    if match:
        return match.group(1)
    return text


# ─────────────────────────────────────────────
# 1. LOAD CSV — works with any column format
# ─────────────────────────────────────────────

def load_trades(csv_file: str) -> list:
    """Load trades from CSV. Auto-detects column names."""
    trades = []
    with open(csv_file, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Normalize keys to lowercase
            row = {k.lower().strip(): v.strip() for k, v in row.items()}

            # Map flexible column names
            def get(options, default=""):
                for o in options:
                    if o in row and row[o]:
                        return row[o]
                return default

            trade = {
                "ticker":       get(["ticker", "symbol", "stock"]),
                "direction":    get(["direction", "side", "type"], "BUY").upper(),
                "entry_date":   get(["entry_date", "date", "open_date"]),
                "entry_time":   get(["entry_time", "open_time"], "09:30"),
                "entry_price":  float(get(["entry_price", "buy_price", "open_price"], "0")),
                "exit_date":    get(["exit_date", "close_date", "sell_date"],
                                    get(["entry_date", "date"])),
                "exit_time":    get(["exit_time", "close_time"], "15:30"),
                "exit_price":   float(get(["exit_price", "sell_price", "close_price"], "0")),
                "quantity":     float(get(["quantity", "qty", "shares", "size"], "1")),
                "setup_type":   get(["setup_type", "setup", "strategy"], "Unknown"),
                "notes":        get(["notes", "note", "comment", "reason"], ""),
                "stop_loss":    float(get(["stop_loss", "stop", "sl"], "0") or "0"),
            }

            # Use stored P&L from CSV; fall back to calculation if absent
            csv_pnl = get(["pnl_eur", "pnl"])
            if csv_pnl:
                try:
                    trade["pnl"] = float(csv_pnl)
                except (ValueError, TypeError):
                    csv_pnl = None
            if not csv_pnl:
                if trade["direction"] in ["BUY", "LONG", "COVER"]:
                    trade["pnl"] = (trade["exit_price"] - trade["entry_price"]) * trade["quantity"]
                else:
                    trade["pnl"] = (trade["entry_price"] - trade["exit_price"]) * trade["quantity"]

            # Use stored R-multiple from CSV; fall back to calculation if absent
            csv_r = get(["r_multiple"])
            if csv_r:
                try:
                    trade["r_multiple"] = float(csv_r)
                except (ValueError, TypeError):
                    csv_r = None
            if not csv_r:
                if trade["stop_loss"] > 0:
                    risk_per_share = abs(trade["entry_price"] - trade["stop_loss"])
                    if risk_per_share > 0:
                        pnl_per_share = abs(trade["exit_price"] - trade["entry_price"])
                        trade["r_multiple"] = round(
                            (pnl_per_share / risk_per_share) * (1 if trade["pnl"] >= 0 else -1), 2
                        )
                    else:
                        trade["r_multiple"] = None
                else:
                    trade["r_multiple"] = None

            trades.append(trade)

    print(f"  Loaded {len(trades)} trades from {csv_file}")
    return trades


# ─────────────────────────────────────────────
# 2. FETCH HISTORICAL DATA + SECTOR
# ─────────────────────────────────────────────

def fetch_chart_data(ticker: str, entry_date: str, exit_date: str) -> tuple:
    """
    Fetch OHLCV data around the trade window.
    Returns (price_df, sector_name, sector_change_pct)
    """
    try:
        entry_dt = datetime.strptime(entry_date, "%Y-%m-%d")
        exit_dt  = datetime.strptime(exit_date,  "%Y-%m-%d")
        start    = (entry_dt - timedelta(days=30)).strftime("%Y-%m-%d")
        end      = (exit_dt  + timedelta(days=5)).strftime("%Y-%m-%d")

        stock = yf.Ticker(ticker)
        df    = stock.history(start=start, end=end, interval="1d")

        if df.empty:
            return None, "Unknown", 0.0

        # Sector performance on trade day
        sector_name   = "DAX"
        sector_change = 0.0
        sector_ticker = SECTOR_MAP.get(ticker, ("Unknown", "^GDAXI"))[1]
        sector_name   = SECTOR_MAP.get(ticker, ("Unknown", "^GDAXI"))[0]

        try:
            sec      = yf.Ticker(sector_ticker)
            sec_df   = sec.history(start=entry_date, end=(exit_dt + timedelta(days=2)).strftime("%Y-%m-%d"))
            if not sec_df.empty and len(sec_df) >= 1:
                sec_open  = sec_df["Open"].iloc[0]
                sec_close = sec_df["Close"].iloc[-1]
                sector_change = round(((sec_close - sec_open) / sec_open) * 100, 2)
        except Exception:
            pass

        return df, sector_name, sector_change

    except Exception as e:
        print(f"  Could not fetch data for {ticker}: {e}")
        return None, "Unknown", 0.0


# ─────────────────────────────────────────────
# 3. GENERATE CHART IMAGE (base64)
# ─────────────────────────────────────────────

def generate_chart_image(df: pd.DataFrame, trade: dict) -> str:
    """
    Draw a clean candlestick chart with entry/exit markers.
    Returns base64 encoded PNG string.
    """
    try:
        entry_dt = datetime.strptime(trade["entry_date"], "%Y-%m-%d")
        exit_dt  = datetime.strptime(trade["exit_date"],  "%Y-%m-%d")

        # Use last 25 candles around trade
        df_plot = df.tail(25).copy()

        fig, (ax1, ax2) = plt.subplots(
            2, 1, figsize=(10, 6),
            gridspec_kw={"height_ratios": [3, 1]},
            facecolor="#0d1117"
        )

        for ax in [ax1, ax2]:
            ax.set_facecolor("#0d1117")
            ax.tick_params(colors="#888", labelsize=8)
            ax.spines["bottom"].set_color("#333")
            ax.spines["top"].set_visible(False)
            ax.spines["right"].set_visible(False)
            ax.spines["left"].set_color("#333")

        # Draw candlesticks manually
        dates  = range(len(df_plot))
        opens  = df_plot["Open"].values
        highs  = df_plot["High"].values
        lows   = df_plot["Low"].values
        closes = df_plot["Close"].values
        vols   = df_plot["Volume"].values

        for i, (o, h, l, c) in enumerate(zip(opens, highs, lows, closes)):
            color  = "#00c853" if c >= o else "#ff3d00"
            ax1.plot([i, i], [l, h], color=color, linewidth=0.8, alpha=0.9)
            ax1.add_patch(plt.Rectangle(
                (i - 0.3, min(o, c)), 0.6, abs(c - o),
                color=color, alpha=0.9
            ))

        # Volume bars
        for i, (c, o, v) in enumerate(zip(closes, opens, vols)):
            color = "#00c85355" if c >= o else "#ff3d0055"
            ax2.bar(i, v, color=color, width=0.8)

        # Entry/exit vertical lines
        date_index = list(df_plot.index.strftime("%Y-%m-%d"))

        def find_idx(target_date):
            target_str = target_date.strftime("%Y-%m-%d")
            for i, d in enumerate(date_index):
                if d >= target_str:
                    return i
            return len(date_index) - 1

        entry_idx = find_idx(entry_dt)
        exit_idx  = find_idx(exit_dt)

        ax1.axvline(entry_idx, color="#00e5ff", linewidth=1.5,
                    linestyle="--", alpha=0.9, label=f"Entry €{trade['entry_price']}")
        ax1.axvline(exit_idx,  color="#ff6d00", linewidth=1.5,
                    linestyle="--", alpha=0.9, label=f"Exit €{trade['exit_price']}")

        # Entry/exit price horizontal lines
        ax1.axhline(trade["entry_price"], color="#00e5ff",
                    linewidth=0.6, linestyle=":", alpha=0.5)
        ax1.axhline(trade["exit_price"],  color="#ff6d00",
                    linewidth=0.6, linestyle=":", alpha=0.5)

        # Stop loss line if available
        if trade["stop_loss"] > 0:
            ax1.axhline(trade["stop_loss"], color="#ff1744",
                        linewidth=0.8, linestyle="-.", alpha=0.7, label=f"Stop €{trade['stop_loss']}")

        # Labels
        ticker_display = trade["ticker"].replace(".DE", "")
        pnl_sign  = "+" if trade["pnl"] >= 0 else ""
        pnl_color = "#00c853" if trade["pnl"] >= 0 else "#ff3d00"
        ax1.set_title(
            f"{ticker_display} — {trade['setup_type']} | "
            f"{trade['entry_date']} → {trade['exit_date']} | "
            f"P&L: {pnl_sign}€{trade['pnl']:.2f}",
            color="#e0e0e0", fontsize=10, pad=8
        )

        # X axis date labels
        step = max(1, len(df_plot) // 6)
        ax1.set_xticks(range(0, len(df_plot), step))
        ax1.set_xticklabels(
            [date_index[i] for i in range(0, len(df_plot), step)],
            rotation=30, ha="right", color="#666", fontsize=7
        )
        ax2.set_xticks(range(0, len(df_plot), step))
        ax2.set_xticklabels(
            [date_index[i] for i in range(0, len(df_plot), step)],
            rotation=30, ha="right", color="#666", fontsize=7
        )

        ax1.set_ylabel("Price (€)", color="#888", fontsize=8)
        ax2.set_ylabel("Volume",    color="#888", fontsize=8)
        ax1.legend(fontsize=8, facecolor="#1a1a2e",
                   labelcolor="#ccc", edgecolor="#333")

        plt.tight_layout(pad=1.5)

        buf = BytesIO()
        plt.savefig(buf, format="png", dpi=130,
                    bbox_inches="tight", facecolor="#0d1117")
        plt.close(fig)
        buf.seek(0)
        return base64.b64encode(buf.read()).decode("utf-8")

    except Exception as e:
        print(f"  Chart generation failed: {e}")
        return ""


# ─────────────────────────────────────────────
# 4. AI ANALYSIS PER TRADE
# ─────────────────────────────────────────────

def analyse_trade_with_ai(trade: dict, sector_name: str, sector_change: float, chart_b64: str) -> dict:
    """Send chart image + trade data to Claude for deep analysis."""
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    direction_label = "long" if trade["direction"] in ["BUY", "LONG"] else "short"
    result          = "WIN" if trade["pnl"] > 0 else "LOSS" if trade["pnl"] < 0 else "BREAKEVEN"
    r_text          = f"{trade['r_multiple']}R" if trade["r_multiple"] else "No stop loss defined"
    sector_dir      = "WITH" if (
        (sector_change > 0 and trade["pnl"] > 0) or
        (sector_change < 0 and trade["pnl"] < 0)
    ) else "AGAINST"

    prompt = f"""You are a professional trading coach analysing a German XETRA trade.

Trade data:
- Ticker: {trade['ticker']} ({sector_name} sector)
- Direction: {direction_label}
- Setup claimed: {trade['setup_type']}
- Entry: €{trade['entry_price']} on {trade['entry_date']} at {trade['entry_time']}
- Exit: €{trade['exit_price']} on {trade['exit_date']} at {trade['exit_time']}
- Quantity: {trade['quantity']} shares
- P&L: €{trade['pnl']:.2f} ({result})
- R-Multiple: {r_text}
- Stop loss: {"€" + str(trade['stop_loss']) if trade['stop_loss'] > 0 else "Not defined"}
- Sector ({sector_name}) moved {sector_change:+.2f}% during trade — trader went {direction_label} {sector_dir} sector
- Trader notes: "{trade['notes']}"

The chart image is attached. Analyse it carefully — look at the price action, volume, trend context, and exactly where the entry and exit lines fall on the chart.

Respond ONLY with a valid JSON object, no markdown, no extra text:
{{
  "setup_confirmed": true or false,
  "entry_timing": "one of: Perfect, Good, Acceptable, Late, Very Late, Too Early",
  "exit_timing": "one of: Perfect, Good, Acceptable, Early, Very Early, Late, Too Late",
  "skill_vs_luck": "one of: Pure Skill, Mostly Skill, Mixed, Mostly Luck, Pure Luck",
  "discipline_score": <integer 1-10>,
  "trade_grade": "one of: A, B, C, D, F",
  "sector_alignment": "one of: Confirmed, Neutral, Against",
  "risk_reward_rating": "one of: Excellent, Good, Acceptable, Poor, No Stop Defined",
  "chart_analysis": "<2-3 sentences describing exactly what you see on the chart at the entry and exit points>",
  "mistakes": ["<specific mistake 1>", "<specific mistake 2>", "<specific mistake 3 if any>"],
  "next_time": "<one clear actionable rule for next time this setup appears>",
  "coaching_note": "<3-5 sentences of direct, honest coaching — reference specific chart observations, be constructive but brutally honest>"
}}"""

    # Build message with or without chart image
    if chart_b64:
        content = [
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": chart_b64
                }
            },
            {"type": "text", "text": prompt}
        ]
    else:
        content = [{"type": "text", "text": prompt}]

    try:
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1200,
            messages=[{"role": "user", "content": content}]
        )
        raw = _strip_markdown_fences(message.content[0].text)
        return json.loads(raw)
    except Exception as e:
        print(f"  AI analysis failed: {e}")
        return {
            "setup_confirmed": False,
            "entry_timing": "Unknown",
            "exit_timing": "Unknown",
            "skill_vs_luck": "Unknown",
            "discipline_score": 0,
            "trade_grade": "?",
            "sector_alignment": "Unknown",
            "risk_reward_rating": "Unknown",
            "chart_analysis": "Analysis unavailable.",
            "mistakes": [],
            "next_time": "",
            "coaching_note": "Analysis unavailable."
        }


# ─────────────────────────────────────────────
# 5. OVERALL COACHING SUMMARY
# ─────────────────────────────────────────────

def generate_overall_summary(trades: list, analyses: list) -> str:
    """Ask Claude to give an overall coaching summary across all trades."""
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    trade_summaries = ""
    for t, a in zip(trades, analyses):
        trade_summaries += f"""
- {t['ticker']} {t['setup_type']} | P&L €{t['pnl']:.2f} | Grade {a.get('trade_grade','?')} | Discipline {a.get('discipline_score',0)}/10 | {a.get('skill_vs_luck','?')} | Entry: {a.get('entry_timing','?')} | Mistakes: {'; '.join(a.get('mistakes', [])[:1])}"""

    prompt = f"""You are a senior trading coach reviewing a full week/month of trades from a developing German market trader.

Here is the complete trade history summary:
{trade_summaries}

Write a coaching summary (4-6 sentences) that:
1. Identifies the single biggest pattern mistake across ALL trades
2. Highlights what the trader is doing right
3. Gives the top 3 specific rules they must implement immediately
4. Ends with one motivational but honest closing statement

Be direct, specific, and reference the actual trades. No generic advice."""

    try:
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}]
        )
        return msg.content[0].text.strip()
    except Exception:
        return "Overall analysis unavailable."


# ─────────────────────────────────────────────
# 6. BUILD HTML REPORT
# ─────────────────────────────────────────────

def build_html_report(trades: list, analyses: list, overall_summary: str) -> str:
    """Build the full HTML coaching report."""

    today        = datetime.now().strftime("%B %d, %Y")
    total_pnl    = sum(t["pnl"] for t in trades)
    wins         = sum(1 for t in trades if t["pnl"] > 0)
    losses       = sum(1 for t in trades if t["pnl"] < 0)
    win_rate     = round(wins / len(trades) * 100, 1) if trades else 0
    avg_disc     = round(sum(a.get("discipline_score", 0) for a in analyses) / len(analyses), 1) if analyses else 0
    skill_trades = sum(1 for a in analyses if a.get("skill_vs_luck", "") in ["Pure Skill", "Mostly Skill"])
    pnl_color    = "#00c853" if total_pnl >= 0 else "#ff3d00"
    pnl_sign     = "+" if total_pnl >= 0 else ""

    # Grade colors
    GRADE_COLORS = {
        "A": ("#00c85320", "#00c853"),
        "B": ("#00e5ff20", "#00e5ff"),
        "C": ("#ff660020", "#ff6600"),
        "D": ("#ff3d0020", "#ff3d00"),
        "F": ("#ff000020", "#ff0000"),
        "?": ("#33333320", "#666666"),
    }

    # Build trade cards
    trade_cards = ""
    for i, (trade, analysis) in enumerate(zip(trades, analyses), 1):
        grade        = analysis.get("trade_grade", "?")
        gbg, gfg     = GRADE_COLORS.get(grade, ("#33333320", "#666"))
        confirmed    = analysis.get("setup_confirmed", False)
        conf_color   = "#00c853" if confirmed else "#ff3d00"
        conf_label   = "Setup Confirmed" if confirmed else "Setup Not Confirmed"
        pnl_c        = "#00c853" if trade["pnl"] >= 0 else "#ff3d00"
        pnl_s        = "+" if trade["pnl"] >= 0 else ""
        direction    = trade["direction"]
        dir_color    = "#00c853" if direction in ["BUY", "LONG"] else "#ff6d00"
        ticker_disp  = trade["ticker"].replace(".DE", "")
        disc         = analysis.get("discipline_score", 0)
        disc_color   = "#00c853" if disc >= 7 else "#ff6600" if disc >= 4 else "#ff3d00"
        sector_aln   = analysis.get("sector_alignment", "Unknown")
        sec_color    = "#00c853" if sector_aln == "Confirmed" else "#ff6600" if sector_aln == "Neutral" else "#ff3d00"
        rrr          = analysis.get("risk_reward_rating", "Unknown")
        r_text       = f"{trade['r_multiple']}R" if trade["r_multiple"] else "No Stop"
        mistakes_html = "".join(f"<li>{m}</li>" for m in analysis.get("mistakes", []))
        chart_html   = (
            f'<img src="data:image/png;base64,{trade.get("chart_b64","")}" '
            f'style="width:100%;border-radius:8px;display:block" alt="Chart">'
            if trade.get("chart_b64") else
            '<div style="height:200px;display:flex;align-items:center;'
            'justify-content:center;color:#555;font-size:13px">Chart unavailable</div>'
        )

        trade_cards += f"""
        <div class="trade-card">
          <div class="trade-header">
            <div class="trade-title">
              <span class="trade-num">#{i}</span>
              <span class="ticker">{ticker_disp}</span>
              <span class="badge" style="background:#1e2a3a;color:#4a9eff;border:1px solid #4a9eff44">{trade['setup_type']}</span>
              <span class="badge" style="background:#1a2a1a;color:{dir_color};border:1px solid {dir_color}44">{direction}</span>
              <span class="badge" style="background:#111;color:{conf_color};border:1px solid {conf_color}44">{conf_label}</span>
            </div>
            <div style="display:flex;align-items:center;gap:12px">
              <span style="color:{pnl_c};font-weight:700;font-size:18px">{pnl_s}€{abs(trade['pnl']):.2f}</span>
              <span class="grade-badge" style="background:{gbg};color:{gfg};border:1px solid {gfg}">Grade {grade}</span>
            </div>
          </div>

          <div class="trade-body">
            <div class="chart-col">
              {chart_html}
              <div class="meta-row">
                <span class="meta-item">{trade['entry_date']} {trade['entry_time']}</span>
                <span class="meta-item">to {trade['exit_date']} {trade['exit_time']}</span>
                <span class="meta-item">{int(trade['quantity'])} shares</span>
              </div>
            </div>

            <div class="analysis-col">
              <div class="metrics-grid">
                <div class="metric">
                  <div class="metric-label">Entry Timing</div>
                  <div class="metric-value">{analysis.get('entry_timing','?')}</div>
                </div>
                <div class="metric">
                  <div class="metric-label">Exit Timing</div>
                  <div class="metric-value">{analysis.get('exit_timing','?')}</div>
                </div>
                <div class="metric">
                  <div class="metric-label">Skill vs Luck</div>
                  <div class="metric-value">{analysis.get('skill_vs_luck','?')}</div>
                </div>
                <div class="metric">
                  <div class="metric-label">Discipline</div>
                  <div class="metric-value" style="color:{disc_color}">{disc}/10</div>
                </div>
                <div class="metric">
                  <div class="metric-label">Sector</div>
                  <div class="metric-value" style="color:{sec_color}">{sector_aln}</div>
                </div>
                <div class="metric">
                  <div class="metric-label">Risk/Reward</div>
                  <div class="metric-value">{rrr} ({r_text})</div>
                </div>
              </div>

              <div class="section-label">Chart Analysis</div>
              <p class="feedback-text">{analysis.get('chart_analysis','')}</p>

              <div class="section-label">Mistakes</div>
              <ul class="mistakes-list">{mistakes_html}</ul>

              <div class="section-label">Next Time</div>
              <p class="next-time-text">{analysis.get('next_time','')}</p>

              <div class="coaching-box">
                <div class="section-label" style="margin-top:0">Coaching Note</div>
                <p>{analysis.get('coaching_note','')}</p>
              </div>
            </div>
          </div>
        </div>"""

    # Overall summary section
    summary_html = overall_summary.replace("\n", "<br>")

    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>Chart Analysis Report — {today}</title>
<style>
  * {{ box-sizing:border-box; margin:0; padding:0; }}
  body {{ font-family:-apple-system,sans-serif; background:#0a0a0f; color:#e0e0e0; padding:24px; }}
  .header {{ background:linear-gradient(135deg,#1a1a2e,#16213e); border:1px solid #333; border-radius:12px; padding:28px 32px; margin-bottom:24px; }}
  .header h1 {{ font-size:24px; color:#fff; margin-bottom:4px; }}
  .header p {{ color:#888; font-size:14px; }}
  .summary {{ display:grid; grid-template-columns:repeat(5,1fr); gap:16px; margin-bottom:24px; }}
  .summary-card {{ background:#12121a; border:1px solid #333; border-radius:10px; padding:18px; text-align:center; }}
  .summary-card .val {{ font-size:26px; font-weight:700; color:#4a9eff; }}
  .summary-card .lbl {{ font-size:11px; color:#888; margin-top:4px; }}
  .overall-box {{ background:#12121a; border:1px solid #4a9eff44; border-left:3px solid #4a9eff; border-radius:12px; padding:20px 24px; margin-bottom:24px; }}
  .overall-box h2 {{ font-size:14px; color:#4a9eff; margin-bottom:10px; text-transform:uppercase; letter-spacing:0.06em; }}
  .overall-box p {{ font-size:14px; color:#bbb; line-height:1.75; }}
  .trade-card {{ background:#12121a; border:1px solid #2a2a3a; border-radius:12px; margin-bottom:24px; overflow:hidden; }}
  .trade-header {{ display:flex; justify-content:space-between; align-items:center; padding:14px 20px; background:#16161f; border-bottom:1px solid #2a2a3a; flex-wrap:wrap; gap:8px; }}
  .trade-title {{ display:flex; align-items:center; gap:8px; flex-wrap:wrap; }}
  .trade-num {{ color:#555; font-size:13px; }}
  .ticker {{ font-size:20px; font-weight:700; color:#fff; }}
  .badge {{ font-size:11px; padding:3px 10px; border-radius:99px; }}
  .grade-badge {{ padding:4px 14px; border-radius:99px; font-size:13px; font-weight:600; }}
  .trade-body {{ display:grid; grid-template-columns:1.5fr 1fr; }}
  .chart-col {{ padding:16px; border-right:1px solid #2a2a3a; }}
  .analysis-col {{ padding:16px; }}
  .meta-row {{ display:flex; gap:12px; flex-wrap:wrap; margin-top:10px; }}
  .meta-item {{ font-size:11px; color:#666; }}
  .metrics-grid {{ display:grid; grid-template-columns:1fr 1fr; gap:8px; margin-bottom:14px; }}
  .metric {{ background:#1a1a25; border:1px solid #2a2a3a; border-radius:8px; padding:10px; }}
  .metric-label {{ font-size:10px; color:#555; text-transform:uppercase; letter-spacing:0.05em; margin-bottom:3px; }}
  .metric-value {{ font-size:13px; color:#ccc; font-weight:500; }}
  .section-label {{ font-size:10px; color:#555; text-transform:uppercase; letter-spacing:0.08em; margin:12px 0 5px; }}
  .feedback-text {{ font-size:13px; color:#999; line-height:1.6; }}
  .mistakes-list {{ padding-left:16px; font-size:13px; color:#ff8888; line-height:1.8; }}
  .next-time-text {{ font-size:13px; color:#88ddff; line-height:1.6; }}
  .coaching-box {{ background:#1a1a2e; border-left:3px solid #4a9eff; border-radius:0 8px 8px 0; padding:12px; margin-top:12px; font-size:13px; color:#bbb; line-height:1.7; }}
  .footer {{ text-align:center; color:#444; font-size:12px; margin-top:32px; padding-top:16px; border-top:1px solid #1a1a1a; }}
  @media(max-width:800px) {{
    .trade-body {{ grid-template-columns:1fr; }}
    .chart-col {{ border-right:none; border-bottom:1px solid #2a2a3a; }}
    .summary {{ grid-template-columns:repeat(2,1fr); }}
  }}
</style>
</head>
<body>

<div class="header">
  <h1>Chart Analysis — Trade Coaching Report</h1>
  <p>German Market (XETRA) · Generated {today} · {len(trades)} trades analysed</p>
</div>

<div class="summary">
  <div class="summary-card">
    <div class="val">{wins}/{len(trades)}</div>
    <div class="lbl">Win Rate ({win_rate}%)</div>
  </div>
  <div class="summary-card">
    <div class="val" style="color:{pnl_color}">{pnl_sign}€{abs(total_pnl):.0f}</div>
    <div class="lbl">Total P&L</div>
  </div>
  <div class="summary-card">
    <div class="val" style="color:{'#ff3d00' if avg_disc < 5 else '#ff6600' if avg_disc < 7 else '#00c853'}">{avg_disc}/10</div>
    <div class="lbl">Avg Discipline</div>
  </div>
  <div class="summary-card">
    <div class="val">{skill_trades}/{len(trades)}</div>
    <div class="lbl">Skill-Based Trades</div>
  </div>
  <div class="summary-card">
    <div class="val">{sum(1 for a in analyses if a.get('setup_confirmed'))}/{len(trades)}</div>
    <div class="lbl">Setups Confirmed</div>
  </div>
</div>

<div class="overall-box">
  <h2>Overall Coaching Summary</h2>
  <p>{summary_html}</p>
</div>

{trade_cards}

<div class="footer">
  Chart Analysis Agent · German Market Edition · {today}
</div>

</body>
</html>"""

    return html


# ─────────────────────────────────────────────
# 7. SEND EMAIL
# ─────────────────────────────────────────────

def send_email(html_content: str, output_file: str):
    """Send HTML report via Gmail."""
    if not all([EMAIL_SENDER, EMAIL_PASSWORD, EMAIL_RECEIVER]):
        print("  Email credentials not set in .env — skipping email")
        return

    today = datetime.now().strftime("%b %d, %Y")
    msg   = MIMEMultipart("alternative")
    msg["Subject"] = f"Trade Chart Analysis Report — {today}"
    msg["From"]    = EMAIL_SENDER
    msg["To"]      = EMAIL_RECEIVER
    msg.attach(MIMEText(html_content, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.sendmail(EMAIL_SENDER, EMAIL_RECEIVER, msg.as_string())
        print(f"  Report emailed to {EMAIL_RECEIVER}")
    except Exception as e:
        print(f"  Email failed: {e}")


# ─────────────────────────────────────────────
# 8. MAIN
# ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Trade Chart Analysis Agent")
    parser.add_argument("--csv",   default="trades.csv", help="CSV file to analyse")
    parser.add_argument("--email", action="store_true",          help="Email the report")
    parser.add_argument("--out",   default="chart_report.html",  help="Output HTML file")
    args = parser.parse_args()

    print("\n" + "="*55)
    print("  Trade Chart Analysis Agent — German Market")
    print("="*55 + "\n")

    if not ANTHROPIC_API_KEY:
        raise ValueError("Missing ANTHROPIC_API_KEY in .env file")

    # Load trades
    trades   = load_trades(args.csv)
    analyses = []

    for i, trade in enumerate(trades, 1):
        ticker = trade["ticker"]
        print(f"[{i}/{len(trades)}] Analysing {ticker} — {trade['entry_date']}...")

        # Fetch chart data
        df, sector_name, sector_change = fetch_chart_data(
            ticker, trade["entry_date"], trade["exit_date"]
        )

        # Generate chart image
        chart_b64 = ""
        if df is not None and not df.empty:
            print(f"  Generating chart...")
            chart_b64 = generate_chart_image(df, trade)

        trade["chart_b64"] = chart_b64

        # AI analysis
        print(f"  Running AI analysis...")
        analysis = analyse_trade_with_ai(trade, sector_name, sector_change, chart_b64)
        analyses.append(analysis)

        grade = analysis.get("trade_grade", "?")
        disc  = analysis.get("discipline_score", 0)
        skill = analysis.get("skill_vs_luck", "?")
        print(f"  Grade {grade} | Discipline {disc}/10 | {skill}")

    # Overall coaching summary
    print("\n  Generating overall coaching summary...")
    overall_summary = generate_overall_summary(trades, analyses)

    # Build HTML
    print("  Building HTML report...")
    html = build_html_report(trades, analyses, overall_summary)

    # Save report
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  Report saved: {args.out}")

    # Email if requested
    if args.email:
        print("  Sending email...")
        send_email(html, args.out)

    print(f"\n{'='*55}")
    print(f"  Done! Open {args.out} in your browser.")
    print(f"{'='*55}\n")


if __name__ == "__main__":
    main()
"""
strategy_builder.py - No-Code Strategy Builder
==============================================
Type your trading strategy in plain English.
Claude converts it into executable rules.
The agent backtests it across the full watchlist
(DAX 40, German indexes, crypto, commodities)
and generates an HTML report.

Usage:
    python strategy_builder.py              # plain English input
    python strategy_builder.py --template   # choose from pre-built templates
    python strategy_builder.py --both       # choose method interactively
"""

import os
import json
import base64
import argparse
from io import BytesIO
from datetime import datetime

import anthropic
import yfinance as yf
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from dotenv import load_dotenv

load_dotenv()
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# ---------------------------------------------
# WATCHLIST
# ---------------------------------------------

# Full DAX 40 - German blue chips
DAX40 = [
    "SAP.DE",  "SIE.DE",  "ALV.DE",  "MUV2.DE", "DTE.DE",
    "BMW.DE",  "MBG.DE",  "VOW3.DE", "PAH3.DE", "CON.DE",
    "BAS.DE",  "1COV.DE", "BAYN.DE", "MRK.DE",  "QGEN.DE",
    "DBK.DE",  "DB1.DE",  "IFX.DE",  "INL.DE",  "BNR.DE",
    "ADS.DE",  "BEI.DE",  "HEN3.DE", "ZAL.DE",  "DHER.DE",
    "DHL.DE",  "AIR.DE",  "MTX.DE",  "SY1.DE",  "RHM.DE",
    "EOAN.DE", "RWE.DE",  "HEI.DE",  "SHL.DE",  "FRE.DE",
    "VNA.DE",  "HFG.DE",  "EVT.DE",  "P911.DE", "ENR.DE",
]

# German market indexes
GERMAN_INDEXES = [
    "^GDAXI",   # DAX 40
    "^MDAXI",   # MDAX
    "^SDAXI",   # SDAX
    "^TECDAX",  # TecDAX
]

# Crypto
CRYPTO = [
    "BTC-USD",  # Bitcoin
    "ETH-USD",  # Ethereum
    "SOL-USD",  # Solana
    "BNB-USD",  # BNB
    "XRP-USD",  # XRP
]

# Commodities
COMMODITIES = [
    "GC=F",     # Gold
    "CL=F",     # Crude Oil
    "SI=F",     # Silver
    "NG=F",     # Natural Gas
    "HG=F",     # Copper
]

WATCHLIST = DAX40 + GERMAN_INDEXES + CRYPTO + COMMODITIES

ASSET_LABELS = {
    **{t: "DAX 40"      for t in DAX40},
    **{t: "German Index" for t in GERMAN_INDEXES},
    **{t: "Crypto"      for t in CRYPTO},
    **{t: "Commodity"   for t in COMMODITIES},
}

# ---------------------------------------------
# PRE-BUILT TEMPLATES
# ---------------------------------------------

TEMPLATES = {
    "1": {
        "name": "RSI Oversold Bounce",
        "description": "Buy when RSI drops below 30 (oversold) and price is above the 200 EMA. Sell when RSI rises above 70 or price drops 3% from entry.",
    },
    "2": {
        "name": "EMA Crossover",
        "description": "Buy when the 21 EMA crosses above the 50 EMA with volume above average. Sell when 21 EMA crosses back below 50 EMA.",
    },
    "3": {
        "name": "Breakout with Volume",
        "description": "Buy when price breaks above the 20-day high with volume at least 1.5x the 20-day average. Sell when price drops 2% below the breakout level.",
    },
    "4": {
        "name": "Pullback to 21 EMA",
        "description": "Buy when price pulls back to within 1% of the 21 EMA in an uptrend (price above 50 EMA). Sell when price hits 3x the initial risk or drops below the 50 EMA.",
    },
    "5": {
        "name": "Momentum Surge",
        "description": "Buy when price rises more than 2% in one day with volume above 2x average and RSI between 55 and 75. Sell after 5 days or when RSI drops below 50.",
    },
}


# ---------------------------------------------
# 1. GET STRATEGY FROM USER
# ---------------------------------------------

def get_strategy_from_text() -> str:
    """Get strategy description from plain English input."""
    print("\n" + "-" * 55)
    print("  Plain English Strategy Input")
    print("-" * 55)
    print("  Describe your trading strategy in plain English.")
    print("  Be specific about entry conditions, exit conditions,")
    print("  and any indicators you want to use.\n")
    print("  Examples:")
    print("  - 'Buy when RSI drops below 30 and sell when it hits 70'")
    print("  - 'Buy breakouts above 20-day high with volume surge'")
    print("  - 'Buy pullbacks to 21 EMA when trend is up'\n")

    return input("  Your strategy: ").strip()


def get_strategy_from_template() -> str:
    """Let user choose from pre-built templates."""
    print("\n" + "-" * 55)
    print("  Pre-Built Strategy Templates")
    print("-" * 55)

    for key, template in TEMPLATES.items():
        print(f"\n  [{key}] {template['name']}")
        print(f"      {template['description'][:80]}...")

    print()
    choice = ""
    while choice not in TEMPLATES:
        choice = input("  Choose template (1-5): ").strip()

    selected = TEMPLATES[choice]
    print(f"\n  Selected: {selected['name']}")
    return selected["description"]


def get_strategy(mode: str) -> tuple:
    """Get strategy based on selected mode."""
    if mode == "template":
        return get_strategy_from_template(), "Template"
    if mode == "text":
        return get_strategy_from_text(), "Plain English"

    print("\n  How do you want to enter your strategy?")
    print("  [1] Type in plain English")
    print("  [2] Choose from pre-built templates")
    choice = input("\n  Choose (1 or 2): ").strip()
    if choice == "2":
        return get_strategy_from_template(), "Template"
    return get_strategy_from_text(), "Plain English"


# ---------------------------------------------
# 2. CONVERT STRATEGY TO RULES USING CLAUDE
# ---------------------------------------------

def parse_strategy_with_ai(strategy_text: str) -> dict:
    """Send strategy to Claude and return structured executable rules."""
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    prompt = f"""You are a quantitative trading expert. Convert this trading strategy description into precise, executable rules.

Strategy description:
"{strategy_text}"

Respond ONLY with a valid JSON object. No markdown, no extra text:
{{
  "strategy_name": "short descriptive name",
  "strategy_type": "one of: Momentum, Mean-Reversion, Breakout, Pullback, Trend-Follow",
  "entry_conditions": [
    {{
      "indicator": "RSI | EMA21 | EMA50 | EMA200 | MACD | volume_surge | price_change_pct | above_high20 | below_low20",
      "operator": "< | > | <= | >= | crosses_above | crosses_below",
      "value": <number or indicator name as string>
    }}
  ],
  "exit_conditions": [
    {{
      "type": "stop_loss_pct | take_profit_pct | indicator | days_held",
      "operator": "< | > | crosses_above | crosses_below | ==",
      "value": <number>
    }}
  ],
  "direction": "LONG | SHORT",
  "holding_period": <estimated days as integer>,
  "description": "plain English summary of the strategy rules",
  "risk_per_trade_pct": <suggested risk % as number between 1 and 3>
}}"""

    try:
        msg = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=800,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = msg.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw.strip())
    except Exception as e:
        print(f"  AI parsing failed: {e}")
        return {
            "strategy_name":      "Custom Strategy",
            "strategy_type":      "Unknown",
            "entry_conditions":   [],
            "exit_conditions":    [],
            "direction":          "LONG",
            "holding_period":     5,
            "description":        strategy_text,
            "risk_per_trade_pct": 2.0,
        }


# ---------------------------------------------
# 3. FETCH DATA AND CALCULATE INDICATORS
# ---------------------------------------------

def fetch_and_calculate(ticker: str) -> pd.DataFrame | None:
    """Fetch 2 years of data and calculate all indicators."""
    try:
        df = yf.Ticker(ticker).history(period="2y", interval="1d")
        if df.empty or len(df) < 50:
            return None

        close  = df["Close"]
        high   = df["High"]
        low    = df["Low"]
        volume = df["Volume"]

        # EMAs
        df["EMA21"]  = close.ewm(span=21,  adjust=False).mean()
        df["EMA50"]  = close.ewm(span=50,  adjust=False).mean()
        df["EMA200"] = close.ewm(span=200, adjust=False).mean()

        # RSI (Wilder, period 14)
        delta = close.diff()
        gain  = delta.clip(lower=0).ewm(com=13, adjust=False).mean()
        loss  = (-delta.clip(upper=0)).ewm(com=13, adjust=False).mean()
        rs    = gain / loss.replace(0, 1e-10)
        df["RSI"] = 100 - (100 / (1 + rs))

        # MACD
        ema12          = close.ewm(span=12, adjust=False).mean()
        ema26          = close.ewm(span=26, adjust=False).mean()
        df["MACD"]     = ema12 - ema26
        df["MACD_sig"] = df["MACD"].ewm(span=9, adjust=False).mean()

        # Volume
        df["vol_ma20"]  = volume.rolling(20).mean()
        df["vol_surge"] = volume / df["vol_ma20"].replace(0, 1e-10)

        # Price
        df["change_pct"] = close.pct_change() * 100
        df["high20"]     = high.rolling(20).max()
        df["low20"]      = low.rolling(20).min()

        df.dropna(inplace=True)
        return df
    except Exception:
        return None


# ---------------------------------------------
# 4. EVALUATE ENTRY CONDITIONS
# ---------------------------------------------

def evaluate_conditions(row: pd.Series, prev_row: pd.Series, conditions: list) -> bool:
    """Check whether all entry conditions are met for the given row."""
    indicator_map = {
        "RSI":              row.get("RSI", 50),
        "EMA21":            row.get("EMA21", 0),
        "EMA50":            row.get("EMA50", 0),
        "EMA200":           row.get("EMA200", 0),
        "MACD":             row.get("MACD", 0),
        "volume_surge":     row.get("vol_surge", 1),
        "price_change_pct": row.get("change_pct", 0),
        "above_high20":     bool(row["Close"] >= row.get("high20", row["Close"] + 1)),
        "below_low20":      bool(row["Close"] <= row.get("low20", row["Close"] - 1)),
        "Close":            row["Close"],
    }

    prev_map = {
        "RSI":   prev_row.get("RSI", 50),
        "EMA21": prev_row.get("EMA21", 0),
        "EMA50": prev_row.get("EMA50", 0),
        "MACD":  prev_row.get("MACD", 0),
    }

    for cond in conditions or []:
        indicator = cond.get("indicator", "")
        operator  = cond.get("operator", ">")
        value     = cond.get("value", 0)

        left = indicator_map.get(indicator, 0)

        # Boolean indicators (above_high20, below_low20) must simply be True
        if isinstance(left, bool):
            if not left:
                return False
            continue

        # Resolve the right-hand side: may be a number or another indicator name
        try:
            right = float(indicator_map.get(str(value), value))
        except (TypeError, ValueError):
            right = 0.0

        if operator == "<"  and not (left <  right): return False
        if operator == ">"  and not (left >  right): return False
        if operator == "<=" and not (left <= right): return False
        if operator == ">=" and not (left >= right): return False

        if operator in ("crosses_above", "crosses_below"):
            prev_left = prev_map.get(indicator, left)
            if operator == "crosses_above" and not (prev_left <= right and left > right):
                return False
            if operator == "crosses_below" and not (prev_left >= right and left < right):
                return False

    return True


# ---------------------------------------------
# 5. RUN BACKTEST
# ---------------------------------------------

def _get_exit_value(exit_conditions: list, exit_type: str, default: float) -> float:
    """Safely look up an exit-rule value by type."""
    for c in exit_conditions or []:
        if c.get("type") == exit_type and c.get("value") is not None:
            return c["value"]
    return default


def run_backtest(df: pd.DataFrame, rules: dict, ticker: str) -> dict:
    """Run backtest on historical data using parsed rules."""
    trades       = []
    in_trade     = False
    entry_price  = 0.0
    entry_date   = None
    entry_idx    = 0

    direction    = rules.get("direction", "LONG")
    holding_days = rules.get("holding_period", 5)
    entry_rules  = rules.get("entry_conditions") or []
    exit_rules   = rules.get("exit_conditions")  or []

    stop_pct   = _get_exit_value(exit_rules, "stop_loss_pct",   3.0)
    target_pct = _get_exit_value(exit_rules, "take_profit_pct", 6.0)
    max_days   = _get_exit_value(exit_rules, "days_held",       holding_days)

    rows = list(df.iterrows())

    for i in range(1, len(rows)):
        date, row       = rows[i]
        _,    prev_row  = rows[i - 1]
        price           = row["Close"]

        if not in_trade:
            if evaluate_conditions(row, prev_row, entry_rules):
                in_trade    = True
                entry_price = price
                entry_date  = date
                entry_idx   = i
            continue

        # Open trade - check exits
        days_held = i - entry_idx
        pnl_pct = (
            (price - entry_price) / entry_price * 100
            if direction == "LONG"
            else (entry_price - price) / entry_price * 100
        )

        if pnl_pct <= -stop_pct:
            exit_reason = "Stop Loss"
        elif pnl_pct >= target_pct:
            exit_reason = "Take Profit"
        elif days_held >= max_days:
            exit_reason = "Time Exit"
        else:
            continue

        trades.append({
            "ticker":      ticker,
            "entry_date":  entry_date.strftime("%Y-%m-%d") if hasattr(entry_date, "strftime") else str(entry_date)[:10],
            "exit_date":   date.strftime("%Y-%m-%d")       if hasattr(date, "strftime")       else str(date)[:10],
            "entry_price": round(entry_price, 2),
            "exit_price":  round(price, 2),
            "days_held":   days_held,
            "pnl_pct":     round(pnl_pct, 2),
            "result":      "WIN" if pnl_pct > 0 else "LOSS",
            "exit_reason": exit_reason,
        })
        in_trade = False

    if not trades:
        return {"ticker": ticker, "trades": [], "stats": None}

    wins   = [t for t in trades if t["result"] == "WIN"]
    losses = [t for t in trades if t["result"] == "LOSS"]
    total  = len(trades)

    return {
        "ticker": ticker,
        "trades": trades,
        "stats": {
            "total_trades": total,
            "wins":         len(wins),
            "losses":       len(losses),
            "win_rate":     round(len(wins) / total * 100, 1),
            "avg_win":      round(sum(t["pnl_pct"] for t in wins)   / len(wins),   2) if wins   else 0,
            "avg_loss":     round(sum(t["pnl_pct"] for t in losses) / len(losses), 2) if losses else 0,
            "total_return": round(sum(t["pnl_pct"] for t in trades), 2),
            "best_trade":   max(trades, key=lambda t: t["pnl_pct"])["pnl_pct"],
            "worst_trade":  min(trades, key=lambda t: t["pnl_pct"])["pnl_pct"],
        },
    }


# ---------------------------------------------
# 6. GENERATE EQUITY CURVE CHART
# ---------------------------------------------

def generate_equity_chart(all_results: list) -> str:
    """Generate a combined equity curve for all tickers as a base64 PNG."""
    try:
        fig, ax = plt.subplots(figsize=(10, 4), facecolor="#0d1117")
        ax.set_facecolor("#0d1117")
        ax.tick_params(colors="#555", labelsize=8)
        for spine in ax.spines.values():
            spine.set_color("#222")

        colors = ["#00c853", "#4a9eff", "#ff6d00", "#e040fb",
                  "#ff3d00", "#00e5ff", "#ffcc00", "#ff6b9d"]

        for i, result in enumerate(all_results):
            if not result["trades"]:
                continue
            cumulative = 0.0
            x = [0]
            y = [0.0]
            for trade in result["trades"]:
                cumulative += trade["pnl_pct"]
                x.append(len(x))
                y.append(round(cumulative, 2))
            color = colors[i % len(colors)]
            ticker_disp = result["ticker"].replace(".DE", "")
            ax.plot(x, y, color=color, linewidth=1.5, alpha=0.8, label=ticker_disp)

        ax.axhline(0, color="#333", linewidth=0.8, linestyle="--")
        ax.set_title("Cumulative Return by Ticker (%)", color="#ccc", fontsize=10, pad=8)
        ax.set_ylabel("Return %", color="#555", fontsize=8)
        ax.set_xlabel("Trade #",  color="#555", fontsize=8)
        ax.legend(fontsize=7, facecolor="#111", labelcolor="#aaa",
                  edgecolor="#333", ncol=4, loc="upper left")
        plt.tight_layout(pad=1.5)

        buf = BytesIO()
        plt.savefig(buf, format="png", dpi=120, bbox_inches="tight", facecolor="#0d1117")
        plt.close(fig)
        buf.seek(0)
        return base64.b64encode(buf.read()).decode("utf-8")
    except Exception as e:
        print(f"  Chart error: {e}")
        return ""


# ---------------------------------------------
# 7. BUILD HTML REPORT
# ---------------------------------------------

def build_html_report(rules: dict, all_results: list,
                      strategy_text: str, method: str,
                      chart_b64: str) -> str:
    today = datetime.now().strftime("%A, %B %d %Y")
    now   = datetime.now().strftime("%H:%M CET")

    all_trades   = [t for r in all_results for t in r["trades"]]
    total_trades = len(all_trades)
    wins         = [t for t in all_trades if t["result"] == "WIN"]
    losses       = [t for t in all_trades if t["result"] == "LOSS"]
    win_rate     = round(len(wins) / total_trades * 100, 1) if total_trades else 0
    avg_return   = round(sum(t["pnl_pct"] for t in all_trades) / total_trades, 2) if all_trades else 0

    chart_html = (
        f'<img src="data:image/png;base64,{chart_b64}" '
        f'style="width:100%;border-radius:8px" alt="Equity Curve">'
        if chart_b64 else ""
    )

    sorted_results = sorted(
        [r for r in all_results if r["stats"]],
        key=lambda r: r["stats"]["total_return"],
        reverse=True,
    )

    ticker_cards = ""
    for r in sorted_results:
        s           = r["stats"]
        ticker_disp = r["ticker"].replace(".DE", "").replace("^", "").replace("-USD", "").replace("=F", "")
        asset_label = ASSET_LABELS.get(r["ticker"], "Stock")
        ret_color   = "#00c853" if s["total_return"] >= 0 else "#ff3d00"
        ret_sign    = "+" if s["total_return"] >= 0 else ""
        wr_color    = "#00c853" if s["win_rate"] >= 55 else "#ff6600" if s["win_rate"] >= 45 else "#ff3d00"

        trade_rows = ""
        for t in r["trades"][-5:]:
            pnl_c = "#00c853" if t["pnl_pct"] >= 0 else "#ff3d00"
            sign  = "+" if t["pnl_pct"] >= 0 else ""
            trade_rows += f"""
            <tr style="border-bottom:1px solid #2a2a3a;font-size:12px">
              <td style="padding:6px 10px;color:#888">{t['entry_date']}</td>
              <td style="padding:6px 10px;color:#888">{t['exit_date']}</td>
              <td style="padding:6px 10px">{t['entry_price']}</td>
              <td style="padding:6px 10px">{t['exit_price']}</td>
              <td style="padding:6px 10px;color:{pnl_c};font-weight:600">{sign}{t['pnl_pct']}%</td>
              <td style="padding:6px 10px;color:#888">{t['exit_reason']}</td>
            </tr>"""

        ticker_cards += f"""
        <div style="background:#12121a;border:1px solid #2a2a3a;border-radius:10px;margin-bottom:16px;overflow:hidden">
          <div style="display:flex;justify-content:space-between;align-items:center;padding:12px 18px;background:#16161f;border-bottom:1px solid #2a2a3a;flex-wrap:wrap;gap:8px">
            <div style="display:flex;align-items:center;gap:10px">
              <span style="font-size:18px;font-weight:700;color:#fff">{ticker_disp}</span>
              <span style="font-size:10px;color:#4a9eff;background:#4a9eff15;border:1px solid #4a9eff33;padding:2px 8px;border-radius:4px">{asset_label}</span>
            </div>
            <div style="display:flex;gap:16px;align-items:center;flex-wrap:wrap">
              <span style="font-size:11px;color:#555">{s['total_trades']} trades</span>
              <span style="color:{wr_color};font-weight:600">{s['win_rate']}% WR</span>
              <span style="color:{ret_color};font-weight:700;font-size:16px">{ret_sign}{s['total_return']}%</span>
            </div>
          </div>
          <div style="padding:14px 18px">
            <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-bottom:14px">
              <div style="background:#1a1a25;border:1px solid #2a2a3a;border-radius:6px;padding:8px;text-align:center">
                <div style="font-size:9px;color:#555;text-transform:uppercase;margin-bottom:3px">Avg Win</div>
                <div style="font-size:13px;color:#00c853;font-weight:500">+{s['avg_win']}%</div>
              </div>
              <div style="background:#1a1a25;border:1px solid #2a2a3a;border-radius:6px;padding:8px;text-align:center">
                <div style="font-size:9px;color:#555;text-transform:uppercase;margin-bottom:3px">Avg Loss</div>
                <div style="font-size:13px;color:#ff3d00;font-weight:500">{s['avg_loss']}%</div>
              </div>
              <div style="background:#1a1a25;border:1px solid #2a2a3a;border-radius:6px;padding:8px;text-align:center">
                <div style="font-size:9px;color:#555;text-transform:uppercase;margin-bottom:3px">Best Trade</div>
                <div style="font-size:13px;color:#00c853;font-weight:500">+{s['best_trade']}%</div>
              </div>
              <div style="background:#1a1a25;border:1px solid #2a2a3a;border-radius:6px;padding:8px;text-align:center">
                <div style="font-size:9px;color:#555;text-transform:uppercase;margin-bottom:3px">Worst Trade</div>
                <div style="font-size:13px;color:#ff3d00;font-weight:500">{s['worst_trade']}%</div>
              </div>
            </div>
            <div style="font-size:11px;color:#555;text-transform:uppercase;letter-spacing:.06em;margin-bottom:6px">Last 5 Trades</div>
            <table style="width:100%;border-collapse:collapse;color:#ccc">
              <thead>
                <tr style="background:#1a1a25;font-size:10px;color:#555;text-transform:uppercase">
                  <th style="padding:6px 10px;text-align:left">Entry</th>
                  <th style="padding:6px 10px;text-align:left">Exit</th>
                  <th style="padding:6px 10px;text-align:left">Buy</th>
                  <th style="padding:6px 10px;text-align:left">Sell</th>
                  <th style="padding:6px 10px;text-align:left">P&L</th>
                  <th style="padding:6px 10px;text-align:left">Reason</th>
                </tr>
              </thead>
              <tbody>{trade_rows}</tbody>
            </table>
          </div>
        </div>"""

    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>Strategy Backtest - {rules.get('strategy_name', 'Strategy')}</title>
<style>
  * {{ box-sizing:border-box; margin:0; padding:0; }}
  body {{ font-family:-apple-system,sans-serif; background:#0a0a0f; color:#e0e0e0; padding:24px; max-width:1000px; margin:auto; }}
</style>
</head>
<body>

<div style="background:linear-gradient(135deg,#1a1a2e,#16213e);border:1px solid #333;border-radius:12px;padding:26px 32px;margin-bottom:24px">
  <h1 style="font-size:22px;color:#fff;margin-bottom:6px">Strategy Backtest Report</h1>
  <p style="color:#888;font-size:13px">{today} &middot; {now} &middot; {rules.get('strategy_name', 'Custom Strategy')} &middot; {method} input &middot; {len(DAX40)} DAX stocks &middot; {len(GERMAN_INDEXES)} indexes &middot; {len(CRYPTO)} crypto &middot; {len(COMMODITIES)} commodities</p>
</div>

<div style="background:#12121a;border:1px solid #2a2a3a;border-radius:10px;padding:18px 22px;margin-bottom:20px">
  <div style="font-size:10px;color:#555;text-transform:uppercase;letter-spacing:.08em;margin-bottom:8px">Strategy Description</div>
  <p style="font-size:14px;color:#ccc;line-height:1.7;margin-bottom:10px">{strategy_text}</p>
  <div style="font-size:10px;color:#555;text-transform:uppercase;letter-spacing:.08em;margin-bottom:6px">Parsed Rules</div>
  <p style="font-size:13px;color:#999;line-height:1.6">{rules.get('description', '')}</p>
  <div style="display:flex;gap:10px;flex-wrap:wrap;margin-top:10px">
    <span style="background:#4a9eff20;color:#4a9eff;border:1px solid #4a9eff44;padding:3px 10px;border-radius:99px;font-size:11px">{rules.get('strategy_type', '')}</span>
    <span style="background:#00c85320;color:#00c853;border:1px solid #00c85344;padding:3px 10px;border-radius:99px;font-size:11px">{rules.get('direction', 'LONG')}</span>
    <span style="background:#ff6d0020;color:#ff6d00;border:1px solid #ff6d0044;padding:3px 10px;border-radius:99px;font-size:11px">~{rules.get('holding_period', 5)} days hold</span>
  </div>
</div>

<div style="display:grid;grid-template-columns:repeat(5,1fr);gap:14px;margin-bottom:20px">
  <div style="background:#12121a;border:1px solid #333;border-radius:10px;padding:16px;text-align:center">
    <div style="font-size:22px;font-weight:700;color:#4a9eff">{total_trades}</div>
    <div style="font-size:11px;color:#888;margin-top:3px">Total Trades</div>
  </div>
  <div style="background:#12121a;border:1px solid #333;border-radius:10px;padding:16px;text-align:center">
    <div style="font-size:22px;font-weight:700;color:{'#00c853' if win_rate >= 55 else '#ff6600' if win_rate >= 45 else '#ff3d00'}">{win_rate}%</div>
    <div style="font-size:11px;color:#888;margin-top:3px">Win Rate</div>
  </div>
  <div style="background:#12121a;border:1px solid #333;border-radius:10px;padding:16px;text-align:center">
    <div style="font-size:22px;font-weight:700;color:{'#00c853' if avg_return >= 0 else '#ff3d00'}">{'+' if avg_return >= 0 else ''}{avg_return}%</div>
    <div style="font-size:11px;color:#888;margin-top:3px">Avg Return</div>
  </div>
  <div style="background:#12121a;border:1px solid #333;border-radius:10px;padding:16px;text-align:center">
    <div style="font-size:22px;font-weight:700;color:#00c853">{len(wins)}</div>
    <div style="font-size:11px;color:#888;margin-top:3px">Wins</div>
  </div>
  <div style="background:#12121a;border:1px solid #333;border-radius:10px;padding:16px;text-align:center">
    <div style="font-size:22px;font-weight:700;color:#ff3d00">{len(losses)}</div>
    <div style="font-size:11px;color:#888;margin-top:3px">Losses</div>
  </div>
</div>

<div style="background:#12121a;border:1px solid #2a2a3a;border-radius:10px;padding:16px;margin-bottom:20px">
  <div style="font-size:11px;color:#555;text-transform:uppercase;letter-spacing:.06em;margin-bottom:10px">Equity Curve - All Tickers</div>
  {chart_html}
</div>

<div style="font-size:13px;font-weight:500;color:#888;margin-bottom:12px;text-transform:uppercase;letter-spacing:.05em">Results by Ticker - Ranked by Total Return</div>

{ticker_cards}

<div style="text-align:center;color:#333;font-size:12px;margin-top:24px;padding-top:16px;border-top:1px solid #111">
  QuantFlow Strategy Builder &middot; {today} &middot; Past performance does not guarantee future results
</div>

</body>
</html>"""

    return html


# ---------------------------------------------
# 8. MAIN
# ---------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="No-Code Strategy Builder")
    parser.add_argument("--template", action="store_true", help="Use pre-built template")
    parser.add_argument("--both",     action="store_true", help="Choose method interactively")
    parser.add_argument("--out",      default="strategy_report.html", help="Output HTML file")
    args = parser.parse_args()

    print("\n" + "=" * 55)
    print("  QuantFlow - No-Code Strategy Builder")
    print("  Type your strategy. Claude converts it to rules.")
    print(f"  Backtested across {len(WATCHLIST)} instruments:")
    print(f"  {len(DAX40)} DAX stocks | {len(GERMAN_INDEXES)} indexes | "
          f"{len(CRYPTO)} crypto | {len(COMMODITIES)} commodities")
    print("=" * 55)

    if not ANTHROPIC_API_KEY:
        raise ValueError("Missing ANTHROPIC_API_KEY in .env file")

    if args.template:
        mode = "template"
    elif args.both:
        mode = "both"
    else:
        mode = "text"

    strategy_text, method = get_strategy(mode)

    print("\n  Converting strategy to executable rules...")
    rules = parse_strategy_with_ai(strategy_text)
    print(f"  Strategy parsed: {rules.get('strategy_name')}")
    print(f"  Type: {rules.get('strategy_type')} | Direction: {rules.get('direction')}")
    print(f"  Entry conditions: {len(rules.get('entry_conditions') or [])}")
    print(f"  Exit conditions:  {len(rules.get('exit_conditions')  or [])}")

    print(f"\n  Backtesting across {len(WATCHLIST)} instruments...")
    all_results = []

    for i, ticker in enumerate(WATCHLIST, 1):
        print(f"  [{i:>2}/{len(WATCHLIST)}] {ticker:<12}", end=" ")
        df = fetch_and_calculate(ticker)
        if df is None:
            print("No data")
            all_results.append({"ticker": ticker, "trades": [], "stats": None})
            continue

        result = run_backtest(df, rules, ticker)
        all_results.append(result)

        if result["stats"]:
            s = result["stats"]
            sign = "+" if s["total_return"] >= 0 else ""
            print(f"{s['total_trades']} trades | {s['win_rate']}% WR | {sign}{s['total_return']}% total")
        else:
            print("No trades generated")

    print("\n  Generating equity curve...")
    chart_b64 = generate_equity_chart(all_results)

    print("  Building HTML report...")
    html = build_html_report(rules, all_results, strategy_text, method, chart_b64)

    with open(args.out, "w", encoding="utf-8") as f:
        f.write(html)

    all_trades = [t for r in all_results for t in r["trades"]]
    wins       = [t for t in all_trades if t["result"] == "WIN"]
    win_rate   = round(len(wins) / len(all_trades) * 100, 1) if all_trades else 0
    best = max(
        all_results,
        key=lambda r: r["stats"]["total_return"] if r["stats"] else -999,
        default=None,
    )

    print(f"\n{'=' * 55}")
    print("  Backtest Complete")
    print(f"  Strategy    : {rules.get('strategy_name')}")
    print(f"  Instruments : {len(DAX40)} DAX | {len(GERMAN_INDEXES)} indexes | "
          f"{len(CRYPTO)} crypto | {len(COMMODITIES)} commodities")
    print(f"  Total trades: {len(all_trades)}")
    print(f"  Win rate    : {win_rate}%")
    if best and best["stats"]:
        print(f"  Best ticker : {best['ticker']} (+{best['stats']['total_return']}%)")
    print(f"  Report saved: {args.out}")
    print(f"{'=' * 55}\n")


if __name__ == "__main__":
    main()

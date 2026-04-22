import os
import json
import argparse
import base64
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
# DAX 40 tickers
# ---------------------------------------------
DAX40 = [
    "ADS.DE",  "AIR.DE",  "ALV.DE",  "BAS.DE",  "BAYN.DE",
    "BEI.DE",  "BMW.DE",  "BNR.DE",  "CON.DE",  "1COV.DE",
    "DHER.DE", "DBK.DE",  "DB1.DE",  "DHL.DE",  "DTE.DE",
    "EOAN.DE", "FRE.DE",  "HEI.DE",  "HEN3.DE", "IFX.DE",
    "INL.DE",  "MBG.DE",  "MRK.DE",  "MTX.DE",  "MUV2.DE",
    "PAH3.DE", "QGEN.DE", "RHM.DE",  "RWE.DE",  "SAP.DE",
    "SHL.DE",  "SIE.DE",  "SY1.DE",  "VOW3.DE", "VNA.DE",
    "ZAL.DE",  "^GDAXI",
]

SECTOR_MAP = {
    "SAP.DE":   "Technology",    "IFX.DE":  "Technology",
    "SIE.DE":   "Industrials",   "RHM.DE":  "Industrials",
    "BMW.DE":   "Automotive",    "VOW3.DE": "Automotive",
    "MBG.DE":   "Automotive",    "PAH3.DE": "Automotive",
    "ALV.DE":   "Finance",       "DBK.DE":  "Finance",
    "MUV2.DE":  "Finance",       "DB1.DE":  "Finance",
    "BAS.DE":   "Chemicals",     "1COV.DE": "Chemicals",
    "BAYN.DE":  "Pharma",        "MRK.DE":  "Pharma",
    "QGEN.DE":  "Pharma",        "SHL.DE":  "Healthcare",
    "ADS.DE":   "Consumer",      "HEN3.DE": "Consumer",
    "DTE.DE":   "Telecom",       "EOAN.DE": "Energy",
    "RWE.DE":   "Energy",        "DHL.DE":  "Logistics",
    "AIR.DE":   "Aerospace",     "MTX.DE":  "Technology",
    "VNA.DE":   "Real Estate",   "ZAL.DE":  "E-Commerce",
    "FRE.DE":   "Industrials",   "CON.DE":  "Automotive",
    "BEI.DE":   "Consumer",      "HEI.DE":  "Healthcare",
    "BNR.DE":   "Technology",    "INL.DE":  "Technology",
    "DHER.DE":  "Food Delivery", "SY1.DE":  "Technology",
    "^GDAXI":   "Index",
}


# ---------------------------------------------
# 1. FETCH DATA
# ---------------------------------------------

def fetch_ticker_data(ticker: str) -> pd.DataFrame | None:
    try:
        df = yf.Ticker(ticker).history(period="90d", interval="1d")
        if df.empty or len(df) < 20:
            return None
        df.index = pd.to_datetime(df.index)
        return df
    except Exception:
        return None


# ---------------------------------------------
# 2. TECHNICAL INDICATORS
# ---------------------------------------------

def calculate_indicators(df: pd.DataFrame) -> dict:
    close  = df["Close"]
    high   = df["High"]
    low    = df["Low"]
    volume = df["Volume"]

    ema21  = close.ewm(span=21,  adjust=False).mean()
    ema50  = close.ewm(span=50,  adjust=False).mean()
    ema200 = close.ewm(span=200, adjust=False).mean()

    # RSI (Wilder smoothing via ewm com=13)
    delta = close.diff()
    gain  = delta.clip(lower=0)
    loss  = -delta.clip(upper=0)
    rs    = gain.ewm(com=13, adjust=False).mean() / loss.ewm(com=13, adjust=False).mean()
    rsi   = 100 - (100 / (1 + rs))

    # MACD
    macd      = close.ewm(span=12, adjust=False).mean() - close.ewm(span=26, adjust=False).mean()
    signal    = macd.ewm(span=9, adjust=False).mean()
    macd_hist = macd - signal

    vol_ma20  = volume.rolling(20).mean()
    vol_surge = round(volume.iloc[-1] / vol_ma20.iloc[-1], 2) if vol_ma20.iloc[-1] > 0 else 1.0

    curr_price = round(close.iloc[-1], 2)
    prev_close = close.iloc[-2]
    change_pct = round(((curr_price - prev_close) / prev_close) * 100, 2)

    high_52w      = round(high.tail(252).max(), 2)
    low_52w       = round(low.tail(252).min(), 2)
    pct_from_high = round(((curr_price - high_52w) / high_52w) * 100, 2)

    resistance = round(high.tail(20).max(), 2)
    support    = round(low.tail(20).min(), 2)

    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low  - close.shift()).abs(),
    ], axis=1).max(axis=1)
    atr = round(tr.rolling(14).mean().iloc[-1], 2)

    return {
        "price":         curr_price,
        "change_pct":    change_pct,
        "ema21":         round(ema21.iloc[-1], 2),
        "ema50":         round(ema50.iloc[-1], 2),
        "ema200":        round(ema200.iloc[-1], 2),
        "rsi":           round(rsi.iloc[-1], 1),
        "macd":          round(macd.iloc[-1], 3),
        "macd_signal":   round(signal.iloc[-1], 3),
        "macd_hist":     round(macd_hist.iloc[-1], 3),
        "vol_surge":     vol_surge,
        "volume":        int(volume.iloc[-1]),
        "resistance":    resistance,
        "support":       support,
        "high_52w":      high_52w,
        "low_52w":       low_52w,
        "pct_from_high": pct_from_high,
        "atr":           atr,
        "above_ema21":   curr_price > ema21.iloc[-1],
        "above_ema50":   curr_price > ema50.iloc[-1],
        "above_ema200":  curr_price > ema200.iloc[-1],
    }


# ---------------------------------------------
# 3. SETUP DETECTION
# ---------------------------------------------

def detect_setup(ind: dict) -> tuple[str, int, str]:
    """Return (setup_type, conviction 0-100, reason)."""
    price      = ind["price"]
    rsi        = ind["rsi"]
    vol_surge  = ind["vol_surge"]
    resistance = ind["resistance"]
    support    = ind["support"]
    macd_hist  = ind["macd_hist"]

    setups = []

    # Breakout: price pressing 20-day high with volume confirmation
    if (price >= resistance * 0.995 and
            vol_surge >= 1.5 and
            ind["above_ema50"] and
            50 < rsi < 80):
        conviction = min(100, int(50 + vol_surge * 10 + (rsi - 50)))
        setups.append(("Breakout", conviction,
            f"Price breaking 20-day high at {resistance} with {vol_surge}x volume surge"))

    # Pullback: healthy retracement to 21 EMA in an uptrend
    ema21_dist = abs(price - ind["ema21"]) / ind["ema21"] * 100
    if (ind["above_ema50"] and
            ind["above_ema200"] and
            ema21_dist < 2.0 and
            40 < rsi < 60 and
            macd_hist > 0):
        conviction = min(100, int(55 + (20 - ema21_dist * 5) + macd_hist * 10))
        setups.append(("Pullback", conviction,
            f"Pulling back to 21 EMA ({ind['ema21']}) in uptrend -- RSI {rsi}"))

    # Momentum: strong intraday move with expanding volume
    if (ind["change_pct"] > 1.5 and
            vol_surge >= 2.0 and
            55 < rsi < 85 and
            ind["above_ema21"] and
            macd_hist > 0):
        conviction = min(100, int(50 + ind["change_pct"] * 5 + vol_surge * 5))
        setups.append(("Momentum", conviction,
            f"Strong momentum +{ind['change_pct']}% with {vol_surge}x volume -- RSI {rsi}"))

    # Breakdown: price losing 20-day support on volume
    if (price <= support * 1.005 and
            vol_surge >= 1.5 and
            not ind["above_ema50"] and
            rsi < 50):
        conviction = min(100, int(50 + vol_surge * 8 + (50 - rsi)))
        setups.append(("Breakdown", conviction,
            f"Breaking below 20-day support at {support} with {vol_surge}x volume"))

    # Reversal: oversold bounce off extreme RSI with positive MACD histogram
    if (rsi < 30 and
            ind["change_pct"] > 0 and
            vol_surge >= 1.3 and
            macd_hist > 0):
        conviction = min(100, int(45 + (30 - rsi) * 1.5 + vol_surge * 5))
        setups.append(("Reversal", conviction,
            f"Oversold RSI {rsi} with green candle and {vol_surge}x volume -- potential bounce"))

    if not setups:
        return "No Setup", 0, "No clear technical pattern detected"

    return max(setups, key=lambda x: x[1])


# ---------------------------------------------
# 4. MINI CHART
# ---------------------------------------------

def generate_mini_chart(df: pd.DataFrame, ticker: str, setup: str) -> str:
    """Return a 30-day candlestick chart as a base64-encoded PNG string."""
    try:
        df_plot = df.tail(30).copy()
        x       = range(len(df_plot))
        opens   = df_plot["Open"].values
        highs   = df_plot["High"].values
        lows    = df_plot["Low"].values
        closes  = df_plot["Close"].values
        volumes = df_plot["Volume"].values

        fig, (ax1, ax2) = plt.subplots(
            2, 1, figsize=(7, 4),
            gridspec_kw={"height_ratios": [3, 1]},
            facecolor="#0d1117",
        )
        for ax in (ax1, ax2):
            ax.set_facecolor("#0d1117")
            ax.tick_params(colors="#555", labelsize=7)
            for spine in ax.spines.values():
                spine.set_color("#222")

        for i, (o, h, l, c) in enumerate(zip(opens, highs, lows, closes)):
            color = "#00c853" if c >= o else "#ff3d00"
            ax1.plot([i, i], [l, h], color=color, linewidth=0.7, alpha=0.85)
            ax1.add_patch(plt.Rectangle(
                (i - 0.3, min(o, c)), 0.6, max(abs(c - o), 0.01),
                color=color, alpha=0.85,
            ))

        close_s = df_plot["Close"]
        ax1.plot(x, close_s.ewm(span=21, adjust=False).mean().values,
                 color="#4a9eff", linewidth=1.0, alpha=0.8, label="EMA21")
        ax1.plot(x, close_s.ewm(span=50, adjust=False).mean().values,
                 color="#ff6d00", linewidth=1.0, alpha=0.8, label="EMA50")

        for i, (c, o, v) in enumerate(zip(closes, opens, volumes)):
            ax2.bar(i, v, color="#00c85333" if c >= o else "#ff3d0033", width=0.8)

        date_strs = list(df_plot.index.strftime("%b %d"))
        step = max(1, len(df_plot) // 5)
        ax1.set_xticks(range(0, len(df_plot), step))
        ax1.set_xticklabels(
            [date_strs[i] for i in range(0, len(df_plot), step)],
            rotation=20, ha="right", fontsize=6, color="#555",
        )
        ax2.set_xticks([])
        ax1.set_ylabel("EUR", color="#555", fontsize=7)
        ax1.legend(fontsize=6, facecolor="#111", labelcolor="#aaa",
                   edgecolor="#333", loc="upper left")

        ticker_disp = ticker.replace(".DE", "").replace("^", "")
        ax1.set_title(f"{ticker_disp} -- {setup}", color="#ccc", fontsize=9, pad=6)
        plt.tight_layout(pad=1.0)

        buf = BytesIO()
        plt.savefig(buf, format="png", dpi=110,
                    bbox_inches="tight", facecolor="#0d1117")
        plt.close(fig)
        buf.seek(0)
        return base64.b64encode(buf.read()).decode("utf-8")

    except Exception as e:
        print(f"  [WARN] Chart error for {ticker}: {e}")
        return ""


# ---------------------------------------------
# 5. AI RANKING
# ---------------------------------------------

def ai_rank_setups(candidates: list) -> list:
    """Rank candidates via Claude and attach trade plan fields."""
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    lines = []
    for c in candidates:
        ind = c["indicators"]
        lines.append(
            f"Ticker: {c['ticker']} | Sector: {c['sector']}\n"
            f"Setup: {c['setup']} | Conviction: {c['conviction']}/100\n"
            f"Price: {ind['price']} ({ind['change_pct']:+}%) | RSI: {ind['rsi']}\n"
            f"Volume: {ind['vol_surge']}x average | ATR: {ind['atr']}\n"
            f"Above EMA21: {ind['above_ema21']} | Above EMA50: {ind['above_ema50']} | Above EMA200: {ind['above_ema200']}\n"
            f"52w High: {ind['high_52w']} | Distance from high: {ind['pct_from_high']}%\n"
            f"Reason: {c['reason']}\n---"
        )
    summary = "\n".join(lines)
    today   = datetime.now().strftime("%A, %B %d %Y")

    prompt = f"""You are a senior German market trader reviewing today's technical setup scanner results for DAX stocks.

Today is {today}. XETRA opens in 30 minutes.

Here are the candidate setups detected:
{summary}

Respond ONLY with a JSON array — no markdown, no extra text:
[
  {{
    "ticker": "SAP.DE",
    "rank": 1,
    "ai_conviction": 85,
    "entry_zone": "145.50 - 146.00",
    "stop_loss": "143.00",
    "target": "150.00",
    "risk_reward": "2.3:1",
    "commentary": "2 sentences max explaining why this setup is interesting and what to watch for.",
    "watch_out": "1 sentence describing the main risk or invalidation condition."
  }}
]

Rank by overall quality: setup clarity, sector alignment, risk/reward, and current market context.
Include ALL tickers provided, ranked from best to worst."""

    try:
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = msg.content[0].text.strip()
        # Strip optional markdown code fence
        if raw.startswith("```"):
            parts = raw.split("```")
            raw = parts[1].lstrip("json").strip() if len(parts) > 1 else raw
        rankings = json.loads(raw)

        rank_map = {r["ticker"]: r for r in rankings}
        for c in candidates:
            ai = rank_map.get(c["ticker"], {})
            c["rank"]          = ai.get("rank", 99)
            c["ai_conviction"] = ai.get("ai_conviction", c["conviction"])
            c["entry_zone"]    = ai.get("entry_zone", f"~{c['indicators']['price']}")
            c["stop_loss"]     = ai.get("stop_loss", "Define before entry")
            c["target"]        = ai.get("target", "Define before entry")
            c["risk_reward"]   = ai.get("risk_reward", "N/A")
            c["commentary"]    = ai.get("commentary", "")
            c["watch_out"]     = ai.get("watch_out", "")

        candidates.sort(key=lambda x: x["rank"])
        return candidates

    except Exception as e:
        print(f"  [WARN] AI ranking failed: {e}")
        candidates.sort(key=lambda x: x["conviction"], reverse=True)
        for i, c in enumerate(candidates):
            c["rank"]          = i + 1
            c["ai_conviction"] = c["conviction"]
            c["entry_zone"]    = f"~{c['indicators']['price']}"
            c["stop_loss"]     = "Define before entry"
            c["target"]        = "Define before entry"
            c["risk_reward"]   = "N/A"
            c["commentary"]    = c["reason"]
            c["watch_out"]     = "AI ranking unavailable"
        return candidates


# ---------------------------------------------
# 6. HTML REPORT
# ---------------------------------------------

def build_html_report(top_setups: list, total_scanned: int) -> str:
    today    = datetime.now().strftime("%A, %B %d %Y")
    gen_time = datetime.now().strftime("%H:%M CET")

    SETUP_COLORS = {
        "Breakout":  ("#00c853", "#00c85320"),
        "Pullback":  ("#4a9eff", "#4a9eff20"),
        "Momentum":  ("#ff6d00", "#ff6d0020"),
        "Breakdown": ("#ff3d00", "#ff3d0020"),
        "Reversal":  ("#e040fb", "#e040fb20"),
    }

    setup_counts: dict[str, int] = {}
    for s in top_setups:
        setup_counts[s["setup"]] = setup_counts.get(s["setup"], 0) + 1

    setup_pills = ""
    for setup, count in setup_counts.items():
        fg, bg = SETUP_COLORS.get(setup, ("#888", "#88888820"))
        setup_pills += (
            f'<span style="background:{bg};color:{fg};border:1px solid {fg}44;'
            f'padding:4px 12px;border-radius:99px;font-size:12px">{setup} ({count})</span> '
        )

    cards_html = ""
    for s in top_setups:
        fg, bg      = SETUP_COLORS.get(s["setup"], ("#888", "#88888820"))
        ticker_disp = s["ticker"].replace(".DE", "").replace("^", "")
        ind         = s["indicators"]
        pnl_color   = "#00c853" if ind["change_pct"] >= 0 else "#ff3d00"
        pnl_sign    = "+" if ind["change_pct"] >= 0 else ""
        rsi_color   = "#ff3d00" if ind["rsi"] < 30 else "#00c853" if ind["rsi"] > 70 else "#ccc"
        vol_label   = "HIGH " if ind["vol_surge"] >= 2.0 else ""
        ema_status  = (
            "Above all EMAs" if (ind["above_ema21"] and ind["above_ema50"] and ind["above_ema200"])
            else "Mixed EMA signals" if ind["above_ema21"]
            else "Below key EMAs"
        )
        ema_color  = "#00c853" if "Above all" in ema_status else "#ff6600" if "Mixed" in ema_status else "#ff3d00"
        chart_html = (
            f'<img src="data:image/png;base64,{s.get("chart_b64", "")}" '
            f'style="width:100%;border-radius:6px" alt="Chart">'
            if s.get("chart_b64") else
            '<div style="height:160px;display:flex;align-items:center;'
            'justify-content:center;color:#444;font-size:12px">Chart unavailable</div>'
        )

        cards_html += f"""
        <div style="background:#12121a;border:1px solid #2a2a3a;border-radius:12px;margin-bottom:20px;overflow:hidden">
          <div style="display:flex;justify-content:space-between;align-items:center;padding:12px 18px;background:#16161f;border-bottom:1px solid #2a2a3a;flex-wrap:wrap;gap:8px">
            <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap">
              <span style="color:#555;font-size:12px">#{s['rank']}</span>
              <span style="font-size:22px;font-weight:700;color:#fff">{ticker_disp}</span>
              <span style="background:{bg};color:{fg};border:1px solid {fg}44;padding:3px 10px;border-radius:99px;font-size:11px">{s['setup']}</span>
              <span style="color:#888;font-size:12px">{s['sector']}</span>
            </div>
            <div style="display:flex;align-items:center;gap:14px">
              <span style="color:{pnl_color};font-weight:700;font-size:18px">{pnl_sign}{ind['change_pct']}%</span>
              <div style="text-align:center">
                <div style="font-size:18px;font-weight:700;color:{fg}">{s['ai_conviction']}</div>
                <div style="font-size:10px;color:#555">CONVICTION</div>
              </div>
            </div>
          </div>

          <div style="display:grid;grid-template-columns:1.4fr 1fr;gap:0">
            <div style="padding:14px;border-right:1px solid #2a2a3a">
              {chart_html}
              <div style="display:flex;gap:10px;flex-wrap:wrap;margin-top:8px">
                <span style="font-size:11px;color:#555">{today}</span>
                <span style="font-size:11px;color:#555">EUR {ind['price']}</span>
                <span style="font-size:11px;color:#555">{vol_label}{ind['vol_surge']}x vol</span>
              </div>
            </div>

            <div style="padding:14px">
              <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:14px">
                <div style="background:#1a1a25;border:1px solid #2a2a3a;border-radius:8px;padding:9px">
                  <div style="font-size:9px;color:#555;text-transform:uppercase;letter-spacing:.05em;margin-bottom:3px">RSI</div>
                  <div style="font-size:13px;font-weight:500;color:{rsi_color}">{ind['rsi']}</div>
                </div>
                <div style="background:#1a1a25;border:1px solid #2a2a3a;border-radius:8px;padding:9px">
                  <div style="font-size:9px;color:#555;text-transform:uppercase;letter-spacing:.05em;margin-bottom:3px">Volume</div>
                  <div style="font-size:13px;font-weight:500;color:#ccc">{vol_label}{ind['vol_surge']}x avg</div>
                </div>
                <div style="background:#1a1a25;border:1px solid #2a2a3a;border-radius:8px;padding:9px">
                  <div style="font-size:9px;color:#555;text-transform:uppercase;letter-spacing:.05em;margin-bottom:3px">Trend</div>
                  <div style="font-size:12px;font-weight:500;color:{ema_color}">{ema_status}</div>
                </div>
                <div style="background:#1a1a25;border:1px solid #2a2a3a;border-radius:8px;padding:9px">
                  <div style="font-size:9px;color:#555;text-transform:uppercase;letter-spacing:.05em;margin-bottom:3px">ATR</div>
                  <div style="font-size:13px;font-weight:500;color:#ccc">EUR {ind['atr']}</div>
                </div>
              </div>

              <div style="background:#1a1a2e;border-radius:8px;padding:12px;margin-bottom:10px">
                <div style="font-size:9px;color:#4a9eff;text-transform:uppercase;letter-spacing:.08em;margin-bottom:8px">Trade Plan</div>
                <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;font-size:12px">
                  <div><span style="color:#555">Entry:</span> <span style="color:#ccc">{s['entry_zone']}</span></div>
                  <div><span style="color:#555">R/R:</span> <span style="color:#ccc">{s['risk_reward']}</span></div>
                  <div><span style="color:#ff3d00">Stop:</span> <span style="color:#ccc">{s['stop_loss']}</span></div>
                  <div><span style="color:#00c853">Target:</span> <span style="color:#ccc">{s['target']}</span></div>
                </div>
              </div>

              <div style="font-size:9px;color:#555;text-transform:uppercase;letter-spacing:.08em;margin-bottom:4px">AI Commentary</div>
              <p style="font-size:12px;color:#999;line-height:1.6;margin-bottom:8px">{s['commentary']}</p>

              <div style="background:#2a1a1a;border-left:3px solid #ff3d00;padding:8px 10px;border-radius:0 6px 6px 0">
                <div style="font-size:9px;color:#ff6600;text-transform:uppercase;letter-spacing:.08em;margin-bottom:3px">Watch Out</div>
                <p style="font-size:12px;color:#ff8888;line-height:1.5;margin:0">{s['watch_out']}</p>
              </div>
            </div>
          </div>
        </div>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>DAX Setup Scanner -- {today}</title>
<style>
  * {{ box-sizing:border-box; margin:0; padding:0; }}
  body {{ font-family:-apple-system,sans-serif; background:#0a0a0f; color:#e0e0e0; padding:24px; max-width:1000px; margin:auto; }}
  @media(max-width:700px) {{
    div[style*="grid-template-columns:1.4fr 1fr"] {{ grid-template-columns:1fr !important; }}
    div[style*="grid-template-columns:repeat(5"] {{ grid-template-columns:repeat(2,1fr) !important; }}
  }}
</style>
</head>
<body>

<div style="background:linear-gradient(135deg,#1a1a2e,#16213e);border:1px solid #333;border-radius:12px;padding:26px 32px;margin-bottom:24px">
  <h1 style="font-size:22px;color:#fff;margin-bottom:4px">DAX Technical Setup Scanner</h1>
  <p style="color:#888;font-size:13px">German Market (XETRA) &middot; {today} &middot; Generated {gen_time} &middot; Scanned {total_scanned} stocks &middot; Top {len(top_setups)} setups</p>
</div>

<div style="display:grid;grid-template-columns:repeat(5,1fr);gap:14px;margin-bottom:24px">
  <div style="background:#12121a;border:1px solid #333;border-radius:10px;padding:16px;text-align:center">
    <div style="font-size:24px;font-weight:700;color:#4a9eff">{total_scanned}</div>
    <div style="font-size:11px;color:#888;margin-top:3px">Stocks Scanned</div>
  </div>
  <div style="background:#12121a;border:1px solid #333;border-radius:10px;padding:16px;text-align:center">
    <div style="font-size:24px;font-weight:700;color:#00c853">{len(top_setups)}</div>
    <div style="font-size:11px;color:#888;margin-top:3px">Setups Found</div>
  </div>
  <div style="background:#12121a;border:1px solid #333;border-radius:10px;padding:16px;text-align:center">
    <div style="font-size:24px;font-weight:700;color:#ff6d00">{top_setups[0]['ai_conviction'] if top_setups else 0}</div>
    <div style="font-size:11px;color:#888;margin-top:3px">Top Conviction</div>
  </div>
  <div style="background:#12121a;border:1px solid #333;border-radius:10px;padding:16px;text-align:center">
    <div style="font-size:24px;font-weight:700;color:#4a9eff">{top_setups[0]['ticker'].replace('.DE', '') if top_setups else '--'}</div>
    <div style="font-size:11px;color:#888;margin-top:3px">Top Pick</div>
  </div>
  <div style="background:#12121a;border:1px solid #333;border-radius:10px;padding:16px;text-align:center">
    <div style="font-size:24px;font-weight:700;color:#e040fb">{gen_time}</div>
    <div style="font-size:11px;color:#888;margin-top:3px">Generated</div>
  </div>
</div>

<div style="background:#12121a;border:1px solid #2a2a3a;border-radius:10px;padding:14px 18px;margin-bottom:24px;display:flex;gap:8px;flex-wrap:wrap;align-items:center">
  <span style="font-size:11px;color:#555;margin-right:4px">SETUPS FOUND:</span>
  {setup_pills}
</div>

{cards_html}

<div style="text-align:center;color:#333;font-size:12px;margin-top:24px;padding-top:16px;border-top:1px solid #111">
  DAX Setup Scanner &middot; German Market Edition &middot; {gen_time}
</div>

</body>
</html>"""


# ---------------------------------------------
# 7. SCAN PIPELINE
# ---------------------------------------------

def run_scan(top: int = 10, out: str = "setup_scanner_report.html") -> None:
    print("\n" + "=" * 55)
    print("  DAX Technical Setup Scanner")
    print(f"  {datetime.now().strftime('%A %d %B %Y -- %H:%M CET')}")
    print(f"  Scanning {len(DAX40)} stocks -- Top {top} setups")
    print("=" * 55 + "\n")

    if not ANTHROPIC_API_KEY:
        raise ValueError("ANTHROPIC_API_KEY is not set in the environment or .env file")

    candidates: list[dict] = []
    total = len(DAX40)

    for i, ticker in enumerate(DAX40, 1):
        print(f"[{i:>2}/{total}] {ticker:<12}", end=" ")
        df = fetch_ticker_data(ticker)
        if df is None:
            print("no data")
            continue

        ind = calculate_indicators(df)
        setup, conviction, reason = detect_setup(ind)

        if setup == "No Setup" or conviction < 40:
            print("no setup")
            continue

        print(f"{setup} ({conviction}/100)")
        candidates.append({
            "ticker":     ticker,
            "sector":     SECTOR_MAP.get(ticker, "Unknown"),
            "setup":      setup,
            "conviction": conviction,
            "reason":     reason,
            "indicators": ind,
            "df":         df,
        })

    if not candidates:
        print("\nNo qualifying setups found today.\n")
        return

    candidates.sort(key=lambda x: x["conviction"], reverse=True)
    top_candidates = candidates[:top]

    print(f"\nFound {len(candidates)} setups -- ranking top {len(top_candidates)}...")

    print("Generating charts...")
    for c in top_candidates:
        c["chart_b64"] = generate_mini_chart(c["df"], c["ticker"], c["setup"])
        del c["df"]

    print("Requesting AI ranking...")
    top_setups = ai_rank_setups(top_candidates)

    print("Building HTML report...")
    dated_out = out.replace(".html", f"_{datetime.now().strftime('%Y-%m-%d')}.html")
    html      = build_html_report(top_setups, total)
    with open(dated_out, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"\nReport saved: {dated_out}")
    print(f"Top pick: {top_setups[0]['ticker']} -- {top_setups[0]['setup']} ({top_setups[0]['ai_conviction']}/100)")
    print(f"Open {dated_out} in your browser.\n")


# ---------------------------------------------
# 8. ENTRY POINT
# ---------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="DAX Technical Setup Scanner")
    parser.add_argument("--top", type=int, default=10,
                        help="Number of top setups to include in the report (default: 10)")
    parser.add_argument("--out", default="setup_scanner_report.html",
                        help="Output HTML filename (date is appended automatically)")
    args = parser.parse_args()
    run_scan(top=args.top, out=args.out)


if __name__ == "__main__":
    main()

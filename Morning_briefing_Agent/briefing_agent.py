"""
Morning Market Briefing Agent
------------------------------
- Fetches price data & news via Yahoo Finance (free, no API key)
- Generates smart summary using Claude AI
- Sends formatted briefing to your email every morning
"""

import yfinance as yf
import anthropic
import smtplib
import schedule
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
from config import WATCHLIST, EMAIL_SENDER, EMAIL_PASSWORD, EMAIL_RECEIVER, ANTHROPIC_API_KEY


# ─────────────────────────────────────────────
# 1. FETCH MARKET DATA
# ─────────────────────────────────────────────

def fetch_stock_data(ticker: str) -> dict:
    """Pull price, change, volume, and recent news for one ticker."""
    stock = yf.Ticker(ticker)
    hist = stock.history(period="2d")

    if len(hist) < 2:
        return {"ticker": ticker, "error": "Not enough data"}

    prev_close = hist["Close"].iloc[-2]
    curr_close = hist["Close"].iloc[-1]
    change_pct = ((curr_close - prev_close) / prev_close) * 100
    volume = hist["Volume"].iloc[-1]
    avg_volume = hist["Volume"].mean()
    volume_surge = volume / avg_volume if avg_volume > 0 else 1
    currency = "EUR" if ticker.endswith(".DE") or ticker == "^GDAXI" else "USD"
    currency_symbol = "EUR" if currency == "EUR" else "$"

    # Grab up to 3 recent news headlines
    news_items = stock.news[:3] if stock.news else []
    headlines = [n.get("content", {}).get("title", "") for n in news_items if n.get("content")]

    # Basic technical check — is price above 50-day MA?
    hist_50 = stock.history(period="60d")
    ma50 = hist_50["Close"].mean() if len(hist_50) >= 50 else None
    above_ma50 = curr_close > ma50 if ma50 else None

    return {
        "ticker": ticker,
        "price": round(curr_close, 2),
        "change_pct": round(change_pct, 2),
        "volume": int(volume),
        "volume_surge": round(volume_surge, 2),
        "above_ma50": above_ma50,
        "headlines": headlines,
        "currency_symbol": currency_symbol,
    }


def fetch_all_stocks(watchlist: list) -> list:
    """Fetch data for every ticker in the watchlist."""
    print(f"Fetching data for {len(watchlist)} tickers...")
    results = []
    for ticker in watchlist:
        data = fetch_stock_data(ticker)
        results.append(data)
        symbol = data.get("currency_symbol", "EUR")
        print(f"  {ticker}: {symbol}{data.get('price', 'N/A')} ({data.get('change_pct', 'N/A')}%)")
    return results


# ─────────────────────────────────────────────
# 2. GENERATE AI SUMMARY WITH CLAUDE
# ─────────────────────────────────────────────

def generate_ai_summary(stock_data: list) -> str:
    """Send stock data to Claude and get a smart morning briefing."""
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    data_text = ""
    for s in stock_data:
        if "error" in s:
            continue
        direction = "up" if s["change_pct"] > 0 else "down"
        ma_status = "above 50MA" if s["above_ma50"] else "below 50MA" if s["above_ma50"] is False else "MA unknown"
        vol_note = f"Volume {s['volume_surge']}x average" if s["volume_surge"] > 1.5 else "Normal volume"
        headlines_text = " | ".join(s["headlines"]) if s["headlines"] else "No recent news"
        symbol = s.get("currency_symbol", "EUR")

        data_text += f"""
Ticker: {s['ticker']}
Price: {symbol}{s['price']} {direction} {abs(s['change_pct'])}%
Technical: {ma_status} | {vol_note}
News: {headlines_text}
"""

    today = datetime.now().strftime("%A, %B %d %Y")

    prompt = f"""You are an experienced stock trader writing a morning briefing for a swing and day trader focused on the German stock market (XETRA / DAX).

Today is {today}. XETRA opens at 09:00 CET.

Here is today's market data for the watchlist:
{data_text}

Write a concise morning briefing that:
1. Starts with a 2-sentence overall DAX market mood summary
2. Highlights the top 2-3 most interesting opportunities or alerts (unusual volume, key level breaks, strong news)
3. Flags any tickers showing warning signs (gap downs, negative news, weak technicals)
4. Ends with a short "Focus list for today" — max 3 tickers worth watching closely and why

Keep it sharp and practical — like a message from a senior Frankfurt trader to their team. Prices are in EUR. No fluff."""

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt}]
    )

    return message.content[0].text


# ─────────────────────────────────────────────
# 3. FORMAT HTML EMAIL
# ─────────────────────────────────────────────

def format_email_html(stock_data: list, ai_summary: str) -> str:
    """Build a clean HTML email with the briefing."""
    today = datetime.now().strftime("%A, %B %d %Y")

    rows = ""
    for s in stock_data:
        if "error" in s:
            continue
        color = "#16a34a" if s["change_pct"] > 0 else "#dc2626"
        arrow = "+" if s["change_pct"] > 0 else "-"
        vol_flag = " (high volume)" if s["volume_surge"] > 2.0 else ""
        symbol = s.get("currency_symbol", "EUR")
        rows += f"""
        <tr>
          <td style="padding:8px 12px;font-weight:600">{s['ticker'].replace('.DE','')}</td>
          <td style="padding:8px 12px">{symbol}{s['price']}</td>
          <td style="padding:8px 12px;color:{color};font-weight:600">{arrow}{abs(s['change_pct'])}%</td>
          <td style="padding:8px 12px;color:#6b7280">{s['volume_surge']}x vol{vol_flag}</td>
        </tr>"""

    summary_html = ai_summary.replace("\n", "<br>")

    html = f"""
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="font-family:Arial,sans-serif;max-width:650px;margin:auto;background:#f9fafb;padding:24px">

  <div style="background:#1e293b;color:white;padding:20px 24px;border-radius:10px 10px 0 0">
    <h2 style="margin:0;font-size:20px">Morgen Markt Briefing — DAX / XETRA</h2>
    <p style="margin:4px 0 0;color:#94a3b8;font-size:14px">{today} · XETRA opens 09:00 CET</p>
  </div>

  <div style="background:white;padding:24px;border:1px solid #e5e7eb;border-top:none">

    <h3 style="color:#1e293b;margin-top:0">Watchlist Snapshot</h3>
    <table style="width:100%;border-collapse:collapse;font-size:14px">
      <thead>
        <tr style="background:#f1f5f9;color:#475569">
          <th style="padding:8px 12px;text-align:left">Ticker</th>
          <th style="padding:8px 12px;text-align:left">Price</th>
          <th style="padding:8px 12px;text-align:left">Change</th>
          <th style="padding:8px 12px;text-align:left">Volume</th>
        </tr>
      </thead>
      <tbody>{rows}</tbody>
    </table>

    <hr style="border:none;border-top:1px solid #e5e7eb;margin:24px 0">

    <h3 style="color:#1e293b">AI Analysis</h3>
    <div style="background:#f8fafc;border-left:4px solid #3b82f6;padding:16px;border-radius:0 8px 8px 0;font-size:14px;line-height:1.7;color:#374151">
      {summary_html}
    </div>

  </div>

  <div style="background:#f1f5f9;padding:12px 24px;border-radius:0 0 10px 10px;text-align:center">
    <p style="margin:0;font-size:12px;color:#94a3b8">Morning Briefing Agent · XETRA · Generated at {datetime.now().strftime("%H:%M")} CET</p>
  </div>

</body>
</html>"""
    return html


# ─────────────────────────────────────────────
# 4. SEND EMAIL
# ─────────────────────────────────────────────

def send_email(html_content: str):
    """Send the briefing email via Gmail SMTP."""
    today = datetime.now().strftime("%b %d")
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"DAX Morning Briefing — {today}"
    msg["From"] = EMAIL_SENDER
    msg["To"] = EMAIL_RECEIVER
    msg.attach(MIMEText(html_content, "html"))

    print("Sending email...")
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.sendmail(EMAIL_SENDER, EMAIL_RECEIVER, msg.as_string())
    print(f"  Briefing sent to {EMAIL_RECEIVER}")


# ─────────────────────────────────────────────
# 5. MAIN AGENT FLOW
# ─────────────────────────────────────────────

def run_briefing():
    """Full agent pipeline: fetch -> analyse -> email."""
    print(f"\n{'='*50}")
    print(f"Running Morning Briefing — {datetime.now().strftime('%H:%M %Z')}")
    print(f"{'='*50}")

    try:
        stock_data = fetch_all_stocks(WATCHLIST)
        print("\nGenerating AI analysis...")
        ai_summary = generate_ai_summary(stock_data)
        html = format_email_html(stock_data, ai_summary)
        send_email(html)
        print("\nBriefing complete.\n")
    except Exception as e:
        print(f"\nError: {e}")


# ─────────────────────────────────────────────
# 6. SCHEDULER — runs every weekday at 08:30 CET
# ─────────────────────────────────────────────

if __name__ == "__main__":
    print("Morning Briefing Agent started — German Markets (XETRA)")
    print("Scheduled for 08:30 CET every weekday (30 min before XETRA opens)\n")

    run_briefing()

    schedule.every().monday.at("08:30").do(run_briefing)
    schedule.every().tuesday.at("08:30").do(run_briefing)
    schedule.every().wednesday.at("08:30").do(run_briefing)
    schedule.every().thursday.at("08:30").do(run_briefing)
    schedule.every().friday.at("08:30").do(run_briefing)

    while True:
        schedule.run_pending()
        time.sleep(60)

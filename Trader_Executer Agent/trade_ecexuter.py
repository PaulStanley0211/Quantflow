"""
trade_executor.py — Human-in-the-Loop Trade Executor
======================================================
Every weekday at 08:30 CET:
1. Scans DAX stocks for high-conviction setups
2. Sends you an approval email for each setup found
3. You reply YES or NO to the email
4. Agent checks your replies every 10 minutes
5. Approved trades are logged to journal CSV automatically
6. Rejected trades are logged to decisions_log.csv with reason

Usage:
    python trade_executor.py          # run once immediately
    python trade_executor.py --schedule  # auto-run at 08:30 every weekday
"""

import os
import csv
import json
import time
import imaplib
import email
import smtplib
import argparse
import schedule
from datetime import datetime, date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import anthropic
import yfinance as yf
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
EMAIL_SENDER      = os.getenv("EMAIL_SENDER")
EMAIL_PASSWORD    = os.getenv("EMAIL_PASSWORD")
EMAIL_RECEIVER    = os.getenv("EMAIL_RECEIVER")

JOURNAL_CSV      = "trades.csv"
DECISIONS_CSV    = "decisions_log.csv"
PENDING_FILE     = "pending_trades.json"
MIN_CONVICTION   = 60   # only send setups above this score
CHECK_REPLIES_INTERVAL = 60   # check email replies every 1 minute

JOURNAL_HEADERS = [
    "date", "ticker", "direction", "entry_price", "stop_loss",
    "exit_price", "quantity", "pnl_eur", "r_multiple",
    "setup_type", "ai_tag", "ai_lesson", "ai_quality", "notes"
]

DECISIONS_HEADERS = [
    "date", "time", "ticker", "setup_type", "direction",
    "entry_zone", "stop_loss", "target", "conviction",
    "decision", "reason", "ai_commentary"
]

# ─────────────────────────────────────────────
# SECTOR MAP
# ─────────────────────────────────────────────
SECTOR_MAP = {
    "SAP.DE": "Technology",   "IFX.DE": "Technology",
    "SIE.DE": "Industrials",  "RHM.DE": "Industrials",
    "BMW.DE": "Automotive",   "VOW3.DE": "Automotive",
    "MBG.DE": "Automotive",   "ALV.DE": "Finance",
    "DBK.DE": "Finance",      "BAS.DE": "Chemicals",
    "BAYN.DE": "Pharma",      "MRK.DE": "Pharma",
    "ADS.DE": "Consumer",     "DTE.DE": "Telecom",
    "EOAN.DE": "Energy",      "RWE.DE": "Energy",
    "DHL.DE": "Logistics",    "AIR.DE": "Aerospace",
}

DAX_WATCHLIST = [
    "SAP.DE", "SIE.DE", "BMW.DE", "VOW3.DE", "ALV.DE",
    "MBG.DE", "BAS.DE", "DBK.DE", "ADS.DE", "DTE.DE",
    "BAYN.DE", "MRK.DE", "IFX.DE", "RHM.DE", "EOAN.DE",
    "RWE.DE", "DHL.DE", "AIR.DE",
]


# ─────────────────────────────────────────────
# 1. FETCH + ANALYSE SETUP
# ─────────────────────────────────────────────

def fetch_data(ticker: str) -> pd.DataFrame | None:
    try:
        df = yf.Ticker(ticker).history(period="90d", interval="1d")
        return df if not df.empty and len(df) >= 20 else None
    except Exception:
        return None


def detect_setup(ticker: str, df: pd.DataFrame) -> dict | None:
    """Detect setup and return trade proposal or None."""
    close  = df["Close"]
    high   = df["High"]
    low    = df["Low"]
    volume = df["Volume"]

    ema21    = close.ewm(span=21, adjust=False).mean()
    ema50    = close.ewm(span=50, adjust=False).mean()
    ema200   = close.ewm(span=200, adjust=False).mean()
    delta    = close.diff()
    gain     = delta.clip(lower=0).ewm(com=13, adjust=False).mean()
    loss     = (-delta.clip(upper=0)).ewm(com=13, adjust=False).mean()
    rsi      = 100 - (100 / (1 + gain / loss))
    vol_ma20 = volume.rolling(20).mean()

    price      = round(float(close.iloc[-1]), 2)
    prev_close = float(close.iloc[-2])
    change_pct = round(((price - prev_close) / prev_close) * 100, 2)
    vol_surge  = round(float(volume.iloc[-1]) / float(vol_ma20.iloc[-1]), 2)
    rsi_val    = round(float(rsi.iloc[-1]), 1)
    resistance = round(float(high.tail(20).max()), 2)
    support    = round(float(low.tail(20).min()), 2)
    atr        = round(float(pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low - close.shift()).abs()
    ], axis=1).max(axis=1).rolling(14).mean().iloc[-1]), 2)

    above_ema21  = price > float(ema21.iloc[-1])
    above_ema50  = price > float(ema50.iloc[-1])
    above_ema200 = price > float(ema200.iloc[-1])

    setup      = None
    conviction = 0
    direction  = "BUY"
    reason     = ""

    # Breakout
    if price >= resistance * 0.995 and vol_surge >= 1.5 and above_ema50 and 50 < rsi_val < 80:
        setup      = "Breakout"
        conviction = min(100, int(50 + vol_surge * 10 + (rsi_val - 50)))
        direction  = "BUY"
        reason     = f"Breaking 20-day high €{resistance} with {vol_surge}x volume"

    # Pullback
    elif above_ema50 and above_ema200 and abs(price - float(ema21.iloc[-1])) / float(ema21.iloc[-1]) * 100 < 2.0 and 40 < rsi_val < 60:
        setup      = "Pullback"
        conviction = min(100, int(55 + (2.0 - abs(price - float(ema21.iloc[-1])) / float(ema21.iloc[-1]) * 100) * 10))
        direction  = "BUY"
        reason     = f"Pullback to 21 EMA €{round(float(ema21.iloc[-1]),2)} in uptrend — RSI {rsi_val}"

    # Momentum
    elif change_pct > 1.5 and vol_surge >= 2.0 and rsi_val > 55 and above_ema21:
        setup      = "Momentum"
        conviction = min(100, int(50 + change_pct * 5 + vol_surge * 5))
        direction  = "BUY"
        reason     = f"Strong momentum +{change_pct}% with {vol_surge}x volume"

    # Breakdown
    elif price <= support * 1.005 and vol_surge >= 1.5 and not above_ema50 and rsi_val < 50:
        setup      = "Breakdown"
        conviction = min(100, int(50 + vol_surge * 8 + (50 - rsi_val)))
        direction  = "SHORT"
        reason     = f"Breaking below support €{support} with {vol_surge}x volume"

    # Reversal
    elif rsi_val < 30 and change_pct > 0 and vol_surge >= 1.3:
        setup      = "Reversal"
        conviction = min(100, int(45 + (30 - rsi_val) * 1.5 + vol_surge * 5))
        direction  = "BUY"
        reason     = f"Oversold RSI {rsi_val} with green candle — potential bounce"

    if not setup or conviction < MIN_CONVICTION:
        return None

    # Calculate entry, stop, target
    if direction == "BUY":
        entry      = price
        stop       = round(price - atr * 1.5, 2)
        target     = round(price + atr * 3.0, 2)
    else:
        entry      = price
        stop       = round(price + atr * 1.5, 2)
        target     = round(price - atr * 3.0, 2)

    rr = round(abs(target - entry) / abs(entry - stop), 2) if abs(entry - stop) > 0 else 0

    return {
        "ticker":      ticker,
        "sector":      SECTOR_MAP.get(ticker, "Unknown"),
        "setup":       setup,
        "direction":   direction,
        "conviction":  conviction,
        "price":       price,
        "change_pct":  change_pct,
        "entry":       entry,
        "stop":        stop,
        "target":      target,
        "rr":          rr,
        "rsi":         rsi_val,
        "vol_surge":   vol_surge,
        "atr":         atr,
        "reason":      reason,
        "scan_time":   datetime.now().strftime("%H:%M"),
        "scan_date":   date.today().isoformat(),
    }


# ─────────────────────────────────────────────
# 2. AI COMMENTARY FOR EACH SETUP
# ─────────────────────────────────────────────

def get_ai_commentary(setup: dict) -> str:
    """Ask Claude for a brief trading commentary on the setup."""
    try:
        client  = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        prompt  = f"""You are a senior DAX trader giving a 2-sentence brief on a setup for a human trader who needs to approve or reject it.

Setup: {setup['ticker']} — {setup['setup']} — {setup['direction']}
Price: €{setup['price']} ({setup['change_pct']:+}%)
Entry: €{setup['entry']} | Stop: €{setup['stop']} | Target: €{setup['target']}
R/R: {setup['rr']}:1 | RSI: {setup['rsi']} | Volume: {setup['vol_surge']}x
Sector: {setup['sector']}
Reason: {setup['reason']}

Give 2 sentences: first sentence — why this setup is interesting. Second sentence — the main risk to watch."""

        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=150,
            messages=[{"role": "user", "content": prompt}]
        )
        return msg.content[0].text.strip()
    except Exception:
        return setup["reason"]


# ─────────────────────────────────────────────
# 3. SEND APPROVAL EMAIL
# ─────────────────────────────────────────────

def send_approval_email(setups: list):
    """Send one email with all setups found — user replies YES/NO per ticker."""
    if not all([EMAIL_SENDER, EMAIL_PASSWORD, EMAIL_RECEIVER]):
        print("  Email credentials not set")
        return

    today    = datetime.now().strftime("%B %d, %Y")
    now      = datetime.now().strftime("%H:%M CET")

    SETUP_COLORS = {
        "Breakout":  "#00c853",
        "Pullback":  "#4a9eff",
        "Momentum":  "#ff6d00",
        "Breakdown": "#ff3d00",
        "Reversal":  "#e040fb",
    }

    # Build setup cards
    cards = ""
    reply_guide = ""
    for s in setups:
        color       = SETUP_COLORS.get(s["setup"], "#888")
        dir_color   = "#00c853" if s["direction"] == "BUY" else "#ff3d00"
        ticker_disp = s["ticker"].replace(".DE", "")
        rr_color    = "#00c853" if s["rr"] >= 2.0 else "#ff6600" if s["rr"] >= 1.5 else "#ff3d00"

        cards += f"""
        <div style="background:#f8fafc;border:1px solid #e5e7eb;border-left:4px solid {color};border-radius:0 8px 8px 0;padding:16px;margin-bottom:16px">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;flex-wrap:wrap;gap:8px">
            <div style="display:flex;align-items:center;gap:10px">
              <span style="font-size:20px;font-weight:700;color:#1e293b">{ticker_disp}</span>
              <span style="background:{color}20;color:{color};border:1px solid {color}44;padding:2px 10px;border-radius:99px;font-size:11px">{s['setup']}</span>
              <span style="background:{dir_color}20;color:{dir_color};border:1px solid {dir_color}44;padding:2px 10px;border-radius:99px;font-size:11px">{s['direction']}</span>
            </div>
            <span style="font-size:18px;font-weight:700;color:{color}">{s['conviction']}/100</span>
          </div>

          <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-bottom:12px">
            <div style="background:white;border:1px solid #e5e7eb;border-radius:6px;padding:8px;text-align:center">
              <div style="font-size:10px;color:#888;margin-bottom:2px">ENTRY</div>
              <div style="font-size:14px;font-weight:600;color:#1e293b">€{s['entry']}</div>
            </div>
            <div style="background:white;border:1px solid #e5e7eb;border-radius:6px;padding:8px;text-align:center">
              <div style="font-size:10px;color:#888;margin-bottom:2px">STOP</div>
              <div style="font-size:14px;font-weight:600;color:#ff3d00">€{s['stop']}</div>
            </div>
            <div style="background:white;border:1px solid #e5e7eb;border-radius:6px;padding:8px;text-align:center">
              <div style="font-size:10px;color:#888;margin-bottom:2px">TARGET</div>
              <div style="font-size:14px;font-weight:600;color:#00c853">€{s['target']}</div>
            </div>
          </div>

          <div style="display:flex;gap:16px;font-size:12px;color:#666;margin-bottom:10px;flex-wrap:wrap">
            <span>📊 RSI: {s['rsi']}</span>
            <span>🔥 Volume: {s['vol_surge']}x avg</span>
            <span style="color:{rr_color};font-weight:600">R/R: {s['rr']}:1</span>
            <span>🏭 Sector: {s['sector']}</span>
          </div>

          <div style="background:#fff;border-left:3px solid {color};padding:10px 12px;border-radius:0 6px 6px 0;font-size:13px;color:#374151;line-height:1.6;margin-bottom:12px">
            {s.get('ai_commentary', s['reason'])}
          </div>

          <div style="background:#1e293b;border-radius:6px;padding:10px 14px;font-size:13px;color:#94a3b8">
            <b style="color:white">To approve:</b> Reply to this email with <b style="color:#00c853">YES {ticker_disp}</b><br>
            <b style="color:white">To reject:</b> Reply with <b style="color:#ff3d00">NO {ticker_disp}</b>
          </div>
        </div>"""

        reply_guide += f"YES {ticker_disp} or NO {ticker_disp}\n"

    html = f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="font-family:Arial,sans-serif;max-width:650px;margin:auto;background:#f9fafb;padding:24px">

  <div style="background:#1e293b;color:white;padding:20px 24px;border-radius:10px 10px 0 0">
    <h2 style="margin:0;font-size:20px">🔔 Trade Approval Request</h2>
    <p style="margin:4px 0 0;color:#94a3b8;font-size:13px">{today} · {now} · {len(setups)} setup(s) found · XETRA opens at 09:00 CET</p>
  </div>

  <div style="background:white;padding:20px 24px;border:1px solid #e5e7eb;border-top:none">

    <p style="color:#374151;font-size:14px;margin:0 0 16px;line-height:1.6">
      The setup scanner found <b>{len(setups)} high-conviction setup(s)</b> this morning.
      Review each one below and reply to this email with your decision.
      Approved trades will be automatically logged to your journal.
    </p>

    {cards}

    <div style="background:#fef3c7;border:1px solid #fbbf24;border-radius:8px;padding:14px;margin-top:8px">
      <p style="margin:0;font-size:13px;color:#92400e;line-height:1.6">
        <b>⚠️ Important:</b> These are suggestions, not financial advice.
        Always verify the setup on your own chart before approving.
        The agent will check your replies every 10 minutes.
      </p>
    </div>

  </div>

  <div style="background:#f1f5f9;padding:10px 24px;border-radius:0 0 10px 10px;text-align:center">
    <p style="margin:0;font-size:11px;color:#94a3b8">Human-in-the-Loop Trade Executor · German Market Edition · {now}</p>
  </div>

</body>
</html>"""

    msg            = MIMEMultipart("alternative")
    msg["Subject"] = f"Trade Approval — {len(setups)} setup(s) — {datetime.now().strftime('%b %d')}"
    msg["From"]    = EMAIL_SENDER
    msg["To"]      = EMAIL_RECEIVER
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.sendmail(EMAIL_SENDER, EMAIL_RECEIVER, msg.as_string())
        print(f"  Approval email sent — {len(setups)} setup(s)")
    except Exception as e:
        print(f"  Email failed: {e}")


# ─────────────────────────────────────────────
# 4. SAVE PENDING TRADES
# ─────────────────────────────────────────────

def save_pending(setups: list):
    """Save pending setups to JSON file waiting for approval."""
    with open(PENDING_FILE, "w") as f:
        json.dump(setups, f, indent=2)
    print(f"  {len(setups)} setup(s) saved as pending")


def load_pending() -> list:
    """Load pending setups from JSON file."""
    try:
        with open(PENDING_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return []


def clear_pending():
    """Clear all pending trades after processing."""
    if os.path.exists(PENDING_FILE):
        os.remove(PENDING_FILE)


# ─────────────────────────────────────────────
# 5. CHECK EMAIL REPLIES
# ─────────────────────────────────────────────

def check_email_replies() -> list:
    """
    Connect to Gmail via IMAP and read reply emails.
    Returns list of decisions: [{"ticker": "SAP", "decision": "YES"/"NO"}]
    """
    decisions = []
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(EMAIL_SENDER, EMAIL_PASSWORD)
        mail.select("inbox")

        # Search for unread emails from yourself (replies)
        today_str = date.today().strftime("%d-%b-%Y")
        _, msgs   = mail.search(None, f'(FROM "{EMAIL_RECEIVER}" SINCE "{today_str}" UNSEEN SUBJECT "Re:")')

        for msg_id in msgs[0].split():
            _, msg_data = mail.fetch(msg_id, "(RFC822)")
            raw         = msg_data[0][1]
            msg         = email.message_from_bytes(raw)

            # Get email body
            body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        body = part.get_payload(decode=True).decode("utf-8", errors="ignore")
                        break
            else:
                body = msg.get_payload(decode=True).decode("utf-8", errors="ignore")

            # Parse YES/NO decisions from body
            for line in body.upper().split("\n"):
                line = line.strip()
                if line.startswith("YES ") or line.startswith("NO "):
                    parts    = line.split()
                    decision = parts[0]
                    ticker   = parts[1] if len(parts) > 1 else ""
                    if ticker and decision in ["YES", "NO"]:
                        decisions.append({
                            "ticker":   ticker,
                            "decision": decision
                        })

            # Mark as read
            mail.store(msg_id, "+FLAGS", "\\Seen")

        mail.logout()

    except Exception as e:
        print(f"  Could not check email replies: {e}")

    return decisions


# ─────────────────────────────────────────────
# 6. LOG TO JOURNAL CSV
# ─────────────────────────────────────────────

def log_to_journal(setup: dict):
    """Log approved trade to journal CSV."""
    file_exists = os.path.exists(JOURNAL_CSV)

    row = {
        "date":        setup["scan_date"],
        "ticker":      setup["ticker"],
        "direction":   setup["direction"],
        "entry_price": setup["entry"],
        "stop_loss":   setup["stop"],
        "exit_price":  "",
        "quantity":    "",
        "pnl_eur":     "",
        "r_multiple":  "",
        "setup_type":  setup["setup"],
        "ai_tag":      f"Approved — {setup['setup']}",
        "ai_lesson":   setup.get("ai_commentary", "")[:100],
        "ai_quality":  "",
        "notes":       f"Auto-logged by trade executor. Conviction: {setup['conviction']}/100. {setup['reason']}",
    }

    with open(JOURNAL_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=JOURNAL_HEADERS)
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)

    print(f"  {setup['ticker']} logged to {JOURNAL_CSV}")


# ─────────────────────────────────────────────
# 7. LOG TO DECISIONS CSV
# ─────────────────────────────────────────────

def log_decision(setup: dict, decision: str, reason: str = ""):
    """Log every decision (YES or NO) to decisions_log.csv."""
    file_exists = os.path.exists(DECISIONS_CSV)

    row = {
        "date":          setup["scan_date"],
        "time":          setup["scan_time"],
        "ticker":        setup["ticker"],
        "setup_type":    setup["setup"],
        "direction":     setup["direction"],
        "entry_zone":    f"€{setup['entry']}",
        "stop_loss":     f"€{setup['stop']}",
        "target":        f"€{setup['target']}",
        "conviction":    setup["conviction"],
        "decision":      decision,
        "reason":        reason,
        "ai_commentary": setup.get("ai_commentary", ""),
    }

    with open(DECISIONS_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=DECISIONS_HEADERS)
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)


# ─────────────────────────────────────────────
# 8. PROCESS REPLIES
# ─────────────────────────────────────────────

def process_replies():
    """Check email for YES/NO replies and process each decision."""
    pending = load_pending()
    if not pending:
        print("  No pending trades to process")
        return

    print(f"\n  Checking email replies for {len(pending)} pending trade(s)...")
    decisions = check_email_replies()

    if not decisions:
        print("  No replies received yet")
        return

    pending_map = {s["ticker"].replace(".DE", ""): s for s in pending}
    processed   = set()

    for d in decisions:
        ticker  = d["ticker"]
        decision = d["decision"]
        setup   = pending_map.get(ticker)

        if not setup:
            continue

        if decision == "YES":
            print(f"  {ticker} APPROVED — logging to journal")
            log_to_journal(setup)
            log_decision(setup, "APPROVED", "User replied YES")
        else:
            print(f"  {ticker} REJECTED — logging decision")
            log_decision(setup, "REJECTED", "User replied NO")

        processed.add(ticker)

    # Keep unprocessed setups as still pending
    remaining = [s for s in pending if s["ticker"].replace(".DE", "") not in processed]
    if remaining:
        save_pending(remaining)
        print(f"  {len(remaining)} setup(s) still awaiting reply")
    else:
        clear_pending()
        print("  All pending trades processed")


# ─────────────────────────────────────────────
# 9. MAIN SCAN + SEND FLOW
# ─────────────────────────────────────────────

def run_scan_and_notify():
    """Full pipeline — scan, get AI commentary, send approval email."""
    print("\n" + "="*55)
    print(f"  Trade Executor — {datetime.now().strftime('%H:%M CET %d %b %Y')}")
    print("="*55 + "\n")

    if not ANTHROPIC_API_KEY:
        raise ValueError("Missing ANTHROPIC_API_KEY in .env")

    # Scan for setups
    setups = []
    for ticker in DAX_WATCHLIST:
        print(f"  Scanning {ticker:<12}", end=" ")
        df = fetch_data(ticker)
        if df is None:
            print("— No data")
            continue
        result = detect_setup(ticker, df)
        if result:
            print(f"{result['setup']} ({result['conviction']}/100)")
            setups.append(result)
        else:
            print("— No setup")

    if not setups:
        print("\n  No high-conviction setups today. No email sent.\n")
        return

    print(f"\n  Found {len(setups)} setup(s) — getting AI commentary...")

    # Get AI commentary for each
    for s in setups:
        s["ai_commentary"] = get_ai_commentary(s)
        print(f"  {s['ticker']} commentary ready")

    # Save as pending
    save_pending(setups)

    # Send approval email
    print("\n  Sending approval email...")
    send_approval_email(setups)

    print(f"\n  Done. Checking for replies every {CHECK_REPLIES_INTERVAL//60} minutes.")
    print(f"  Reply YES TICKER or NO TICKER to your email.\n")


# ─────────────────────────────────────────────
# 10. MAIN
# ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Human-in-the-Loop Trade Executor")
    parser.add_argument("--schedule", action="store_true", help="Auto-run at 08:30 every weekday")
    parser.add_argument("--check",    action="store_true", help="Check email replies now")
    args = parser.parse_args()

    # Just check replies
    if args.check:
        process_replies()
        return

    # Run once immediately (no schedule)
    if not args.schedule:
        run_scan_and_notify()
        # Keep checking replies every 10 minutes
        print("  Monitoring for replies... (Ctrl+C to stop)\n")
        while True:
            time.sleep(CHECK_REPLIES_INTERVAL)
            process_replies()
        return

    # Scheduled mode
    print("\n" + "="*55)
    print("  Trade Executor — Scheduled Mode")
    print("  Scan runs every weekday at 08:30 CET")
    print("  Replies checked every 10 minutes")
    print("  Keep this terminal open in background")
    print("="*55 + "\n")

    # Run once on startup
    run_scan_and_notify()

    # Schedule daily scan at 08:30
    schedule.every().monday.at("08:30").do(run_scan_and_notify)
    schedule.every().tuesday.at("08:30").do(run_scan_and_notify)
    schedule.every().wednesday.at("08:30").do(run_scan_and_notify)
    schedule.every().thursday.at("08:30").do(run_scan_and_notify)
    schedule.every().friday.at("08:30").do(run_scan_and_notify)

    schedule.every(CHECK_REPLIES_INTERVAL // 60).minutes.do(process_replies)

    print("  Scheduler running — Ctrl+C to stop\n")

    while True:
        try:
            schedule.run_pending()
            time.sleep(60)
        except KeyboardInterrupt:
            print("\n  Trade Executor stopped.\n")
            break


if __name__ == "__main__":
    main()
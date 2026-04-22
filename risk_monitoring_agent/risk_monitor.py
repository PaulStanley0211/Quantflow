import os
import csv
import time
import smtplib
import argparse
from datetime import datetime, date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import yfinance as yf
from dotenv import load_dotenv

load_dotenv()

EMAIL_SENDER      = os.getenv("EMAIL_SENDER")
EMAIL_PASSWORD    = os.getenv("EMAIL_PASSWORD")
EMAIL_RECEIVER    = os.getenv("EMAIL_RECEIVER")

# ─────────────────────────────────────────────
# RISK RULES — edit these to match your account
# ─────────────────────────────────────────────
DAILY_LOSS_LIMIT    = 500.0   # max loss per day in EUR
DAILY_PROFIT_TARGET = 300.0   # stop trading after hitting this profit
MAX_RISK_PER_TRADE  = 2.0     # max % of account per trade
DRAWDOWN_ALERT      = 100.0   # alert if single position down this much EUR
CHECK_INTERVAL_SECS = 300     # check every 5 minutes


# ─────────────────────────────────────────────
# 1. LOAD POSITIONS
# ─────────────────────────────────────────────

def load_positions_manual() -> list:
    """Enter open positions via terminal."""
    positions = []
    print("\n" + "="*50)
    print("  Enter Your Open Positions")
    print("="*50)
    print("  Enter each open position. Type 'done' when finished.\n")

    while True:
        ticker = input("  Ticker (e.g. SAP.DE) or 'done': ").strip().upper()
        if ticker == "DONE":
            break

        direction  = ""
        while direction not in ["BUY", "SHORT"]:
            direction = input("  Direction (BUY / SHORT): ").strip().upper()

        entry_price = float(input("  Entry price (€): ").strip())
        quantity    = float(input("  Quantity (shares): ").strip())

        sl_input   = input("  Stop loss (€) [press Enter to skip]: ").strip()
        stop_loss  = float(sl_input) if sl_input else 0.0

        positions.append({
            "ticker":      ticker,
            "direction":   direction,
            "entry_price": entry_price,
            "quantity":    quantity,
            "stop_loss":   stop_loss,
            "entry_date":  date.today().isoformat(),
        })

        print(f"  Added {ticker} {direction} x{int(quantity)} @ {entry_price}\n")

    return positions


def load_positions_csv(csv_file: str) -> list:
    """Load open positions from CSV — rows without an exit_price are considered open."""
    positions = []

    try:
        with open(csv_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                row = {k.lower().strip(): v.strip() for k, v in row.items()}

                exit_price = float(row.get("exit_price", 0) or 0)

                # Consider open if exit_price is 0 or not set
                if exit_price > 0:
                    continue

                ticker      = row.get("ticker", "")
                direction   = row.get("direction", "BUY").upper()
                entry_price = float(row.get("entry_price", 0) or 0)
                quantity    = float(row.get("quantity", 1) or 1)
                stop_loss   = float(row.get("stop_loss", 0) or 0)
                entry_date  = row.get("date", row.get("entry_date", ""))

                if ticker and entry_price > 0:
                    positions.append({
                        "ticker":      ticker,
                        "direction":   direction,
                        "entry_price": entry_price,
                        "quantity":    quantity,
                        "stop_loss":   stop_loss,
                        "entry_date":  entry_date,
                    })

        print(f"  Loaded {len(positions)} open positions from {csv_file}")
    except FileNotFoundError:
        print(f"  ERROR: CSV file not found: {csv_file}")

    return positions


# ─────────────────────────────────────────────
# 2. FETCH LIVE PRICES
# ─────────────────────────────────────────────

def fetch_live_price(ticker: str) -> float | None:
    """Fetch latest price for a ticker."""
    try:
        stock = yf.Ticker(ticker)
        hist  = stock.history(period="1d", interval="1m")
        if not hist.empty:
            return round(float(hist["Close"].iloc[-1]), 2)
        # Fallback to daily
        hist = stock.history(period="2d")
        if not hist.empty:
            return round(float(hist["Close"].iloc[-1]), 2)
        return None
    except Exception:
        return None


# ─────────────────────────────────────────────
# 3. CALCULATE P&L PER POSITION
# ─────────────────────────────────────────────

def calculate_pnl(position: dict, live_price: float) -> float:
    """Calculate current unrealised P&L."""
    entry = position["entry_price"]
    qty   = position["quantity"]
    if position["direction"] in ["BUY", "LONG"]:
        return round((live_price - entry) * qty, 2)
    else:
        return round((entry - live_price) * qty, 2)


# ─────────────────────────────────────────────
# 4. CHECK RISK RULES
# ─────────────────────────────────────────────

def check_risk_rules(positions: list, live_prices: dict, account_size: float) -> tuple:
    """
    Check all risk rules against current positions.
    Returns list of alert dicts.
    """
    alerts      = []
    total_pnl   = 0.0
    position_pnls = []

    for pos in positions:
        ticker     = pos["ticker"]
        live_price = live_prices.get(ticker)

        if live_price is None:
            continue

        pnl = calculate_pnl(pos, live_price)
        total_pnl += pnl
        position_pnls.append({**pos, "live_price": live_price, "pnl": pnl})

        # ── Rule 3: Stop loss missing ─────────
        if pos["stop_loss"] == 0:
            alerts.append({
                "level":   "WARNING",
                "rule":    "No Stop Loss",
                "ticker":  ticker,
                "message": f"{ticker} has NO stop loss defined — define one immediately",
                "pnl":     pnl,
                "price":   live_price,
            })

        # ── Rule 4: Single trade drawdown ─────
        if pnl <= -DRAWDOWN_ALERT:
            alerts.append({
                "level":   "DANGER",
                "rule":    "Trade Drawdown",
                "ticker":  ticker,
                "message": f"{ticker} is down €{abs(pnl):.2f} — consider cutting or reviewing stop loss",
                "pnl":     pnl,
                "price":   live_price,
            })

        # ── Stop loss breached ─────────────────
        if pos["stop_loss"] > 0:
            sl = pos["stop_loss"]
            if pos["direction"] in ["BUY", "LONG"] and live_price <= sl:
                alerts.append({
                    "level":   "CRITICAL",
                    "rule":    "Stop Loss Hit",
                    "ticker":  ticker,
                    "message": f"{ticker} has hit your stop loss at €{sl} — current price €{live_price}. EXIT NOW.",
                    "pnl":     pnl,
                    "price":   live_price,
                })
            elif pos["direction"] in ["SHORT", "SELL"] and live_price >= sl:
                alerts.append({
                    "level":   "CRITICAL",
                    "rule":    "Stop Loss Hit",
                    "ticker":  ticker,
                    "message": f"{ticker} has hit your stop loss at €{sl} — current price €{live_price}. EXIT NOW.",
                    "pnl":     pnl,
                    "price":   live_price,
                })

        # ── Rule 2: Position size too large ───
        risk_eur = abs(pos["entry_price"] - pos["stop_loss"]) * pos["quantity"] if pos["stop_loss"] > 0 else 0
        if risk_eur > 0:
            risk_pct = (risk_eur / account_size) * 100
            if risk_pct > MAX_RISK_PER_TRADE:
                alerts.append({
                    "level":   "WARNING",
                    "rule":    "Oversized Position",
                    "ticker":  ticker,
                    "message": f"{ticker} risks €{risk_eur:.2f} ({risk_pct:.1f}% of account) — exceeds {MAX_RISK_PER_TRADE}% rule",
                    "pnl":     pnl,
                    "price":   live_price,
                })

    # ── Rule 1: Daily loss limit ───────────────
    if total_pnl <= -DAILY_LOSS_LIMIT:
        alerts.append({
            "level":   "CRITICAL",
            "rule":    "Daily Loss Limit",
            "ticker":  "ACCOUNT",
            "message": f"DAILY LOSS LIMIT HIT — Total P&L: -€{abs(total_pnl):.2f}. STOP TRADING TODAY.",
            "pnl":     total_pnl,
            "price":   0,
        })

    # ── Rule 5: Daily profit lock ─────────────
    if total_pnl >= DAILY_PROFIT_TARGET:
        alerts.append({
            "level":   "INFO",
            "rule":    "Profit Target Hit",
            "ticker":  "ACCOUNT",
            "message": f"DAILY PROFIT TARGET HIT — Total P&L: +€{total_pnl:.2f}. Consider stopping trading to protect gains.",
            "pnl":     total_pnl,
            "price":   0,
        })

    return alerts, total_pnl, position_pnls


# ─────────────────────────────────────────────
# 5. SEND EMAIL ALERT
# ─────────────────────────────────────────────

def send_alert_email(alerts: list, total_pnl: float, position_pnls: list):
    """Send risk alert email."""
    if not all([EMAIL_SENDER, EMAIL_PASSWORD, EMAIL_RECEIVER]):
        print("  WARNING: Email credentials not set — printing alerts only")
        return

    now        = datetime.now().strftime("%H:%M CET")
    today      = datetime.now().strftime("%B %d, %Y")
    pnl_color  = "#00c853" if total_pnl >= 0 else "#ff3d00"
    pnl_sign   = "+" if total_pnl >= 0 else ""

    LEVEL_COLORS = {
        "CRITICAL": ("#ff3d00", "#ff000015"),
        "DANGER":   ("#ff6d00", "#ff6d0015"),
        "WARNING":  ("#ffcc00", "#ffcc0015"),
        "INFO":     ("#00c853", "#00c85315"),
    }

    # Alert rows
    alert_rows = ""
    for a in alerts:
        fg, bg = LEVEL_COLORS.get(a["level"], ("#888", "#88888815"))
        alert_rows += f"""
        <div style="background:{bg};border-left:4px solid {fg};border-radius:0 8px 8px 0;padding:12px 16px;margin-bottom:10px">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px">
            <span style="color:{fg};font-weight:600;font-size:13px">{a['level']} — {a['rule']}</span>
            <span style="color:{fg};font-size:12px">{a['ticker']}</span>
          </div>
          <p style="color:#333;font-size:13px;margin:0;line-height:1.5">{a['message']}</p>
        </div>"""

    # Position rows
    pos_rows = ""
    for p in position_pnls:
        pnl_c = "#00c853" if p["pnl"] >= 0 else "#ff3d00"
        sign  = "+" if p["pnl"] >= 0 else ""
        sl    = f"€{p['stop_loss']}" if p["stop_loss"] > 0 else "NOT SET"
        pos_rows += f"""
        <tr style="border-bottom:1px solid #eee">
          <td style="padding:8px 12px;font-weight:600">{p['ticker'].replace('.DE','')}</td>
          <td style="padding:8px 12px">{p['direction']}</td>
          <td style="padding:8px 12px">€{p['entry_price']}</td>
          <td style="padding:8px 12px">€{p['live_price']}</td>
          <td style="padding:8px 12px;color:{pnl_c};font-weight:600">{sign}€{abs(p['pnl']):.2f}</td>
          <td style="padding:8px 12px;color:{'#ff3d00' if p['stop_loss']==0 else '#333'}">{sl}</td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="font-family:Arial,sans-serif;max-width:650px;margin:auto;background:#f9fafb;padding:24px">

  <div style="background:#1e293b;color:white;padding:20px 24px;border-radius:10px 10px 0 0">
    <h2 style="margin:0;font-size:20px">Risk Monitor Alert</h2>
    <p style="margin:4px 0 0;color:#94a3b8;font-size:13px">{today} · {now} · {len(alerts)} alert(s)</p>
  </div>

  <div style="background:white;padding:20px 24px;border:1px solid #e5e7eb;border-top:none">

    <div style="display:flex;gap:16px;margin-bottom:20px">
      <div style="flex:1;background:#f8fafc;border-radius:8px;padding:14px;text-align:center">
        <div style="font-size:22px;font-weight:700;color:{pnl_color}">{pnl_sign}€{abs(total_pnl):.2f}</div>
        <div style="font-size:11px;color:#888;margin-top:2px">Total P&L</div>
      </div>
      <div style="flex:1;background:#f8fafc;border-radius:8px;padding:14px;text-align:center">
        <div style="font-size:22px;font-weight:700;color:#1e293b">{len(position_pnls)}</div>
        <div style="font-size:11px;color:#888;margin-top:2px">Open Positions</div>
      </div>
      <div style="flex:1;background:#f8fafc;border-radius:8px;padding:14px;text-align:center">
        <div style="font-size:22px;font-weight:700;color:#ff3d00">{len(alerts)}</div>
        <div style="font-size:11px;color:#888;margin-top:2px">Active Alerts</div>
      </div>
    </div>

    <h3 style="color:#1e293b;margin:0 0 12px">Risk Alerts</h3>
    {alert_rows}

    <h3 style="color:#1e293b;margin:16px 0 10px">Open Positions</h3>
    <table style="width:100%;border-collapse:collapse;font-size:13px">
      <thead>
        <tr style="background:#f1f5f9;color:#475569">
          <th style="padding:8px 12px;text-align:left">Ticker</th>
          <th style="padding:8px 12px;text-align:left">Dir</th>
          <th style="padding:8px 12px;text-align:left">Entry</th>
          <th style="padding:8px 12px;text-align:left">Live</th>
          <th style="padding:8px 12px;text-align:left">P&L</th>
          <th style="padding:8px 12px;text-align:left">Stop</th>
        </tr>
      </thead>
      <tbody>{pos_rows}</tbody>
    </table>

    <div style="background:#fef3c7;border-left:4px solid #f59e0b;padding:12px 16px;margin-top:16px;border-radius:0 8px 8px 0">
      <p style="margin:0;font-size:12px;color:#92400e">
        <b>Risk Rules Active:</b> Daily loss limit €{DAILY_LOSS_LIMIT:.0f} · Daily profit target €{DAILY_PROFIT_TARGET:.0f} · Max risk per trade {MAX_RISK_PER_TRADE}% · Drawdown alert €{DRAWDOWN_ALERT:.0f}
      </p>
    </div>

  </div>

  <div style="background:#f1f5f9;padding:10px 24px;border-radius:0 0 10px 10px;text-align:center">
    <p style="margin:0;font-size:11px;color:#94a3b8">Risk Monitor Agent · German Market Edition · {now}</p>
  </div>

</body>
</html>"""

    msg             = MIMEMultipart("alternative")
    msg["Subject"]  = f"Risk Alert — {len(alerts)} alert(s) — P&L {pnl_sign}€{abs(total_pnl):.2f}"
    msg["From"]     = EMAIL_SENDER
    msg["To"]       = EMAIL_RECEIVER
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.sendmail(EMAIL_SENDER, EMAIL_RECEIVER, msg.as_string())
        print(f"  Alert email sent to {EMAIL_RECEIVER}")
    except Exception as e:
        print(f"  ERROR: Email failed: {e}")


# ─────────────────────────────────────────────
# 6. PRINT DASHBOARD TO TERMINAL
# ─────────────────────────────────────────────

def print_dashboard(position_pnls: list, alerts: list, total_pnl: float):
    """Print a clean terminal dashboard."""
    now       = datetime.now().strftime("%H:%M:%S")
    pnl_sign  = "+" if total_pnl >= 0 else ""

    print(f"\n{'='*55}")
    print(f"  Risk Monitor — {now}")
    print(f"{'='*55}")
    print(f"  Total P&L    : {pnl_sign}€{total_pnl:.2f}")
    print(f"  Loss limit   : €{DAILY_LOSS_LIMIT:.0f}  ({abs(total_pnl)/DAILY_LOSS_LIMIT*100:.1f}% used)")
    print(f"  Open positions: {len(position_pnls)}")
    print(f"{'─'*55}")

    for p in position_pnls:
        pnl_sign_p = "+" if p["pnl"] >= 0 else ""
        sl_status  = f"SL: €{p['stop_loss']}" if p["stop_loss"] > 0 else "NO STOP"
        print(f"  {p['ticker']:<12} {p['direction']:<6} €{p['live_price']:<10} {pnl_sign_p}€{p['pnl']:<10.2f} {sl_status}")

    if alerts:
        print(f"\n  ALERTS ({len(alerts)}):")
        for a in alerts:
            print(f"  [{a['level']}] {a['message']}")
    else:
        print(f"\n  All clear — no risk rules breached")

    print(f"{'='*55}")
    print(f"  Next check in {CHECK_INTERVAL_SECS//60} minutes... (Ctrl+C to stop)\n")


# ─────────────────────────────────────────────
# 7. MAIN MONITORING LOOP
# ─────────────────────────────────────────────

def monitor(positions: list, account_size: float):
    """Main monitoring loop — runs every 5 minutes."""
    if not positions:
        print("\n  No open positions to monitor. Exiting.\n")
        return

    print(f"\n  Monitoring {len(positions)} position(s)")
    print(f"  Alerts sent to: {EMAIL_RECEIVER}")
    print(f"  Checking every {CHECK_INTERVAL_SECS//60} minutes")
    print(f"  Daily loss limit: €{DAILY_LOSS_LIMIT:.0f}")
    print(f"  Daily profit target: €{DAILY_PROFIT_TARGET:.0f}")
    print(f"  Press Ctrl+C to stop\n")

    alerted_rules = set()  # track which alerts already sent to avoid spam

    while True:
        try:
            # Fetch live prices
            live_prices = {}
            for pos in positions:
                ticker = pos["ticker"]
                price  = fetch_live_price(ticker)
                if price is not None:
                    live_prices[ticker] = price

            # Check risk rules
            alerts, total_pnl, position_pnls = check_risk_rules(
                positions, live_prices, account_size
            )

            # Print terminal dashboard
            print_dashboard(position_pnls, alerts, total_pnl)

            # Only email NEW alerts (avoid spamming same alert every 5 min)
            new_alerts = []
            for a in alerts:
                alert_key = f"{a['rule']}_{a['ticker']}"
                if alert_key not in alerted_rules:
                    new_alerts.append(a)
                    alerted_rules.add(alert_key)

            if new_alerts:
                send_alert_email(new_alerts, total_pnl, position_pnls)

            # Stop if daily loss limit hit
            if any(a["rule"] == "Daily Loss Limit" for a in alerts):
                print("  DAILY LOSS LIMIT REACHED — Monitor stopping.\n")
                break

            time.sleep(CHECK_INTERVAL_SECS)

        except KeyboardInterrupt:
            print("\n\n  Risk Monitor stopped.\n")
            break
        except Exception as e:
            print(f"\n  ERROR: {e} — retrying in 60s")
            time.sleep(60)


# ─────────────────────────────────────────────
# 8. MAIN
# ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Risk Monitor Agent")
    parser.add_argument("--csv",       default="",         help="Load positions from CSV file")
    parser.add_argument("--account",   type=float, default=10000.0, help="Account size in EUR")
    parser.add_argument("--no-manual", action="store_true", help="Skip manual position entry prompt")
    args = parser.parse_args()

    print("\n" + "="*55)
    print("  Risk Monitor Agent — German Market Edition")
    print(f"  Account size : €{args.account:,.0f}")
    print(f"  Loss limit   : €{DAILY_LOSS_LIMIT:.0f}")
    print(f"  Profit target: €{DAILY_PROFIT_TARGET:.0f}")
    print("="*55)

    positions = []

    # Load from CSV if provided
    if args.csv:
        csv_positions = load_positions_csv(args.csv)
        positions.extend(csv_positions)
        print(f"\n  Loaded {len(csv_positions)} position(s) from {args.csv}")

    if not args.no_manual:
        add_manual = input("\n  Add positions manually? (y/n): ").strip().lower()
        if add_manual == "y":
            manual_positions = load_positions_manual()
            positions.extend(manual_positions)

    # Start monitoring
    monitor(positions, args.account)


if __name__ == "__main__":
    main()
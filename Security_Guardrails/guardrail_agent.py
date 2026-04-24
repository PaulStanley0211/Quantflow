"""
guardrail_agent.py — Security Guardrails Agent
=================================================
Pre-trade risk checker for the QuantFlow system.
Every trade is checked against your rules before
it is logged, approved, or executed.

7 Checks performed on every trade:
1. Stop loss defined
2. Position size within account limits
3. Risk/reward ratio acceptable
4. Daily loss limit not breached
5. Daily trade limit not exceeded
6. Ticker not on blocked list
7. No duplicate open position

Usage:
    python guardrail_agent.py                    # check a single trade manually
    python guardrail_agent.py --csv trades.csv   # check all trades in a CSV file
    python guardrail_agent.py --report           # generate full risk report
"""

import os
import csv
import json
import smtplib
import argparse
from datetime import datetime, date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from dotenv import load_dotenv

load_dotenv()

EMAIL_SENDER   = os.getenv("EMAIL_SENDER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_RECEIVER = os.getenv("EMAIL_RECEIVER")

# ─────────────────────────────────────────────
# GUARDRAIL RULES — edit these to match your setup
# ─────────────────────────────────────────────
RULES = {
    "account_size":        10000.0,  # your total account in EUR
    "max_risk_pct":        2.0,      # max % of account per trade
    "min_risk_reward":     1.5,      # minimum acceptable R/R ratio
    "daily_loss_limit":    500.0,    # max daily loss in EUR
    "daily_trade_limit":   5,        # max trades per day
    "blocked_tickers":     [],       # tickers you never want to trade e.g. ["BAYN.DE"]
    "require_stop_loss":   True,     # stop loss is mandatory
    "max_position_size":   200,      # max shares per trade
}

# Track daily state
DAILY_STATE_FILE = "daily_state.json"


# ─────────────────────────────────────────────
# 1. DAILY STATE MANAGEMENT
# ─────────────────────────────────────────────

def load_daily_state() -> dict:
    """Load today's trading state — resets every day."""
    today = date.today().isoformat()
    try:
        with open(DAILY_STATE_FILE, "r") as f:
            state = json.load(f)
        if state.get("date") != today:
            return reset_daily_state()
        return state
    except Exception:
        return reset_daily_state()


def reset_daily_state() -> dict:
    """Reset daily state for a new trading day."""
    state = {
        "date":           date.today().isoformat(),
        "daily_pnl":      0.0,
        "trade_count":    0,
        "open_positions": [],
        "blocked_today":  [],
    }
    save_daily_state(state)
    return state


def save_daily_state(state: dict):
    """Save current daily state."""
    with open(DAILY_STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def update_daily_state(trade: dict, result: str):
    """Update daily state after a trade is approved."""
    state = load_daily_state()
    if result == "APPROVED":
        state["trade_count"] += 1
        state["open_positions"].append(trade["ticker"])
    save_daily_state(state)


# ─────────────────────────────────────────────
# 2. INDIVIDUAL GUARDRAIL CHECKS
# ─────────────────────────────────────────────

def check_stop_loss(trade: dict) -> dict:
    """Check 1 — Stop loss must be defined."""
    if not RULES["require_stop_loss"]:
        return {"passed": True, "rule": "Stop Loss", "message": "Stop loss check disabled"}

    stop = float(trade.get("stop_loss", 0) or 0)
    if stop == 0:
        return {
            "passed":  False,
            "rule":    "Stop Loss Missing",
            "message": f"No stop loss defined for {trade['ticker']}. Define a stop loss before proceeding.",
            "fix":     "Add a stop loss level based on your technical analysis. Minimum 1x ATR below entry for longs.",
        }

    entry     = float(trade.get("entry_price", 0))
    direction = trade.get("direction", "BUY").upper()

    if direction in ["BUY", "LONG"] and stop >= entry:
        return {
            "passed":  False,
            "rule":    "Stop Loss Invalid",
            "message": f"Stop loss €{stop} must be BELOW entry €{entry} for a BUY trade.",
            "fix":     f"Set stop loss below €{entry}.",
        }
    elif direction in ["SHORT", "SELL"] and stop <= entry:
        return {
            "passed":  False,
            "rule":    "Stop Loss Invalid",
            "message": f"Stop loss €{stop} must be ABOVE entry €{entry} for a SHORT trade.",
            "fix":     f"Set stop loss above €{entry}.",
        }

    return {
        "passed":  True,
        "rule":    "Stop Loss",
        "message": f"Stop loss €{stop} correctly placed.",
    }


def check_position_size(trade: dict) -> dict:
    """Check 2 — Position size must not exceed max risk % of account."""
    entry    = float(trade.get("entry_price", 0))
    stop     = float(trade.get("stop_loss",   0) or 0)
    quantity = float(trade.get("quantity",     0) or 0)

    if stop == 0 or entry == 0 or quantity == 0:
        return {
            "passed":  False,
            "rule":    "Position Size",
            "message": "Cannot check position size — entry, stop, or quantity missing.",
            "fix":     "Provide entry price, stop loss, and quantity.",
        }

    risk_per_share = abs(entry - stop)
    total_risk     = risk_per_share * quantity
    risk_pct       = (total_risk / RULES["account_size"]) * 100
    max_risk_eur   = RULES["account_size"] * (RULES["max_risk_pct"] / 100)

    if risk_pct > RULES["max_risk_pct"]:
        max_qty = int(max_risk_eur / risk_per_share) if risk_per_share > 0 else 0
        return {
            "passed":  False,
            "rule":    "Position Too Large",
            "message": f"This trade risks €{total_risk:.2f} ({risk_pct:.1f}% of account). Max allowed: {RULES['max_risk_pct']}% (€{max_risk_eur:.2f}).",
            "fix":     f"Reduce quantity to {max_qty} shares to stay within {RULES['max_risk_pct']}% risk limit.",
        }

    if quantity > RULES["max_position_size"]:
        return {
            "passed":  False,
            "rule":    "Position Too Large",
            "message": f"Quantity {int(quantity)} shares exceeds maximum allowed {RULES['max_position_size']} shares.",
            "fix":     f"Reduce quantity to {RULES['max_position_size']} shares or less.",
        }

    return {
        "passed":  True,
        "rule":    "Position Size",
        "message": f"Position size OK — risking €{total_risk:.2f} ({risk_pct:.1f}% of account).",
    }


def check_risk_reward(trade: dict) -> dict:
    """Check 3 — Risk/reward ratio must meet minimum."""
    entry     = float(trade.get("entry_price", 0))
    stop      = float(trade.get("stop_loss",   0) or 0)
    target    = float(trade.get("target",      0) or 0)
    direction = trade.get("direction", "BUY").upper()

    if target == 0:
        return {
            "passed":  True,
            "rule":    "Risk/Reward",
            "message": "No target defined — R/R check skipped. Consider defining a target.",
        }

    if stop == 0 or entry == 0:
        return {
            "passed":  False,
            "rule":    "Risk/Reward",
            "message": "Cannot calculate R/R — entry or stop missing.",
            "fix":     "Provide both entry price and stop loss.",
        }

    if direction in ["BUY", "LONG"] and target <= entry:
        return {
            "passed":  False,
            "rule":    "Target Invalid",
            "message": f"Target €{target} must be above entry €{entry} for a BUY trade.",
            "fix":     f"Set target above €{entry}.",
        }
    elif direction in ["SHORT", "SELL"] and target >= entry:
        return {
            "passed":  False,
            "rule":    "Target Invalid",
            "message": f"Target €{target} must be below entry €{entry} for a SHORT trade.",
            "fix":     f"Set target below €{entry}.",
        }

    risk   = abs(entry - stop)
    reward = abs(target - entry)
    rr     = round(reward / risk, 2) if risk > 0 else 0

    if rr < RULES["min_risk_reward"]:
        if direction in ["BUY", "LONG"]:
            min_target = round(entry + risk * RULES["min_risk_reward"], 2)
            fix_msg    = f"Move target to at least €{min_target} to achieve {RULES['min_risk_reward']}:1 R/R."
        else:
            min_target = round(entry - risk * RULES["min_risk_reward"], 2)
            fix_msg    = f"Move target to at most €{min_target} to achieve {RULES['min_risk_reward']}:1 R/R."
        return {
            "passed":  False,
            "rule":    "Risk/Reward Too Low",
            "message": f"R/R ratio is {rr}:1 — minimum required is {RULES['min_risk_reward']}:1.",
            "fix":     fix_msg,
        }

    return {
        "passed":  True,
        "rule":    "Risk/Reward",
        "message": f"R/R ratio {rr}:1 — meets minimum requirement of {RULES['min_risk_reward']}:1.",
    }


def check_daily_loss_limit(trade: dict) -> dict:
    """Check 4 — Daily loss limit must not be breached."""
    state     = load_daily_state()
    daily_pnl = state.get("daily_pnl", 0.0)

    if daily_pnl <= -RULES["daily_loss_limit"]:
        return {
            "passed":  False,
            "rule":    "Daily Loss Limit",
            "message": f"Daily loss limit hit — P&L today: -€{abs(daily_pnl):.2f}. No more trades allowed today.",
            "fix":     "Stop trading for today. Come back tomorrow with a fresh mindset.",
        }

    remaining = RULES["daily_loss_limit"] - abs(daily_pnl)
    return {
        "passed":  True,
        "rule":    "Daily Loss Limit",
        "message": f"Daily loss limit OK — €{remaining:.2f} remaining before limit.",
    }


def check_daily_trade_limit(trade: dict) -> dict:
    """Check 5 — Daily trade count must not exceed limit."""
    state       = load_daily_state()
    trade_count = state.get("trade_count", 0)

    if trade_count >= RULES["daily_trade_limit"]:
        return {
            "passed":  False,
            "rule":    "Daily Trade Limit",
            "message": f"Daily trade limit reached — {trade_count}/{RULES['daily_trade_limit']} trades taken today.",
            "fix":     "You have reached your maximum trades for today. Stop trading.",
        }

    remaining = RULES["daily_trade_limit"] - trade_count
    return {
        "passed":  True,
        "rule":    "Daily Trade Limit",
        "message": f"Trade count OK — {trade_count}/{RULES['daily_trade_limit']} trades today. {remaining} remaining.",
    }


def check_blocked_ticker(trade: dict) -> dict:
    """Check 6 — Ticker must not be on blocked list."""
    ticker = trade.get("ticker", "").upper()

    if ticker in [t.upper() for t in RULES["blocked_tickers"]]:
        return {
            "passed":  False,
            "rule":    "Blocked Ticker",
            "message": f"{ticker} is on your blocked list. This ticker is not allowed.",
            "fix":     f"Remove {ticker} from your blocked list in config if you want to trade it again.",
        }

    return {
        "passed":  True,
        "rule":    "Blocked Ticker",
        "message": f"{ticker} is not blocked.",
    }


def check_duplicate_position(trade: dict) -> dict:
    """Check 7 — No duplicate open positions in same ticker."""
    state          = load_daily_state()
    open_positions = state.get("open_positions", [])
    ticker         = trade.get("ticker", "").upper()

    if ticker in [t.upper() for t in open_positions]:
        return {
            "passed":  False,
            "rule":    "Duplicate Position",
            "message": f"You already have an open position in {ticker}. No duplicate positions allowed.",
            "fix":     "Close your existing position before opening a new one in the same ticker.",
        }

    return {
        "passed":  True,
        "rule":    "Duplicate Position",
        "message": f"No existing position in {ticker}.",
    }


# ─────────────────────────────────────────────
# 3. RUN ALL CHECKS
# ─────────────────────────────────────────────

def run_all_checks(trade: dict) -> dict:
    """Run all 7 guardrail checks on a trade. Returns full result."""
    checks = [
        check_stop_loss(trade),
        check_position_size(trade),
        check_risk_reward(trade),
        check_daily_loss_limit(trade),
        check_daily_trade_limit(trade),
        check_blocked_ticker(trade),
        check_duplicate_position(trade),
    ]

    passed  = [c for c in checks if c["passed"]]
    failed  = [c for c in checks if not c["passed"]]
    overall = len(failed) == 0

    return {
        "ticker":    trade.get("ticker", ""),
        "overall":   overall,
        "result":    "APPROVED" if overall else "BLOCKED",
        "checks":    checks,
        "passed":    passed,
        "failed":    failed,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


# ─────────────────────────────────────────────
# 4. DISPLAY RESULT IN TERMINAL
# ─────────────────────────────────────────────

def display_result(result: dict, trade: dict):
    """Print a clean terminal result."""
    ticker   = result["ticker"]
    overall  = result["result"]
    icon_ok  = "[OK]"
    icon_bad = "[!]"

    print(f"\n{'='*55}")
    print(f"  Security Guardrails — {ticker}")
    print(f"  {datetime.now().strftime('%H:%M:%S')} · Account: €{RULES['account_size']:,.0f}")
    print(f"{'='*55}")

    for check in result["checks"]:
        icon = icon_ok if check["passed"] else icon_bad
        print(f"  {icon} {check['rule']:<25} {check['message'].split('—')[0].strip()}")

    print(f"{'─'*55}")

    if overall == "APPROVED":
        entry    = float(trade.get("entry_price", 0))
        stop     = float(trade.get("stop_loss",   0) or 0)
        quantity = float(trade.get("quantity",     0) or 0)
        risk     = abs(entry - stop) * quantity
        print(f"\n  TRADE APPROVED")
        print(f"  {ticker} — Risk: €{risk:.2f} — Ready to execute\n")
        update_daily_state(trade, "APPROVED")
    else:
        print(f"\n  TRADE BLOCKED — {len(result['failed'])} rule(s) violated\n")
        for f in result["failed"]:
            print(f"  Rule   : {f['rule']}")
            print(f"  Problem: {f['message']}")
            if f.get("fix"):
                print(f"  Fix    : {f['fix']}")
            print()


# ─────────────────────────────────────────────
# 5. SEND EMAIL ALERT FOR BLOCKED TRADES
# ─────────────────────────────────────────────

def send_blocked_alert(result: dict, trade: dict):
    """Send email when a trade is blocked."""
    if not all([EMAIL_SENDER, EMAIL_PASSWORD, EMAIL_RECEIVER]):
        return

    ticker = result["ticker"]
    failed = result["failed"]
    today  = datetime.now().strftime("%B %d, %Y · %H:%M CET")

    failed_rows = ""
    for f in failed:
        failed_rows += f"""
        <div style="background:#fff5f5;border-left:4px solid #ff3d00;padding:12px 16px;margin-bottom:10px;border-radius:0 8px 8px 0">
          <div style="font-weight:600;color:#ff3d00;margin-bottom:4px">{f['rule']}</div>
          <div style="font-size:13px;color:#333;margin-bottom:4px">{f['message']}</div>
          {f'<div style="font-size:12px;color:#666">Fix: {f["fix"]}</div>' if f.get("fix") else ""}
        </div>"""

    html = f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="font-family:Arial,sans-serif;max-width:600px;margin:auto;background:#f9fafb;padding:24px">
  <div style="background:#1e293b;color:white;padding:18px 24px;border-radius:10px 10px 0 0">
    <h2 style="margin:0;font-size:18px">Trade Blocked — Guardrails Alert</h2>
    <p style="margin:4px 0 0;color:#94a3b8;font-size:13px">{today}</p>
  </div>
  <div style="background:white;padding:20px 24px;border:1px solid #e5e7eb;border-top:none">
    <p style="font-size:14px;color:#374151;margin:0 0 16px">
      The following trade was <b style="color:#ff3d00">BLOCKED</b> by the Security Guardrails Agent:
    </p>
    <div style="background:#f8fafc;border:1px solid #e5e7eb;border-radius:8px;padding:14px;margin-bottom:16px;font-size:13px">
      <b>Ticker:</b> {ticker} &nbsp;|&nbsp;
      <b>Direction:</b> {trade.get('direction', '?')} &nbsp;|&nbsp;
      <b>Entry:</b> €{trade.get('entry_price', '?')} &nbsp;|&nbsp;
      <b>Stop:</b> €{trade.get('stop_loss', '?')} &nbsp;|&nbsp;
      <b>Qty:</b> {trade.get('quantity', '?')}
    </div>
    <h3 style="color:#1e293b;margin:0 0 12px">Rules Violated ({len(failed)})</h3>
    {failed_rows}
  </div>
  <div style="background:#f1f5f9;padding:10px 24px;border-radius:0 0 10px 10px;text-align:center">
    <p style="margin:0;font-size:11px;color:#94a3b8">Security Guardrails Agent · QuantFlow · {datetime.now().strftime('%H:%M CET')}</p>
  </div>
</body>
</html>"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Trade Blocked — {ticker} — {len(failed)} rule(s) violated"
    msg["From"]    = EMAIL_SENDER
    msg["To"]      = EMAIL_RECEIVER
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.sendmail(EMAIL_SENDER, EMAIL_RECEIVER, msg.as_string())
        print(f"  Alert email sent to {EMAIL_RECEIVER}")
    except Exception as e:
        print(f"  Email failed: {e}")


# ─────────────────────────────────────────────
# 6. COLLECT TRADE INPUT FROM TERMINAL
# ─────────────────────────────────────────────

def collect_trade_input() -> dict:
    """Ask user to enter trade details in terminal."""
    print("\n" + "="*55)
    print("  Security Guardrails — Trade Checker")
    print("="*55)
    print("  Enter trade details to check against your rules\n")

    ticker    = input("  Ticker (e.g. SAP.DE): ").strip().upper()
    direction = ""
    while direction not in ["BUY", "SHORT"]:
        direction = input("  Direction (BUY / SHORT): ").strip().upper()

    entry    = float(input("  Entry price (€): ").strip())
    stop     = float(input("  Stop loss (€): ").strip() or "0")
    target   = float(input("  Target (€) [press Enter to skip]: ").strip() or "0")
    quantity = float(input("  Quantity (shares): ").strip())

    return {
        "ticker":      ticker,
        "direction":   direction,
        "entry_price": entry,
        "stop_loss":   stop,
        "target":      target,
        "quantity":    quantity,
    }


# ─────────────────────────────────────────────
# 7. CHECK TRADES FROM CSV
# ─────────────────────────────────────────────

def check_csv(csv_file: str):
    """Run guardrails checks on all trades in a CSV file."""
    print(f"\n  Checking trades from {csv_file}...\n")

    approved = 0
    blocked  = 0

    with open(csv_file, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            row   = {k.lower().strip(): v.strip() for k, v in row.items()}
            trade = {
                "ticker":      row.get("ticker", ""),
                "direction":   row.get("direction", "BUY").upper(),
                "entry_price": float(row.get("entry_price", 0) or 0),
                "stop_loss":   float(row.get("stop_loss",   0) or 0),
                "target":      float(row.get("target",      0) or 0),
                "quantity":    float(row.get("quantity",    1) or 1),
            }

            result = run_all_checks(trade)
            display_result(result, trade)

            if result["overall"]:
                approved += 1
            else:
                blocked += 1
                send_blocked_alert(result, trade)

    print(f"\n{'='*55}")
    print(f"  CSV Check Complete")
    print(f"  Approved : {approved}")
    print(f"  Blocked  : {blocked}")
    print(f"{'='*55}\n")


# ─────────────────────────────────────────────
# 8. GENERATE RISK REPORT
# ─────────────────────────────────────────────

def generate_report():
    """Generate a daily risk rules summary report."""
    state = load_daily_state()

    print(f"\n{'='*55}")
    print(f"  QuantFlow — Risk Rules Report")
    print(f"  {datetime.now().strftime('%A %B %d %Y · %H:%M CET')}")
    print(f"{'='*55}")
    print(f"\n  ACCOUNT RULES:")
    print(f"  Account size      : €{RULES['account_size']:,.0f}")
    print(f"  Max risk per trade: {RULES['max_risk_pct']}% (€{RULES['account_size'] * RULES['max_risk_pct'] / 100:.0f})")
    print(f"  Min R/R ratio     : {RULES['min_risk_reward']}:1")
    print(f"  Daily loss limit  : €{RULES['daily_loss_limit']:.0f}")
    print(f"  Daily trade limit : {RULES['daily_trade_limit']} trades")
    print(f"  Require stop loss : {'Yes' if RULES['require_stop_loss'] else 'No'}")
    print(f"  Blocked tickers   : {', '.join(RULES['blocked_tickers']) or 'None'}")
    print(f"\n  TODAY'S STATUS:")
    print(f"  Date              : {state['date']}")
    print(f"  Trades taken      : {state['trade_count']}/{RULES['daily_trade_limit']}")
    print(f"  Daily P&L         : €{state['daily_pnl']:.2f}")
    print(f"  Open positions    : {', '.join(state['open_positions']) or 'None'}")
    print(f"{'='*55}\n")


# ─────────────────────────────────────────────
# 9. MAIN
# ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Security Guardrails Agent")
    parser.add_argument("--csv",    default="", help="Check all trades in a CSV file")
    parser.add_argument("--report", action="store_true", help="Show risk rules report")
    args = parser.parse_args()

    print("\n" + "="*55)
    print("  QuantFlow — Security Guardrails Agent")
    print(f"  Account: €{RULES['account_size']:,.0f} · Max risk: {RULES['max_risk_pct']}% per trade")
    print("="*55)

    if args.report:
        generate_report()
        return

    if args.csv:
        check_csv(args.csv)
        return

    while True:
        trade  = collect_trade_input()
        result = run_all_checks(trade)
        display_result(result, trade)

        if not result["overall"]:
            send_blocked_alert(result, trade)

        again = input("\n  Check another trade? (y/n): ").strip().lower()
        if again != "y":
            break


if __name__ == "__main__":
    main()

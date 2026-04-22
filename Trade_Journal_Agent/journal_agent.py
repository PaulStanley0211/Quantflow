import anthropic
import csv
import json
import os
import re
from datetime import datetime

from config import ANTHROPIC_API_KEY, CSV_FILE

CSV_HEADERS = [
    "date", "ticker", "direction", "entry_price", "stop_loss", "exit_price",
    "quantity", "pnl_eur", "r_multiple", "setup_type",
    "ai_tag", "ai_lesson", "ai_quality", "notes"
]


# ─────────────────────────────────────────────
# 1. COLLECT TRADE INPUT FROM USER
# ─────────────────────────────────────────────

def collect_trade_input() -> dict:
    """Prompt the user for trade details and compute P&L."""
    print("\n" + "=" * 50)
    print("  New Trade Entry")
    print("=" * 50)

    date = input("Date (YYYY-MM-DD) [today]: ").strip()
    if not date:
        date = datetime.now().strftime("%Y-%m-%d")

    ticker = input("Ticker (e.g. SAP.DE): ").strip().upper()

    direction = ""
    while direction not in ["BUY", "SELL", "SHORT", "COVER"]:
        direction = input("Direction (BUY / SELL / SHORT / COVER): ").strip().upper()

    entry_price = float(input("Entry price (EUR): ").strip())
    stop_loss_input = input("Stop loss price (EUR) [leave blank to skip]: ").strip()
    stop_loss   = float(stop_loss_input) if stop_loss_input else 0.0
    exit_price  = float(input("Exit price (EUR): ").strip())
    quantity    = float(input("Quantity (shares): ").strip())
    notes       = input("Your notes / reason for trade: ").strip()

    if direction in ["BUY", "COVER"]:
        pnl = (exit_price - entry_price) * quantity
    else:
        pnl = (entry_price - exit_price) * quantity

    print(f"\n  P&L: EUR {pnl:.2f}")

    return {
        "date":        date,
        "ticker":      ticker,
        "direction":   direction,
        "entry_price": entry_price,
        "stop_loss":   stop_loss,
        "exit_price":  exit_price,
        "quantity":    quantity,
        "pnl_eur":     round(pnl, 2),
        "notes":       notes,
    }


# ─────────────────────────────────────────────
# 2. AI ANALYSIS WITH CLAUDE
# ─────────────────────────────────────────────

def _strip_markdown_fences(text: str) -> str:
    """Remove optional ```json ... ``` wrapping that the model may add."""
    text = text.strip()
    match = re.match(r"^```(?:json)?\s*([\s\S]*?)\s*```$", text)
    if match:
        return match.group(1)
    return text


def analyse_trade_with_ai(trade: dict) -> dict:
    """Send trade to Claude and return setup tag, lesson, and quality score."""
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    direction_label = "long" if trade["direction"] in ["BUY", "COVER"] else "short"
    result = "WIN" if trade["pnl_eur"] > 0 else "LOSS" if trade["pnl_eur"] < 0 else "BREAK EVEN"

    prompt = f"""You are a professional trading coach analysing a trade journal entry.

Trade details:
- Ticker: {trade['ticker']}
- Direction: {direction_label}
- Entry: EUR {trade['entry_price']} | Exit: EUR {trade['exit_price']}
- Quantity: {trade['quantity']} shares
- P&L: EUR {trade['pnl_eur']} ({result})
- Trader notes: "{trade['notes']}"

Respond ONLY with a JSON object, no extra text, no markdown:
{{
  "setup_type": "one of: Breakout, Pullback, Reversal, Momentum, Mean-Reversion, News-Play, Earnings, Trend-Follow, Unknown",
  "r_multiple": <float: how many R this trade made or lost. Estimate from entry/exit if stop not given. Positive for wins, negative for losses>,
  "ai_tag": "2-4 word sharp label for this trade e.g. 'Clean breakout entry' or 'Revenge trade - avoid'",
  "ai_quality": "one of: A, B, C, D — A=excellent execution, D=poor decision",
  "ai_lesson": "one sentence max — the single most important lesson from this trade"
}}"""

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=400,
        messages=[{"role": "user", "content": prompt}]
    )

    raw = _strip_markdown_fences(message.content[0].text)
    return json.loads(raw)


# ─────────────────────────────────────────────
# 3. SAVE TO CSV
# ─────────────────────────────────────────────

def save_to_csv(trade: dict, analysis: dict):
    """Append trade and AI analysis as one row in the CSV file."""
    file_exists = os.path.exists(CSV_FILE)

    row = {
        "date":        trade["date"],
        "ticker":      trade["ticker"],
        "direction":   trade["direction"],
        "entry_price": trade["entry_price"],
        "stop_loss":   trade["stop_loss"],
        "exit_price":  trade["exit_price"],
        "quantity":    trade["quantity"],
        "pnl_eur":     trade["pnl_eur"],
        "r_multiple":  analysis.get("r_multiple", ""),
        "setup_type":  analysis.get("setup_type", ""),
        "ai_tag":      analysis.get("ai_tag", ""),
        "ai_lesson":   analysis.get("ai_lesson", ""),
        "ai_quality":  analysis.get("ai_quality", ""),
        "notes":       trade["notes"],
    }

    with open(CSV_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)

    print(f"\n  Trade saved to {CSV_FILE}")


# ─────────────────────────────────────────────
# 4. DISPLAY AI RESULT
# ─────────────────────────────────────────────

QUALITY_LABEL = {"A": "[A] Excellent", "B": "[B] Good", "C": "[C] Fair", "D": "[D] Poor"}


def display_analysis(analysis: dict):
    """Print the AI analysis in a clean format."""
    grade = analysis.get("ai_quality", "?")
    label = QUALITY_LABEL.get(grade, f"[{grade}]")

    print("\n" + "-" * 50)
    print("  AI Analysis")
    print("-" * 50)
    print(f"  Setup type : {analysis.get('setup_type', 'Unknown')}")
    print(f"  Tag        : {analysis.get('ai_tag', '')}")
    print(f"  R-Multiple : {analysis.get('r_multiple', '?')}R")
    print(f"  Quality    : {label}")
    print(f"  Lesson     : {analysis.get('ai_lesson', '')}")
    print("-" * 50)


# ─────────────────────────────────────────────
# 5. MAIN FLOW
# ─────────────────────────────────────────────

def run():
    print("\n  Trade Journal Agent — German Market Edition")
    print(f"  Trades are saved to {CSV_FILE}")
    print("  Run stats.py anytime to see your performance\n")

    while True:
        trade = collect_trade_input()

        print("\n  Analysing trade with AI...")
        try:
            analysis = analyse_trade_with_ai(trade)
            display_analysis(analysis)
            save_to_csv(trade, analysis)
        except Exception as e:
            print(f"\n  AI analysis failed ({e}) — saving trade without AI tags")
            save_to_csv(trade, {})

        again = input("\n  Log another trade? (y/n): ").strip().lower()
        if again != "y":
            print("\n  Journal closed. Run stats.py to review your performance.\n")
            break


if __name__ == "__main__":
    run()

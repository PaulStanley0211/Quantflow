import csv
import os
from collections import defaultdict

from config import CSV_FILE


def load_trades() -> list:
    if not os.path.exists(CSV_FILE):
        print("\n  No trades found. Log some trades first with journal_agent.py\n")
        return []
    with open(CSV_FILE, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def print_stats(trades: list):
    if not trades:
        return

    total     = len(trades)
    wins      = [t for t in trades if float(t["pnl_eur"]) > 0]
    losses    = [t for t in trades if float(t["pnl_eur"]) < 0]
    total_pnl = sum(float(t["pnl_eur"]) for t in trades)
    win_rate  = (len(wins) / total * 100) if total else 0
    avg_win   = sum(float(t["pnl_eur"]) for t in wins) / len(wins) if wins else 0
    avg_loss  = sum(float(t["pnl_eur"]) for t in losses) / len(losses) if losses else 0
    best      = max(trades, key=lambda t: float(t["pnl_eur"]))
    worst     = min(trades, key=lambda t: float(t["pnl_eur"]))

    by_setup = defaultdict(list)
    for t in trades:
        by_setup[t["setup_type"] or "Unknown"].append(float(t["pnl_eur"]))

    by_quality = defaultdict(int)
    for t in trades:
        by_quality[t.get("ai_quality") or "?"] += 1

    print("\n" + "=" * 50)
    print("  Trading Performance Summary")
    print("=" * 50)
    print(f"  Total trades  : {total}")
    print(f"  Win rate      : {win_rate:.1f}%  ({len(wins)}W / {len(losses)}L)")
    print(f"  Total P&L     : EUR {total_pnl:.2f}")
    print(f"  Avg win       : EUR {avg_win:.2f}")
    print(f"  Avg loss      : EUR {avg_loss:.2f}")
    print(f"  Best trade    : EUR {float(best['pnl_eur']):.2f} ({best['ticker']})")
    print(f"  Worst trade   : EUR {float(worst['pnl_eur']):.2f} ({worst['ticker']})")

    print("\n  P&L by Setup Type")
    print("  " + "-" * 36)
    for setup, pnls in sorted(by_setup.items(), key=lambda x: sum(x[1]), reverse=True):
        total_setup = sum(pnls)
        count       = len(pnls)
        bar         = "#" * min(int(abs(total_setup) / 10), 20)
        sign        = "+" if total_setup >= 0 else "-"
        print(f"  {setup:<20} {sign}EUR {abs(total_setup):.0f}  ({count} trades)  {bar}")

    print("\n  Trade Quality Breakdown")
    print("  " + "-" * 36)
    for grade in ["A", "B", "C", "D"]:
        count = by_quality.get(grade, 0)
        bar   = "#" * count
        print(f"  Grade {grade}  {count:>3} trades  {bar}")

    print("\n  Recent AI Lessons")
    print("  " + "-" * 36)
    recent = [t for t in trades[-5:] if t.get("ai_lesson")]
    for t in recent:
        print(f"  [{t.get('entry_date', '')}] {t['ticker']}: {t['ai_lesson']}")

    print("=" * 50 + "\n")


if __name__ == "__main__":
    trades = load_trades()
    print_stats(trades)

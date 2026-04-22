# ─────────────────────────────────────────────
# config.py — Settings & watchlist
# Secrets are loaded from .env (never hardcoded here)
# ─────────────────────────────────────────────

import os
from dotenv import load_dotenv

# Load secrets from .env file
load_dotenv()

# ── Secrets (loaded from .env) ───────────────
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
EMAIL_SENDER      = os.getenv("EMAIL_SENDER")
EMAIL_PASSWORD    = os.getenv("EMAIL_PASSWORD")
EMAIL_RECEIVER    = os.getenv("EMAIL_RECEIVER")

# ── Validation — fail early if anything is missing ──
missing = [k for k, v in {
    "ANTHROPIC_API_KEY": ANTHROPIC_API_KEY,
    "EMAIL_SENDER":      EMAIL_SENDER,
    "EMAIL_PASSWORD":    EMAIL_PASSWORD,
    "EMAIL_RECEIVER":    EMAIL_RECEIVER,
}.items() if not v]

if missing:
    raise ValueError(f"Missing required .env variables: {', '.join(missing)}")

# ── Watchlist — German stocks (XETRA via Yahoo Finance) ──
# Add or remove tickers freely — .DE suffix = XETRA exchange
WATCHLIST = [
    "SAP.DE",      # SAP — largest German tech company
    "SIE.DE",      # Siemens
    "BMW.DE",      # BMW
    "VOW3.DE",     # Volkswagen
    "ALV.DE",      # Allianz
    "MBG.DE",      # Mercedes-Benz
    "BAS.DE",      # BASF
    "DBK.DE",      # Deutsche Bank
    "ADS.DE",      # Adidas
    "DTE.DE",      # Deutsche Telekom
    "^GDAXI",      # DAX 40 Index (benchmark)
]
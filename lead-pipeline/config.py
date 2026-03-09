"""
CONFIG — All your settings in one place.

HOW TO USE:
  Fill in the values below. The rest of the code reads from here.
  Never share this file publicly (it contains your passwords/keys).
"""

# ──────────────────────────────────────────────
# SCRAPER SETTINGS (Step 1)
# ──────────────────────────────────────────────

# What type of business to search for
# TIP: Service businesses (plombier, electricien, serrurier, avocat, comptable)
#      are more likely to have email addresses listed than food businesses.
SEARCH_CATEGORY = "plombier"

# Where to search (city or department)
SEARCH_LOCATION = "Toulouse"

# How many pages of results to scrape (each page ~ 20 businesses)
MAX_PAGES = 10

# ──────────────────────────────────────────────
# DEEPSEEK AI SETTINGS (Step 2 — not used yet)
# ──────────────────────────────────────────────

DEEPSEEK_API_KEY = ""  # Get from: platform.deepseek.com

# ──────────────────────────────────────────────
# NETLIFY SETTINGS (Step 3 — not used yet)
# ──────────────────────────────────────────────

NETLIFY_API_TOKEN = ""  # Get from: app.netlify.com/user/applications

# ──────────────────────────────────────────────
# EMAIL SETTINGS (Step 4 — not used yet)
# ──────────────────────────────────────────────

GMAIL_ADDRESS = ""      # Your Gmail address
GMAIL_APP_PASSWORD = ""  # NOT your Gmail password! See README for how to get this.

# ──────────────────────────────────────────────
# FILE PATHS (don't change unless you know why)
# ──────────────────────────────────────────────

import os

# This gets the folder where config.py lives
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# All data files go here
DATA_DIR = os.path.join(BASE_DIR, "data")
LEADS_CSV = os.path.join(DATA_DIR, "leads.csv")
SITES_DIR = os.path.join(DATA_DIR, "sites")
RESULTS_CSV = os.path.join(DATA_DIR, "results.csv")

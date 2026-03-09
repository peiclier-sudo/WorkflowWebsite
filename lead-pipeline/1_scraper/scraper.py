"""
SCRAPER — Finds businesses on PagesJaunes that have NO website.

HOW IT WORKS:
  1. Builds a search URL for pagesjaunes.fr (like typing in their search bar)
  2. Downloads each results page
  3. For each business on the page, extracts: name, phone, email, address
  4. Keeps ONLY businesses that have an email but NO website
  5. Saves everything to data/leads.csv
"""

import csv
import os
import time

import httpx
from bs4 import BeautifulSoup

# Go up one folder to find config.py
# "sys.path" tells Python where to look for files to import
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config


def build_url(category, location, page=1):
    """
    Builds the PagesJaunes search URL.

    Example result:
      https://www.pagesjaunes.fr/annuaire/chercherlespros?quoiqui=boulangerie&ou=Paris&page=1
    """
    base = "https://www.pagesjaunes.fr/annuaire/chercherlespros"
    return f"{base}?quoiqui={category}&ou={location}&page={page}"


def fetch_page(url):
    """
    Downloads a web page and returns the HTML text.

    KEY CONCEPT — HTTP Headers:
      Websites can block "robots" (scripts). By sending a "User-Agent" header,
      we tell the site "I'm a normal browser", not "I'm a Python script".
      This is standard practice for scraping.
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "fr-FR,fr;q=0.9",
    }

    try:
        response = httpx.get(url, headers=headers, follow_redirects=True, timeout=30)
    except httpx.HTTPError as e:
        print(f"  ⚠ Network error: {e}")
        print("    Make sure you have internet access and try again.")
        return None

    # "status_code 200" = success, anything else = problem
    if response.status_code != 200:
        print(f"  ⚠ Page returned status {response.status_code}, skipping.")
        return None

    return response.text


def parse_listing(card):
    """
    Extracts business info from ONE result card on the page.

    KEY CONCEPT — CSS Selectors:
      HTML is structured like a tree. Each business is inside a <div> with
      a specific class name. We use "select" to find elements by their
      class name, like searching a filing cabinet by label.

    Returns a dict like:
      {"name": "Boulangerie Dupont", "phone": "01 23 45 67 89", ...}
    or None if the business has a website (we don't want those).
    """
    info = {
        "name": "",
        "phone": "",
        "email": "",
        "address": "",
        "city": config.SEARCH_LOCATION,
        "category": config.SEARCH_CATEGORY,
        "has_website": False,
    }

    # --- Extract business name ---
    name_tag = card.select_one(".bi-denomination")
    if name_tag:
        info["name"] = name_tag.get_text(strip=True)

    # --- Extract phone number ---
    phone_tag = card.select_one(".bi-phone .coord-value")
    if not phone_tag:
        phone_tag = card.select_one("[data-phone]")
    if phone_tag:
        info["phone"] = phone_tag.get_text(strip=True)

    # --- Extract address ---
    address_tag = card.select_one(".bi-address")
    if address_tag:
        info["address"] = address_tag.get_text(" ", strip=True)

    # --- Check for website (we want businesses WITHOUT one) ---
    website_link = card.select_one("a.bi-website") or card.select_one(".pj-link--website")
    if website_link:
        info["has_website"] = True

    # --- Extract email ---
    email_tag = card.select_one("a[href^='mailto:']")
    if email_tag:
        href = email_tag.get("href", "")
        info["email"] = href.replace("mailto:", "").strip()

    return info


def scrape_page(url):
    """
    Scrapes ONE page of PagesJaunes results.
    Returns a list of business dicts.
    """
    html = fetch_page(url)
    if not html:
        return []

    # KEY CONCEPT — BeautifulSoup:
    # Turns raw HTML text into a searchable tree structure.
    # "html.parser" is the built-in Python parser (no extra install needed).
    soup = BeautifulSoup(html, "html.parser")

    # Each business result is inside a <li> with class "bi-item"
    # (this may change if PagesJaunes updates their site)
    cards = soup.select("li.bi-item")
    if not cards:
        # Fallback: try alternative selectors
        cards = soup.select(".bi")

    results = []
    for card in cards:
        info = parse_listing(card)
        if info and info["name"]:
            results.append(info)

    return results


def save_leads(leads, filepath):
    """
    Saves the leads list to a CSV file.

    KEY CONCEPT — CSV:
      CSV = "Comma-Separated Values". It's the simplest spreadsheet format.
      You can open it in Excel, Google Sheets, or any text editor.
      Each line is one business. Columns are separated by commas.
    """
    os.makedirs(os.path.dirname(filepath), exist_ok=True)

    fieldnames = ["name", "phone", "email", "address", "city", "category"]

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()  # Writes the column names as first line
        for lead in leads:
            # Only write the fields we care about (skip has_website)
            row = {k: lead[k] for k in fieldnames}
            writer.writerow(row)

    print(f"\n✅ Saved {len(leads)} leads to {filepath}")


def run():
    """
    Main function — runs the full scraping process.

    This is what gets called when you run the scraper.
    """
    print("=" * 50)
    print(f"🔍 Searching PagesJaunes for: {config.SEARCH_CATEGORY}")
    print(f"📍 Location: {config.SEARCH_LOCATION}")
    print(f"📄 Pages to scrape: {config.MAX_PAGES}")
    print("=" * 50)

    all_leads = []

    for page_num in range(1, config.MAX_PAGES + 1):
        url = build_url(config.SEARCH_CATEGORY, config.SEARCH_LOCATION, page_num)
        print(f"\n📄 Scraping page {page_num}/{config.MAX_PAGES}...")
        print(f"   URL: {url}")

        page_results = scrape_page(url)
        print(f"   Found {len(page_results)} businesses on this page")

        # Filter: keep only businesses WITH email and WITHOUT website
        qualified = []
        for biz in page_results:
            if biz["email"] and not biz["has_website"]:
                qualified.append(biz)

        print(f"   ✅ {len(qualified)} qualified (has email, no website)")
        all_leads.extend(qualified)

        # Be polite: wait between requests so we don't overload the site
        if page_num < config.MAX_PAGES:
            print("   ⏳ Waiting 2 seconds before next page...")
            time.sleep(2)

    print(f"\n{'=' * 50}")
    print(f"📊 Total qualified leads: {len(all_leads)}")

    if all_leads:
        save_leads(all_leads, config.LEADS_CSV)
    else:
        print("⚠ No qualified leads found. Try a different category or location.")

    return all_leads


# This runs the scraper when you execute this file directly:
#   python 1_scraper/scraper.py
if __name__ == "__main__":
    run()

"""
SCRAPER — Finds businesses on PagesJaunes that have NO website.

HOW IT WORKS:
  1. Opens a real Chrome browser (invisible, in the background)
  2. Navigates to pagesjaunes.fr and searches for businesses
  3. For each business on the page, extracts: name, phone, email, address
  4. Keeps ONLY businesses that have an email but NO website
  5. Saves everything to data/leads.csv

WHY SELENIUM (not simple HTTP requests)?
  PagesJaunes blocks simple HTTP requests (returns 403 Forbidden).
  Selenium launches a REAL browser, so the website thinks a human is browsing.
"""

import csv
import os
import time

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Go up one folder to find config.py
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


def create_browser():
    """
    Creates an invisible Chrome browser.

    KEY CONCEPT — Headless Browser:
      "Headless" means the browser window is invisible. Chrome loads the page
      exactly like normal, but without showing anything on screen.
      The website sees a real browser visit, not a script.

    KEY CONCEPT — Selenium + ChromeDriver:
      Selenium is the "remote control". ChromeDriver is the "translator"
      between Selenium and Chrome. Selenium tells ChromeDriver what to do,
      ChromeDriver tells Chrome to do it.
    """
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")  # Invisible mode
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--lang=fr-FR")
    chrome_options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )

    try:
        driver = webdriver.Chrome(options=chrome_options)
        return driver
    except Exception as e:
        print(f"\n❌ Could not start Chrome browser: {e}")
        print("\nTo fix this, make sure Google Chrome is installed on your PC.")
        print("Selenium will automatically download ChromeDriver for you.")
        return None


def fetch_page(url, driver):
    """
    Opens a URL in the browser and returns the page HTML.
    """
    try:
        driver.get(url)

        # Wait for the page to load (wait until result cards appear or 10s timeout)
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".bi-item, .bi"))
            )
        except Exception:
            pass  # Timeout — page may have no results

        # Handle cookie consent popup
        try:
            cookie_btn = driver.find_element(By.ID, "didomi-notice-agree-button")
            cookie_btn.click()
            time.sleep(1)
        except Exception:
            pass  # No cookie popup

        return driver.page_source

    except Exception as e:
        print(f"  ⚠ Browser error: {e}")
        return None


def parse_listing(card):
    """
    Extracts business info from ONE result card on the page.

    KEY CONCEPT — CSS Selectors:
      HTML is structured like a tree. Each business is inside a <div> with
      a specific class name. We use "select" to find elements by their
      class name, like searching a filing cabinet by label.

    Returns a dict like:
      {"name": "Boulangerie Dupont", "phone": "01 23 45 67 89", ...}
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


def scrape_page(url, driver):
    """
    Scrapes ONE page of PagesJaunes results.
    Returns a list of business dicts.
    """
    html = fetch_page(url, driver)
    if not html:
        return []

    # KEY CONCEPT — BeautifulSoup:
    # Turns raw HTML text into a searchable tree structure.
    soup = BeautifulSoup(html, "html.parser")

    # Each business result is inside a <li> with class "bi-item"
    cards = soup.select("li.bi-item")
    if not cards:
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
    """
    os.makedirs(os.path.dirname(filepath), exist_ok=True)

    fieldnames = ["name", "phone", "email", "address", "city", "category"]

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for lead in leads:
            row = {k: lead[k] for k in fieldnames}
            writer.writerow(row)

    print(f"\n✅ Saved {len(leads)} leads to {filepath}")


def run():
    """
    Main function — runs the full scraping process.
    """
    print("=" * 50)
    print(f"🔍 Searching PagesJaunes for: {config.SEARCH_CATEGORY}")
    print(f"📍 Location: {config.SEARCH_LOCATION}")
    print(f"📄 Pages to scrape: {config.MAX_PAGES}")
    print("=" * 50)

    print("\n🌐 Launching Chrome browser...")
    driver = create_browser()
    if not driver:
        return []

    all_leads = []

    try:
        for page_num in range(1, config.MAX_PAGES + 1):
            url = build_url(config.SEARCH_CATEGORY, config.SEARCH_LOCATION, page_num)
            print(f"\n📄 Scraping page {page_num}/{config.MAX_PAGES}...")
            print(f"   URL: {url}")

            page_results = scrape_page(url, driver)
            print(f"   Found {len(page_results)} businesses on this page")

            # Filter: keep only businesses WITH email and WITHOUT website
            qualified = []
            for biz in page_results:
                if biz["email"] and not biz["has_website"]:
                    qualified.append(biz)

            print(f"   ✅ {len(qualified)} qualified (has email, no website)")
            all_leads.extend(qualified)

            # Be polite: wait between requests
            if page_num < config.MAX_PAGES:
                print("   ⏳ Waiting 2 seconds before next page...")
                time.sleep(2)
    finally:
        # Always close the browser, even if an error occurs
        driver.quit()
        print("\n🌐 Browser closed.")

    print(f"\n{'=' * 50}")
    print(f"📊 Total qualified leads: {len(all_leads)}")

    if all_leads:
        save_leads(all_leads, config.LEADS_CSV)
    else:
        print("⚠ No qualified leads found. Try a different category or location.")

    return all_leads


if __name__ == "__main__":
    run()

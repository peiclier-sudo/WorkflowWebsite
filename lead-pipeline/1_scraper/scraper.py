"""
SCRAPER — Finds businesses on PagesJaunes that have NO website.

HOW IT WORKS:
  1. Opens a real Chrome browser (invisible, in the background)
  2. Navigates to pagesjaunes.fr and searches for businesses
  3. Clicks "Afficher le N°" buttons to reveal hidden phone numbers
  4. Extracts: name, phone, address for each business
  5. Keeps ONLY businesses that have NO website
  6. Saves everything to data/leads.csv

WHY SELENIUM (not simple HTTP requests)?
  PagesJaunes blocks simple HTTP requests (returns 403 Forbidden).
  Selenium launches a REAL browser, so the website thinks a human is browsing.

WHY CLICK PHONE BUTTONS?
  PagesJaunes hides phone numbers behind "Afficher le N°" buttons.
  The number only appears in the HTML after clicking. Same concept as
  a "Show phone number" button on any website.
"""

import csv
import os
import re
import time

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
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
      https://www.pagesjaunes.fr/annuaire/chercherlespros?quoiqui=plombier&ou=Paris&page=1
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


def dismiss_cookie_popup(driver):
    """Clicks the cookie consent button if it appears."""
    try:
        cookie_btn = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.ID, "didomi-notice-agree-button"))
        )
        cookie_btn.click()
        time.sleep(0.5)
    except Exception:
        pass  # No cookie popup


def scrape_page(url, driver, page_num):
    """
    Scrapes ONE page of PagesJaunes results using Selenium.

    KEY CONCEPT — Dynamic Content:
      PagesJaunes hides phone numbers behind "Afficher le N°" buttons.
      We must click each button, then read the revealed number from
      a hidden <div> that becomes visible.

    Returns a list of business dicts.
    """
    try:
        driver.get(url)
    except Exception as e:
        print(f"  ⚠ Browser error loading page: {e}")
        return []

    # Handle cookie popup FIRST (it can block the page content)
    dismiss_cookie_popup(driver)

    # Wait for business cards to appear
    card_selector = "li.bi"
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, card_selector))
        )
    except Exception:
        print("  ⚠ No results found on this page (timeout)")
        debug_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
        os.makedirs(debug_dir, exist_ok=True)
        driver.save_screenshot(os.path.join(debug_dir, f"debug_page{page_num}.png"))
        with open(os.path.join(debug_dir, f"debug_page{page_num}.html"), "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        print(f"  📸 Debug files saved to data/")
        return []

    # Find all business cards
    cards = driver.find_elements(By.CSS_SELECTOR, card_selector)
    print(f"   Found {len(cards)} business cards")

    # --- Step 1: Click ALL "Afficher le N°" buttons to reveal phone numbers ---
    # KEY CONCEPT: PagesJaunes hides phone numbers. Each card has a button
    # with class "btn_tel". Clicking it reveals a hidden div (class "bi-fantomas")
    # containing the actual phone number inside ".number-contact".
    phone_buttons = driver.find_elements(By.CSS_SELECTOR, "button.btn_tel")
    if phone_buttons:
        print(f"   📞 Clicking {len(phone_buttons)} phone buttons...")
        for btn in phone_buttons:
            try:
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
                time.sleep(0.1)
                driver.execute_script("arguments[0].click();", btn)
                time.sleep(0.2)
            except Exception:
                pass
        time.sleep(0.5)

    # --- Step 2: Extract data from each card ---
    results = []
    for card in cards:
        info = extract_card_data(card)
        if info and info["name"]:
            results.append(info)

    return results


def extract_card_data(card):
    """
    Extracts business info from ONE card element using Selenium.

    The actual PagesJaunes HTML structure (as of 2025):
      - Name:    <h3> inside <a class="bi-denomination">
      - Address: <div class="bi-address"> containing an <a> with the text
      - Phone:   <div class="bi-fantomas"> > <div class="number-contact">
                 (only visible after clicking "Afficher le N°")
      - Website: <a> with "site internet" or "website" in the link
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

    # --- Business name (inside h3 within .bi-denomination link) ---
    try:
        name_el = card.find_element(By.CSS_SELECTOR, "h3")
        info["name"] = name_el.text.strip()
    except Exception:
        pass

    # --- Phone number (revealed after clicking "Afficher le N°") ---
    # The phone appears in: <div class="bi-fantomas"><div class="number-contact">
    # Text looks like: "Tél : 01 84 83 14 68"
    try:
        phone_el = card.find_element(By.CSS_SELECTOR, ".number-contact")
        phone_text = phone_el.text.strip()
        # Extract just the number: remove "Tél :" prefix
        phone_clean = re.sub(r'^.*?:\s*', '', phone_text).strip()
        if phone_clean:
            info["phone"] = phone_clean
    except Exception:
        pass

    # --- Address (inside .bi-address) ---
    # Text looks like: "3 rue Janssen 75019 Paris\nVoir le plan"
    try:
        addr_el = card.find_element(By.CSS_SELECTOR, ".bi-address")
        addr_text = addr_el.text.strip()
        # Remove "Voir le plan" suffix
        addr_text = addr_text.replace("Voir le plan", "").strip()
        info["address"] = addr_text
    except Exception:
        pass

    # --- Website detection ---
    # Paid listings have website links. We look for any link containing
    # "site internet" or website-related attributes.
    try:
        # Check for site internet link in the card's actions
        card_html = card.get_attribute("innerHTML").lower()
        if "site internet" in card_html or "bi-website" in card_html or "visiter le site" in card_html:
            info["has_website"] = True
    except Exception:
        pass

    # --- Email (rare on search results, but check anyway) ---
    try:
        email_el = card.find_element(By.CSS_SELECTOR, "a[href^='mailto:']")
        href = email_el.get_attribute("href") or ""
        info["email"] = href.replace("mailto:", "").strip()
    except Exception:
        pass

    # Regex fallback for email
    if not info["email"]:
        try:
            card_html = card.get_attribute("innerHTML")
            email_match = re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', card_html)
            if email_match:
                info["email"] = email_match.group(0)
        except Exception:
            pass

    return info


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

            page_results = scrape_page(url, driver, page_num)

            # Keep ALL businesses without a website (even if no email)
            # These are our potential clients — they need a website!
            qualified = [biz for biz in page_results if not biz["has_website"]]
            with_email = [biz for biz in qualified if biz["email"]]
            with_phone = [biz for biz in qualified if biz["phone"]]

            print(f"   📊 {len(qualified)} without website, {len(with_phone)} with phone, {len(with_email)} with email")
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
    print(f"📊 Total leads (no website): {len(all_leads)}")
    with_email_total = sum(1 for l in all_leads if l["email"])
    with_phone_total = sum(1 for l in all_leads if l["phone"])
    print(f"   📞 With phone: {with_phone_total}")
    print(f"   📧 With email: {with_email_total}")

    if all_leads:
        save_leads(all_leads, config.LEADS_CSV)
    else:
        print("\n⚠ No leads found.")
        print("   Check the debug screenshots in data/ folder to see what the page looks like.")

    return all_leads


if __name__ == "__main__":
    run()

"""
SCRAPER — Finds businesses on PagesJaunes that have NO website.

HOW IT WORKS:
  1. Opens a real Chrome browser (invisible, in the background)
  2. Navigates to pagesjaunes.fr and searches for businesses
  3. For each business card, clicks "Email" button to reveal hidden email
  4. Keeps ONLY businesses that have an email but NO website
  5. Saves everything to data/leads.csv

WHY SELENIUM (not simple HTTP requests)?
  PagesJaunes blocks simple HTTP requests (returns 403 Forbidden).
  Selenium launches a REAL browser, so the website thinks a human is browsing.

WHY CLICK EMAIL BUTTONS?
  PagesJaunes hides emails behind a button click. The email is NOT in the
  initial HTML — it's loaded dynamically when you click "E-mail".
  We must use Selenium to click each button and wait for the email to appear.
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
    Scrapes ONE page of PagesJaunes results using Selenium directly.

    KEY CONCEPT — Dynamic Content:
      PagesJaunes loads emails only when you click the "E-mail" button.
      So we can't just read the HTML — we must interact with the page
      like a real user would: click buttons, wait for content to appear.

    Returns a list of business dicts.
    """
    try:
        driver.get(url)
    except Exception as e:
        print(f"  ⚠ Browser error loading page: {e}")
        return []

    # Wait for business cards to appear
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".bi-liste li.bi"))
        )
    except Exception:
        print("  ⚠ No results found on this page (timeout waiting for cards)")
        # Save a debug screenshot
        debug_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", f"debug_page{page_num}.png")
        os.makedirs(os.path.dirname(debug_path), exist_ok=True)
        driver.save_screenshot(debug_path)
        print(f"  📸 Debug screenshot saved to {debug_path}")
        return []

    # Handle cookie popup (only needed on first page)
    dismiss_cookie_popup(driver)

    # Find all business cards
    cards = driver.find_elements(By.CSS_SELECTOR, ".bi-liste li.bi")
    if not cards:
        cards = driver.find_elements(By.CSS_SELECTOR, "li.bi-item")

    print(f"   Found {len(cards)} business cards")

    # --- Step 1: Click ALL "E-mail" buttons to reveal hidden emails ---
    # KEY CONCEPT: PagesJaunes hides emails. Each card has an "E-mail" button.
    # When clicked, it loads the actual email address via JavaScript.
    # We click all buttons first, then extract data after.

    email_buttons = driver.find_elements(By.CSS_SELECTOR, "a[title*='E-mail'], a[title*='email'], a.pj-link--email")
    if email_buttons:
        print(f"   📧 Found {len(email_buttons)} email buttons — clicking them...")
        for btn in email_buttons:
            try:
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
                time.sleep(0.2)
                driver.execute_script("arguments[0].click();", btn)
                time.sleep(0.3)
            except Exception:
                pass
        # Wait a moment for all emails to load
        time.sleep(1)
    else:
        print("   📧 No email buttons found on this page")

    # --- Step 2: Now extract data from each card ---
    results = []
    for card in cards:
        info = extract_card_data(card)
        if info and info["name"]:
            results.append(info)

    return results


def extract_card_data(card):
    """
    Extracts business info from ONE card element using Selenium.

    This runs AFTER we've clicked all email buttons, so any revealed
    emails should now be visible in the DOM.
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

    # --- Business name ---
    try:
        name_el = card.find_element(By.CSS_SELECTOR, ".bi-denomination, .denomination-links, h2, h3")
        info["name"] = name_el.text.strip()
    except Exception:
        pass

    # --- Phone number ---
    try:
        phone_el = card.find_element(By.CSS_SELECTOR, ".bi-phone .coord-value, [class*='phone'] .coord-value, .tel-value")
        info["phone"] = phone_el.text.strip()
    except Exception:
        # Try data attribute
        try:
            phone_el = card.find_element(By.CSS_SELECTOR, "[data-phone]")
            info["phone"] = phone_el.get_attribute("data-phone") or phone_el.text.strip()
        except Exception:
            pass

    # --- Address ---
    try:
        addr_el = card.find_element(By.CSS_SELECTOR, ".bi-address, .address-container")
        info["address"] = addr_el.text.strip()
    except Exception:
        pass

    # --- Website (we want businesses WITHOUT one) ---
    try:
        card.find_element(By.CSS_SELECTOR, "a.bi-website, a[class*='website'], .pj-link--website")
        info["has_website"] = True
    except Exception:
        pass  # No website link found — good!

    # --- Email (should be visible now after clicking the button) ---
    # Look for mailto: links that appeared after clicking
    try:
        email_el = card.find_element(By.CSS_SELECTOR, "a[href^='mailto:']")
        href = email_el.get_attribute("href") or ""
        info["email"] = href.replace("mailto:", "").strip()
    except Exception:
        pass

    # Also check the card's inner HTML for email patterns (backup method)
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

            # Filter: keep only businesses WITH email and WITHOUT website
            qualified = []
            no_website_count = 0
            for biz in page_results:
                if not biz["has_website"]:
                    no_website_count += 1
                if biz["email"] and not biz["has_website"]:
                    qualified.append(biz)

            print(f"   📊 {no_website_count} without website, {len(qualified)} also have email")
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
        print("\n⚠ No qualified leads found.")
        print("   This can happen if PagesJaunes changed their HTML structure.")
        print("   Check the debug screenshots in data/ folder to see what the page looks like.")
        print("   Try: python main.py scrape  (to re-run)")

    return all_leads


if __name__ == "__main__":
    run()

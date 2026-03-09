"""
SCRAPER — Finds businesses on PagesJaunes that have NO website.

HOW IT WORKS:
  1. Opens a real Chrome browser (invisible, in the background)
  2. Searches pagesjaunes.fr for businesses in your category/location
  3. Clicks "Afficher le N°" buttons to reveal hidden phone numbers
  4. Filters out businesses that already have a website
  5. For each remaining business, visits their DETAIL PAGE to find email
  6. Saves results to data/leads.csv

WHY TWO STEPS (search page → detail page)?
  PagesJaunes shows limited info on search results. Emails are only
  visible on individual business detail pages, not on the search list.

WHY SELENIUM (not simple HTTP requests)?
  PagesJaunes blocks simple HTTP requests (returns 403 Forbidden).
  Selenium launches a REAL browser, so the website thinks a human is browsing.
"""

import csv
import os
import re
import time
import base64

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
    """Builds the PagesJaunes search URL."""
    base = "https://www.pagesjaunes.fr/annuaire/chercherlespros"
    return f"{base}?quoiqui={category}&ou={location}&page={page}"


def create_browser():
    """Creates an invisible Chrome browser."""
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
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
        pass


def scrape_search_page(url, driver, page_num):
    """
    Scrapes ONE page of PagesJaunes search results.

    For each business card, extracts:
      - name, phone, address, detail_url, has_website

    Phone numbers are hidden behind "Afficher le N°" buttons, so we
    click them all first, then extract the revealed numbers.

    Returns a list of business dicts.
    """
    try:
        driver.get(url)
    except Exception as e:
        print(f"  ⚠ Browser error loading page: {e}")
        return []

    dismiss_cookie_popup(driver)

    # Wait for business cards
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "li.bi"))
        )
    except Exception:
        print("  ⚠ No results found on this page (timeout)")
        return []

    cards = driver.find_elements(By.CSS_SELECTOR, "li.bi")
    print(f"   Found {len(cards)} business cards")

    # Click ALL "Afficher le N°" buttons to reveal phone numbers
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

    # Extract data from each card
    results = []
    for card in cards:
        info = extract_card_data(card)
        if info and info["name"]:
            results.append(info)

    return results


def extract_card_data(card):
    """
    Extracts business info from ONE search result card.

    PagesJaunes HTML structure:
      - Name:       <h3> inside <a class="bi-denomination">
      - Phone:      .bi-fantomas .number-contact (after clicking button)
      - Address:    .bi-address (strip "Voir le plan")
      - Detail URL: <a class="bi-denomination"> has data-pjlb with base64 URL
      - Website:    check for "site internet" text in card HTML
    """
    info = {
        "name": "",
        "phone": "",
        "email": "",
        "address": "",
        "detail_url": "",
        "city": config.SEARCH_LOCATION,
        "category": config.SEARCH_CATEGORY,
        "has_website": False,
    }

    # --- Business name ---
    try:
        name_el = card.find_element(By.CSS_SELECTOR, "h3")
        info["name"] = name_el.text.strip()
    except Exception:
        pass

    # --- Detail page URL ---
    # The business name is a link (<a class="bi-denomination">) whose href
    # points to the detail page (e.g. /pros/detail?code=...).
    # Fallback: try data-pjlb attribute which contains a base64-encoded URL.
    try:
        link_el = card.find_element(By.CSS_SELECTOR, "a.bi-denomination")
        href = link_el.get_attribute("href") or ""
        if href and "/pros/" in href:
            info["detail_url"] = href
        else:
            # Fallback: decode base64 URL from data-pjlb attribute
            pjlb = link_el.get_attribute("data-pjlb") or ""
            url_match = re.search(r'"url"\s*:\s*"([^"]+)"', pjlb)
            if url_match:
                encoded = url_match.group(1)
                decoded_path = base64.b64decode(encoded).decode("utf-8")
                info["detail_url"] = "https://www.pagesjaunes.fr" + decoded_path
    except Exception:
        pass

    # --- Phone number (revealed after clicking "Afficher le N°") ---
    try:
        phone_el = card.find_element(By.CSS_SELECTOR, ".number-contact")
        phone_text = phone_el.text.strip()
        phone_clean = re.sub(r'^.*?:\s*', '', phone_text).strip()
        if phone_clean:
            info["phone"] = phone_clean
    except Exception:
        pass

    # --- Address ---
    try:
        addr_el = card.find_element(By.CSS_SELECTOR, ".bi-address")
        addr_text = addr_el.text.strip()
        addr_text = addr_text.replace("Voir le plan", "").strip()
        info["address"] = addr_text
    except Exception:
        pass

    # --- Website detection ---
    try:
        card_html = card.get_attribute("innerHTML").lower()
        if "site internet" in card_html or "bi-website" in card_html or "visiter le site" in card_html:
            info["has_website"] = True
    except Exception:
        pass

    return info


def fetch_email_from_detail_page(driver, detail_url, business_name):
    """
    Visits a business's detail page on PagesJaunes to find their email.

    KEY CONCEPT — Detail Pages:
      PagesJaunes only shows emails on individual business pages, not on
      search results. We visit each page and look for:
      1. mailto: links (direct email links)
      2. Email patterns in the page HTML (regex fallback)
      3. "E-mail" buttons that reveal the email when clicked

    Returns the email string, or "" if not found.
    """
    try:
        driver.get(detail_url)
        time.sleep(1.5)

        dismiss_cookie_popup(driver)

        # Method 1: Click any "E-mail" / "Afficher" email buttons
        email_buttons = driver.find_elements(By.CSS_SELECTOR,
            "a[title*='mail'], a[title*='Mail'], button[class*='mail'], "
            "a[data-pjstats*='EMAIL'], a[data-pjstats*='MAIL']"
        )
        for btn in email_buttons:
            try:
                driver.execute_script("arguments[0].click();", btn)
                time.sleep(0.5)
            except Exception:
                pass

        # Method 2: Look for mailto: links
        try:
            mailto_el = driver.find_element(By.CSS_SELECTOR, "a[href^='mailto:']")
            href = mailto_el.get_attribute("href") or ""
            email = href.replace("mailto:", "").split("?")[0].strip()
            if email:
                return email
        except Exception:
            pass

        # Method 3: Regex scan of page for email patterns
        page_html = driver.page_source
        # Look for email addresses, excluding common false positives
        emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', page_html)
        # Filter out PagesJaunes internal emails and tracking pixels
        for email in emails:
            lower = email.lower()
            if "pagesjaunes" not in lower and "solocal" not in lower and "didomi" not in lower:
                return email

    except Exception as e:
        print(f"      ⚠ Error visiting detail page: {e}")

    return ""


def save_leads(leads, filepath):
    """Saves the leads list to a CSV file."""
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

    FLOW:
      1. Search PagesJaunes for businesses
      2. Filter: keep only those WITHOUT a website
      3. For each one, visit their detail page to find email
      4. Save all leads to CSV
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
        # ── PHASE 1: Collect businesses from search results ──
        for page_num in range(1, config.MAX_PAGES + 1):
            url = build_url(config.SEARCH_CATEGORY, config.SEARCH_LOCATION, page_num)
            print(f"\n📄 Scraping page {page_num}/{config.MAX_PAGES}...")
            print(f"   URL: {url}")

            page_results = scrape_search_page(url, driver, page_num)

            # Keep only businesses WITHOUT a website
            qualified = [biz for biz in page_results if not biz["has_website"]]
            with_phone = [biz for biz in qualified if biz["phone"]]

            print(f"   📊 {len(qualified)} without website, {len(with_phone)} with phone")
            all_leads.extend(qualified)

            if page_num < config.MAX_PAGES:
                print("   ⏳ Waiting 2 seconds...")
                time.sleep(2)

        print(f"\n{'=' * 50}")
        print(f"📊 Found {len(all_leads)} businesses without a website")

        # ── PHASE 2: Visit detail pages to find emails ──
        leads_with_detail = [l for l in all_leads if l.get("detail_url")]
        if leads_with_detail:
            print(f"\n📧 Visiting {len(leads_with_detail)} detail pages to find emails...")
            for i, lead in enumerate(leads_with_detail, 1):
                print(f"   [{i}/{len(leads_with_detail)}] {lead['name']}...", end=" ")
                email = fetch_email_from_detail_page(driver, lead["detail_url"], lead["name"])
                if email:
                    lead["email"] = email
                    print(f"✅ {email}")
                else:
                    print("❌ no email")
                # Be polite between requests
                time.sleep(1.5)
        else:
            print("\n⚠ No detail page URLs found — cannot search for emails")

    finally:
        driver.quit()
        print("\n🌐 Browser closed.")

    # ── PHASE 3: Summary & Save ──
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

    return all_leads


if __name__ == "__main__":
    run()

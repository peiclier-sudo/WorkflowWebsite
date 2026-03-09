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
        "description": "",
        "specialties": "",
        "hours": "",
        "zone": "",
        "year_created": "",
        "review_score": "",
        "review_count": "",
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


def _is_real_email(email):
    """
    Returns False for placeholder/template emails found in PagesJaunes HTML.

    PagesJaunes pages contain fake example emails like "nom@mail.fr" in
    their HTML templates. We filter those out so we only keep real
    business emails.
    """
    lower = email.lower().strip()
    # PagesJaunes internal / template domains
    blacklist = [
        "pagesjaunes", "solocal", "didomi",  # PJ internal
        "mail.fr", "example.", "test.",       # Placeholder domains
        "email.fr", "adresse.fr",             # Generic placeholders
    ]
    for word in blacklist:
        if word in lower:
            return False
    # Must have at least 2 chars before @ (filters out "a@b.fr" type junk)
    local_part = lower.split("@")[0]
    if len(local_part) < 3:
        return False
    return True


def fetch_detail_page_info(driver, detail_url, business_name):
    """
    Visits a business's detail page on PagesJaunes to extract ALL useful info.

    KEY CONCEPT — Data Enrichment:
      PagesJaunes detail pages contain much more than just an email.
      We extract everything useful so DeepSeek can generate a better,
      more personalized website with real data (hours, specialties, etc.).

    Extracts:
      - email:        Business email address
      - description:  Presentation text written by the business
      - specialties:  List of specialties/services offered
      - hours:        Opening hours
      - zone:         Zone of intervention
      - year_created: Year the business was established
      - review_score: Average review rating (e.g. "4.5/5")
      - review_count: Number of reviews

    Returns a dict with all extracted fields (empty strings if not found).
    """
    info = {
        "email": "",
        "description": "",
        "specialties": "",
        "hours": "",
        "zone": "",
        "year_created": "",
        "review_score": "",
        "review_count": "",
    }

    try:
        driver.get(detail_url)
        time.sleep(1.5)

        dismiss_cookie_popup(driver)

        # ── EMAIL ──
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
            if email and _is_real_email(email):
                info["email"] = email
        except Exception:
            pass

        # Method 3: Regex scan of page for email patterns
        if not info["email"]:
            page_html = driver.page_source
            emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', page_html)
            for email in emails:
                if _is_real_email(email):
                    info["email"] = email
                    break

        # ── DESCRIPTION / PRESENTATION ──
        # PagesJaunes shows a "Présentation" or description block
        for selector in [".bloc-description p", ".description-pro p",
                         ".teaser-presentation", "[class*='description'] p",
                         ".pres-text", ".bi-description"]:
            try:
                desc_els = driver.find_elements(By.CSS_SELECTOR, selector)
                texts = [el.text.strip() for el in desc_els if el.text.strip()]
                if texts:
                    info["description"] = " ".join(texts)[:500]  # Cap at 500 chars
                    break
            except Exception:
                pass

        # ── SPECIALTIES / ACTIVITÉS ──
        # Usually listed as tags or bullet points
        for selector in [".activite-list li", ".tags-activite span",
                         ".liste-activites li", "[class*='activit'] li",
                         ".denomination-activite", ".bi-activities li"]:
            try:
                spec_els = driver.find_elements(By.CSS_SELECTOR, selector)
                specs = [el.text.strip() for el in spec_els if el.text.strip()]
                if specs:
                    info["specialties"] = ", ".join(specs[:10])  # Max 10
                    break
            except Exception:
                pass

        # ── OPENING HOURS (HORAIRES) ──
        for selector in [".horaire-ouvert", ".liste-horaires",
                         "[class*='horaire']", ".opening-hours",
                         ".bi-horaires"]:
            try:
                hours_els = driver.find_elements(By.CSS_SELECTOR, selector)
                hours_texts = [el.text.strip() for el in hours_els if el.text.strip()]
                if hours_texts:
                    info["hours"] = " | ".join(hours_texts)[:300]
                    break
            except Exception:
                pass

        # ── ZONE D'INTERVENTION ──
        for selector in [".zone-intervention", "[class*='zone']",
                         ".bi-zone"]:
            try:
                zone_el = driver.find_element(By.CSS_SELECTOR, selector)
                zone_text = zone_el.text.strip()
                if zone_text and len(zone_text) > 3:
                    info["zone"] = zone_text[:200]
                    break
            except Exception:
                pass

        # ── YEAR CREATED / ANCIENNETÉ ──
        try:
            page_text = driver.find_element(By.TAG_NAME, "body").text
            # Look for patterns like "Créée en 2005" or "Depuis 1998"
            year_match = re.search(r'(?:créé|fondé|depuis|établi|existant|en activité)[e]?\s+(?:en\s+)?(\d{4})',
                                   page_text, re.IGNORECASE)
            if year_match:
                info["year_created"] = year_match.group(1)
        except Exception:
            pass

        # ── REVIEWS / AVIS ──
        for selector in [".note-global", ".rating-score",
                         "[class*='note']", "[class*='rating']"]:
            try:
                review_el = driver.find_element(By.CSS_SELECTOR, selector)
                score_text = review_el.text.strip()
                # Extract score like "4.5" or "4,5/5"
                score_match = re.search(r'(\d[,.]?\d?)\s*/\s*5', score_text)
                if score_match:
                    info["review_score"] = score_match.group(1).replace(",", ".")
                elif re.match(r'^\d[,.]?\d?$', score_text):
                    info["review_score"] = score_text.replace(",", ".")
                break
            except Exception:
                pass

        # Review count
        for selector in [".nb-avis", "[class*='avis'] .count",
                         "[class*='review'] .count"]:
            try:
                count_el = driver.find_element(By.CSS_SELECTOR, selector)
                count_match = re.search(r'(\d+)', count_el.text)
                if count_match:
                    info["review_count"] = count_match.group(1)
                    break
            except Exception:
                pass

    except Exception as e:
        print(f"      ⚠ Error visiting detail page: {e}")

    return info


def save_leads(leads, filepath):
    """Saves the leads list to a CSV file."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)

    fieldnames = ["name", "phone", "email", "address", "city", "category",
                   "description", "specialties", "hours", "zone",
                   "year_created", "review_score", "review_count"]

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
            print(f"\n📧 Visiting {len(leads_with_detail)} detail pages for emails + extra info...")
            for i, lead in enumerate(leads_with_detail, 1):
                print(f"   [{i}/{len(leads_with_detail)}] {lead['name']}...", end=" ")
                detail_info = fetch_detail_page_info(driver, lead["detail_url"], lead["name"])

                # Merge all extracted info into the lead
                lead["email"] = detail_info["email"]
                lead["description"] = detail_info["description"]
                lead["specialties"] = detail_info["specialties"]
                lead["hours"] = detail_info["hours"]
                lead["zone"] = detail_info["zone"]
                lead["year_created"] = detail_info["year_created"]
                lead["review_score"] = detail_info["review_score"]
                lead["review_count"] = detail_info["review_count"]

                # Show what we found
                found = []
                if detail_info["email"]:
                    found.append(f"email={detail_info['email']}")
                if detail_info["specialties"]:
                    found.append("specialties")
                if detail_info["hours"]:
                    found.append("hours")
                if detail_info["description"]:
                    found.append("description")
                if detail_info["review_score"]:
                    found.append(f"rating={detail_info['review_score']}/5")

                if found:
                    print(f"✅ {', '.join(found)}")
                else:
                    print("⚠ basic info only")

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

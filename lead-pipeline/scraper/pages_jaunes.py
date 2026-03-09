"""Pages Jaunes scraper using Playwright.

Scrapes business listings from pagesjaunes.fr to find leads
that have an email address but no website.
"""

import logging
import random
import re
import time
from typing import List
from urllib.parse import quote

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

from core.models import Lead

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)


class PagesJaunesScraper:
    """Scrapes Pages Jaunes for business leads.

    Uses Playwright with headless Chromium to navigate the directory,
    extract business information, and filter results based on criteria.

    Attributes:
        base_url: The Pages Jaunes search base URL.
    """

    base_url = "https://www.pagesjaunes.fr/annuaire/chercherlespros"

    def search(
        self,
        category: str,
        city: str,
        limit: int = 10,
        require_email: bool = True,
        exclude_with_website: bool = True,
    ) -> List[Lead]:
        """Search Pages Jaunes for business leads matching criteria.

        Args:
            category: Business category to search (e.g. 'boulangerie').
            city: City to search in.
            limit: Maximum number of qualifying leads to return.
            require_email: Only return leads that have an email address.
            exclude_with_website: Skip leads that already have a website.

        Returns:
            List of Lead objects matching all filter conditions.
        """
        leads: List[Lead] = []
        page_num = 1

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(user_agent=USER_AGENT)
            page = context.new_page()

            while len(leads) < limit:
                url = (
                    f"{self.base_url}?quoiqui={quote(category)}"
                    f"&ou={quote(city)}&page={page_num}"
                )
                logger.info("Fetching page %d: %s", page_num, url)

                try:
                    page.goto(url, timeout=30000)
                    page.wait_for_selector(
                        "article.bi-bloc, .noResult", timeout=15000
                    )
                except PlaywrightTimeout:
                    logger.warning(
                        "Timeout loading page %d, stopping pagination.", page_num
                    )
                    break

                # Check if no results
                if page.query_selector(".noResult"):
                    logger.info("No more results found on page %d.", page_num)
                    break

                cards = page.query_selector_all("article.bi-bloc")
                if not cards:
                    logger.info("No listing cards found on page %d.", page_num)
                    break

                for card in cards:
                    if len(leads) >= limit:
                        break

                    lead = self._parse_card(card, category, city)
                    if lead is None:
                        continue

                    # Apply filters
                    if require_email and not lead.email:
                        continue
                    if exclude_with_website and self._has_website(card):
                        continue

                    leads.append(lead)
                    logger.info("Found lead: %s (%s)", lead.name, lead.email)

                page_num += 1
                # Human-like delay between pages
                delay = 1.5 + random.random() * 1.5
                logger.debug("Sleeping %.1fs before next page.", delay)
                time.sleep(delay)

            browser.close()

        logger.info(
            "Scraping complete: %d leads found for '%s' in '%s'.",
            len(leads),
            category,
            city,
        )
        return leads

    def _parse_card(self, card, category: str, city: str) -> Lead | None:
        """Extract lead information from a listing card element.

        Args:
            card: Playwright ElementHandle for the listing card.
            category: The search category.
            city: The search city.

        Returns:
            A Lead object or None if the card could not be parsed.
        """
        try:
            # Business name
            name_el = card.query_selector("h3 a, .denomination-links a")
            name = name_el.inner_text().strip() if name_el else ""
            if not name:
                return None

            # Address
            addr_el = card.query_selector(".bi-address .bi-adresse")
            address = addr_el.inner_text().strip() if addr_el else ""

            # Phone
            phone = ""
            phone_el = card.query_selector(
                "[data-pj-event='afficher_tel'] .coord-et-horaires-num"
            )
            if phone_el:
                phone = phone_el.inner_text().strip()

            # Description
            desc_el = card.query_selector(".bi-description, .pj-text")
            description = desc_el.inner_text().strip() if desc_el else ""

            # Opening hours
            hours_el = card.query_selector(".bi-horaires, .horaires-text")
            opening_hours = hours_el.inner_text().strip() if hours_el else ""

            # Email extraction
            email = self._extract_email(card)

            return Lead(
                name=name,
                category=category,
                city=city,
                address=address,
                phone=phone,
                email=email,
                description=description,
                opening_hours=opening_hours,
            )
        except Exception as exc:
            logger.warning("Failed to parse card: %s", exc)
            return None

    def _extract_email(self, card) -> str:
        """Extract email address from a listing card.

        Checks mailto links, data-email attributes, and text content.

        Args:
            card: Playwright ElementHandle for the listing card.

        Returns:
            Email address string, or empty string if not found.
        """
        # Check mailto links
        mailto = card.query_selector("a[href^='mailto:']")
        if mailto:
            href = mailto.get_attribute("href") or ""
            email = href.replace("mailto:", "").split("?")[0].strip()
            if email:
                return email

        # Check data-email attribute
        data_email = card.query_selector("[data-email]")
        if data_email:
            email = (data_email.get_attribute("data-email") or "").strip()
            if email:
                return email

        # Regex fallback on card text
        text = card.inner_text()
        match = re.search(
            r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", text
        )
        if match:
            return match.group(0)

        return ""

    def _has_website(self, card) -> bool:
        """Check if a listing card has a website link.

        Args:
            card: Playwright ElementHandle for the listing card.

        Returns:
            True if the listing has a website link.
        """
        site_link = card.query_selector("a[data-pj-event='site_internet']")
        return site_link is not None

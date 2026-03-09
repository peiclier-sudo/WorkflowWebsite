"""CLI entrypoint and pipeline orchestrator.

Coordinates the full lead pipeline: scrape -> generate -> deploy -> email.
Supports dry-run mode for local preview generation.
"""

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path

from core.config import Config
from core.models import Lead, PipelineResult
from scraper.pages_jaunes import PagesJaunesScraper
from generator.website_gen import WebsiteGenerator
from hosting.netlify import NetlifyHosting
from email_sender.gmail import GmailSender


def setup_logging() -> None:
    """Configure logging with both console and file handlers."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = f"pipeline_{timestamp}.log"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_file, encoding="utf-8"),
        ],
    )


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments.

    Returns:
        Parsed arguments namespace.
    """
    parser = argparse.ArgumentParser(
        description="B2B Lead Pipeline: Pages Jaunes -> DeepSeek -> Netlify -> Gmail",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--category",
        required=True,
        help="Business category to search (e.g. boulangerie, plombier)",
    )
    parser.add_argument(
        "--city",
        required=True,
        help="City to target (e.g. Paris, Lyon, Marseille)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Maximum number of leads to process (default: 10)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Generate HTML locally without deploying or sending emails",
    )
    return parser.parse_args()


def run_pipeline(args: argparse.Namespace) -> None:
    """Execute the full lead pipeline.

    Args:
        args: Parsed command-line arguments.
    """
    logger = logging.getLogger(__name__)
    config = Config()

    # Validate config unless dry-run (only need DeepSeek key)
    if not args.dry_run:
        config.validate()
    elif not config.DEEPSEEK_API_KEY:
        raise ValueError("DEEPSEEK_API_KEY is required even for dry-run mode.")

    # Initialize components
    logger.info(
        "Starting pipeline: category='%s', city='%s', limit=%d, dry_run=%s",
        args.category, args.city, args.limit, args.dry_run,
    )

    scraper = PagesJaunesScraper()
    generator = WebsiteGenerator(config.DEEPSEEK_API_KEY)
    netlify = None if args.dry_run else NetlifyHosting(config.NETLIFY_TOKEN)
    gmail = None if args.dry_run else GmailSender(config.GMAIL_CREDENTIALS_PATH)

    # Step 1: Scrape leads
    logger.info("Scraping Pages Jaunes for '%s' in '%s'...", args.category, args.city)
    leads = scraper.search(
        category=args.category,
        city=args.city,
        limit=args.limit,
        require_email=True,
        exclude_with_website=True,
    )
    logger.info("Found %d qualifying leads.", len(leads))

    if not leads:
        logger.warning("No leads found. Exiting.")
        return

    # Ensure previews directory exists for dry-run
    if args.dry_run:
        Path("previews").mkdir(exist_ok=True)

    # Step 2: Process each lead
    results: list[PipelineResult] = []
    success_count = 0

    for i, lead in enumerate(leads, 1):
        logger.info("--- Processing lead %d/%d: %s ---", i, len(leads), lead.name)
        result = PipelineResult(lead=lead)

        try:
            # Generate HTML
            logger.info("Generating website for '%s'...", lead.name)
            html = generator.generate(lead)
            result.html_generated = True

            if args.dry_run:
                # Save locally
                preview_path = Path("previews") / f"{lead.slug}.html"
                preview_path.write_text(html, encoding="utf-8")
                result.preview_path = str(preview_path)
                logger.info("Preview saved: %s", preview_path)
                success_count += 1
            else:
                # Deploy to Netlify
                logger.info("Deploying to Netlify as '%s'...", lead.slug)
                site_url = netlify.deploy(html, lead.slug)
                result.hosted = True
                result.site_url = site_url

                # Send email
                logger.info("Sending email to %s...", lead.email)
                sent = gmail.send(
                    lead=lead,
                    site_url=site_url,
                    sender_name=config.GMAIL_SENDER_NAME,
                    template=config.EMAIL_TEMPLATE,
                )
                result.email_sent = sent
                if sent:
                    success_count += 1

        except Exception as exc:
            result.error = str(exc)
            logger.error("Error processing '%s': %s", lead.name, exc)

        results.append(result)

        # Delay between leads
        if i < len(leads):
            logger.debug("Sleeping %.1fs before next lead...", config.DELAY_BETWEEN_LEADS)
            time.sleep(config.DELAY_BETWEEN_LEADS)

    # Step 3: Save results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_file = f"results_{timestamp}.json"
    results_data = [r.to_dict() for r in results]

    with open(results_file, "w", encoding="utf-8") as f:
        json.dump(results_data, f, ensure_ascii=False, indent=2)

    logger.info("Results saved to %s", results_file)

    # Summary
    logger.info(
        "Pipeline complete: %d/%d leads processed successfully.",
        success_count, len(leads),
    )


def main() -> None:
    """Main entry point."""
    setup_logging()
    args = parse_args()

    try:
        run_pipeline(args)
    except KeyboardInterrupt:
        logging.getLogger(__name__).info("Pipeline interrupted by user.")
        sys.exit(1)
    except ValueError as exc:
        logging.getLogger(__name__).error("Configuration error: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()

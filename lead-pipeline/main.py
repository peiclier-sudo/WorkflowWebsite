"""
MAIN — The remote control for your lead pipeline.

Run this file to execute any step:
  python main.py scrape        ← Step 1: Find leads
  python main.py build         ← Step 2: Generate websites (coming soon)
  python main.py deploy        ← Step 3: Put online (coming soon)
  python main.py email         ← Step 4: Send emails (coming soon)
  python main.py all           ← Run everything in order
"""

import sys


def main():
    # sys.argv = the words you typed in the terminal
    # sys.argv[0] = "main.py", sys.argv[1] = the command you typed
    if len(sys.argv) < 2:
        print("Usage: python main.py <command>")
        print()
        print("Commands:")
        print("  scrape  — Step 1: Find leads on PagesJaunes")
        print("  build   — Step 2: Generate websites (coming soon)")
        print("  deploy  — Step 3: Deploy to Netlify (coming soon)")
        print("  email   — Step 4: Send emails (coming soon)")
        print("  all     — Run all steps in order")
        return

    command = sys.argv[1].lower()

    if command == "scrape":
        from scraper_module import run_scraper
        run_scraper()

    elif command == "build":
        from builder_module import run_builder
        run_builder()

    elif command == "deploy":
        print("🚧 Step 3 (deployer) not built yet!")

    elif command == "email":
        print("🚧 Step 4 (emailer) not built yet!")

    elif command == "all":
        print("Running full pipeline...\n")
        from scraper_module import run_scraper
        run_scraper()
        # Future steps will be added here

    else:
        print(f"Unknown command: {command}")
        print("Run 'python main.py' to see available commands.")


# --- Helper imports ---
# These exist so main.py can call each step cleanly

def _setup_path():
    """Add project root to Python path so imports work."""
    import os
    project_dir = os.path.dirname(os.path.abspath(__file__))
    if project_dir not in sys.path:
        sys.path.insert(0, project_dir)

# This creates a simple wrapper to call the scraper
class scraper_module:
    @staticmethod
    def run_scraper():
        _setup_path()
        from importlib import import_module
        # Import scraper.py from the 1_scraper folder
        # We use import_module because the folder name starts with a number
        spec = import_module("1_scraper.scraper")
        spec.run()

class builder_module:
    @staticmethod
    def run_builder():
        _setup_path()
        from importlib import import_module
        spec = import_module("2_website_builder.builder")
        spec.run()

# Make the wrappers importable
sys.modules["scraper_module"] = scraper_module
sys.modules["builder_module"] = builder_module


if __name__ == "__main__":
    main()

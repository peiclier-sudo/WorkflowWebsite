# Lead Pipeline — B2B Automated Outreach

Automated B2B lead pipeline that scrapes French businesses from Pages Jaunes, generates personalized websites, deploys them to Netlify, and sends cold outreach emails via Gmail.

## Architecture

```
┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐
│   1. SCRAPE      │───▶│   2. GENERATE    │───▶│   3. DEPLOY      │───▶│   4. EMAIL       │
│                  │    │                  │    │                  │    │                  │
│  Pages Jaunes    │    │  DeepSeek API    │    │  Netlify API     │    │  Gmail OAuth2    │
│  (Playwright)    │    │  + HTML Template │    │  (Free tier)     │    │  (Personalized)  │
│                  │    │                  │    │                  │    │                  │
│  Finds leads     │    │  Creates custom  │    │  Deploys site    │    │  Sends email     │
│  with email,     │    │  landing page    │    │  to subdomain    │    │  with live URL   │
│  no website      │    │  per business    │    │  .netlify.app    │    │  + CTA button    │
└──────────────────┘    └──────────────────┘    └──────────────────┘    └──────────────────┘
```

## Prerequisites

- **Python 3.10+**
- **Playwright** (Chromium browser for scraping)
- **3 API keys:**
  - DeepSeek API key (for content generation)
  - Netlify Personal Access Token (for site deployment)
  - Gmail OAuth credentials (for email sending)

## Setup

### 1. Install dependencies

```bash
cd lead-pipeline
pip install -r requirements.txt
playwright install chromium
```

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env` with your credentials:

### 3. Get API keys

**DeepSeek API Key:**
1. Go to [platform.deepseek.com](https://platform.deepseek.com)
2. Create an account and generate an API key
3. Add to `.env` as `DEEPSEEK_API_KEY`

**Netlify Token:**
1. Go to [app.netlify.com/user/applications](https://app.netlify.com/user/applications)
2. Create a Personal Access Token
3. Add to `.env` as `NETLIFY_TOKEN`

**Gmail OAuth Setup:**
1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create a project and enable the Gmail API
3. Create OAuth 2.0 credentials (Desktop application)
4. Download `credentials.json` to the `lead-pipeline/` directory
5. On first run, a browser window will open for authorization
6. `token.json` is created automatically after auth (gitignored)

## Usage

### Dry-run mode (local preview, no deploy, no email)

```bash
python main.py --category boulangerie --city Paris --dry-run
```

Generated HTML files are saved to `previews/` (gitignored).

### Full pipeline

```bash
python main.py --category plombier --city Lyon --limit 5
```

This will:
1. Scrape up to 5 plumbers in Lyon from Pages Jaunes
2. Generate a personalized website for each
3. Deploy each site to Netlify
4. Send a cold outreach email with the live URL

### Options

| Flag | Description | Default |
|------|-------------|---------|
| `--category` | Business category (required) | — |
| `--city` | Target city (required) | — |
| `--limit` | Max leads to process | 10 |
| `--dry-run` | Preview only, no deploy/email | False |

## Project Structure

```
lead-pipeline/
├── main.py                    # CLI entrypoint & pipeline orchestrator
├── requirements.txt           # Python dependencies
├── .env.example               # Environment variable template
├── .gitignore                 # Excludes secrets and generated files
├── README.md                  # This file
│
├── core/
│   ├── config.py              # Config from .env with validation
│   └── models.py              # Lead and PipelineResult dataclasses
│
├── scraper/
│   └── pages_jaunes.py        # Playwright scraper for Pages Jaunes
│
├── generator/
│   ├── website_gen.py          # DeepSeek API content + template fill
│   └── template.html          # Master HTML template (responsive, SEO)
│
├── hosting/
│   └── netlify.py             # Netlify API: create site & deploy
│
├── email_sender/
│   └── gmail.py               # Gmail OAuth2 HTML email sender
│
└── tests/
    ├── test_models.py         # Tests for dataclasses and slugify
    ├── test_generator.py      # Tests for template filling and API
    └── test_netlify.py        # Tests for Netlify deployment
```

## Customization

### Adding sectors

Edit `generator/website_gen.py` and add entries to:
- `SCHEMA_TYPES` — Schema.org type for structured data
- `SECTOR_PALETTES` — Color scheme (9 color values)
- `SECTOR_FONTS` — Google Fonts pair (display + body)
- `SECTOR_EMOJIS` — Emoji icon for the sector

### Editing email template

Modify the `_render_template` method in `email_sender/gmail.py`. The HTML email uses inline CSS for maximum email client compatibility.

### Tuning DeepSeek prompt

Edit the prompt string in `generator/website_gen.py` → `_get_content_from_deepseek()`. Adjust temperature, max_tokens, or the prompt itself to change tone and content style.

## Cost Estimate

| Service | Cost per lead | Notes |
|---------|--------------|-------|
| DeepSeek API | ~$0.0005 | ~1K tokens per call |
| Netlify | $0.00 | Free tier (100 sites) |
| Gmail | $0.00 | Free with OAuth |
| **Total** | **~$0.001** | |

## Legal / RGPD

This tool is designed for **B2B cold outreach** which is legal in France under the following conditions:

- **B2B only**: emails are sent to professional addresses publicly listed on Pages Jaunes
- **Legitimate interest**: providing a relevant service (website creation) to businesses that don't have one
- **Unsubscribe**: every email includes an unsubscribe mechanism (RGPD Art. 21)
- **Transparency**: the sender's identity and purpose are clearly stated
- **Data minimization**: only publicly available business information is collected

**Important:** Always comply with CNIL guidelines and the French Commercial Code (Art. L34-5 CPCE). Ensure your outreach is proportionate and respectful.

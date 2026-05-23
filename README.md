# Ness Assignment — eBay E2E Automation

Playwright + Python automation for eBay: search with price filter, add items to cart, verify cart total.

## Prerequisites

- Python 3.11+

## Setup

```bash
pip install -r requirements.txt
playwright install chromium
```

Create a `.env` file with `EBAY_URL`, `EBAY_USERNAME`, and `EBAY_PASSWORD` if login is required.

## Run tests

```bash
pytest tests/test_e2e_flow.py
```

Test data is loaded from `data/test_data.json` (search query, max price, item limit).

## Test reports

Each run writes reports under `reports/` (gitignored):

- **HTML** — `reports/report.html` (open in your browser)
- **JUnit XML** — `reports/junit.xml` (for CI tools, Azure DevOps, Jenkins, etc.)

## Architecture (brief)

- **Pages** — Page Object Model (`pages/`)
- **Flows** — orchestration (`flows/`)
- **Config / data** — `config.py` + `data/test_data.json`
- **Utils** — helpers (`utils/`)

Screenshots are saved under `logs/screenshots/` during the run.

## Limitations

- Depends on live eBay (external site, possible captcha or layout changes).
- CI skips e2e tests on GitHub Actions to avoid captcha.
- Currency and guest/login behavior follow the target eBay locale/account.

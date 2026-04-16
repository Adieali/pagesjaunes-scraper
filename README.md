# 🕷 Pages Jaunes Pro Scraper

> **Professional B2B data collection tool** for Pages Jaunes (France's leading business directory).
> Collects only **publicly displayed professional data**, fully **GDPR/RGPD-compliant**.

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://python.org)
[![Scrapy](https://img.shields.io/badge/Scrapy-2.11-60A839?logo=scrapy)](https://scrapy.org)
[![Playwright](https://img.shields.io/badge/Playwright-JS%20rendering-2EAD33?logo=playwright)](https://playwright.dev)
[![Docker](https://img.shields.io/badge/Docker-ready-2496ED?logo=docker&logoColor=white)](https://docker.com)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 📋 Features

- **Full spider with Playwright** — handles JavaScript-rendered content (dynamic listings, lazy-loaded data)
- **4 data categories** collected per business listing:
  - 🏢 General info (name, category, description, subcategories)
  - 📍 Geolocation (full address + GPS coordinates via JSON-LD/data attributes)
  - 📞 Professional contacts (phone, website, email, social media links)
  - ⭐ Reviews & ratings (average score, review count, rating distribution)
- **Opening hours** extraction (structured dict by day)
- **3 output formats**: CSV, JSON Lines, SQLite database
- **Rotating User-Agents** (15+ real browser fingerprints)
- **Proxy rotation middleware** (HTTP/HTTPS/SOCKS5, configurable via YAML or env)
- **Anti-ban protection**: soft-ban detection, exponential backoff, AutoThrottle
- **Configurable CLI** (`pj-scraper scrape/export/stats`)
- **Docker + docker-compose** for isolated, reproducible runs
- **Unit tests** with pytest (17 test cases)

---

## 🏗 Architecture

```
pagesjaunes-pro-scraper/
├── pagesjaunes/
│   ├── spiders/
│   │   └── pagesjaunes_spider.py   # Main spider (search + detail pages)
│   ├── middlewares/
│   │   ├── user_agent.py           # Random User-Agent rotation
│   │   ├── proxy.py                # Proxy rotation (YAML/env)
│   │   ├── retry.py                # Smart retry + soft-ban detection
│   │   └── stats.py                # Custom crawl statistics
│   ├── items.py                    # Data model (30+ fields)
│   ├── pipelines.py                # Validation → Cleaning → Dedup → SQLite/CSV/JSON
│   ├── settings.py                 # Scrapy settings (throttling, Playwright, etc.)
│   └── utils.py                    # Helpers (GPS extract, phone normalize, etc.)
├── cli/
│   └── main.py                     # Click CLI (scrape / export / stats)
├── tests/
│   ├── test_spider.py              # Unit tests (17 cases)
│   └── fixtures/
│       └── sample_listing.html    # HTML fixture for offline testing
├── config/
│   └── proxies.yaml               # Proxy list configuration
├── data/                          # Output directory (CSV, JSON, SQLite)
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

---

## ⚡ Quick Start

### Option 1 — Local (with virtualenv)

```bash
# Clone
git clone https://github.com/YOUR_USERNAME/pagesjaunes-pro-scraper.git
cd pagesjaunes-pro-scraper

# Virtual environment
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
pip install -e .

# Install Playwright browser
playwright install chromium

# Run scraper
pj-scraper scrape --what "restaurant" --where "Paris" --pages 5
```

### Option 2 — Docker (recommended for production)

```bash
# Build image
docker build -t pagesjaunes-pro-scraper .

# Run scraper
docker run --rm -v $(pwd)/data:/app/data \
  pagesjaunes-pro-scraper scrape \
  --what "plombier" \
  --where "Lyon" \
  --pages 10

# Or with docker-compose
WHAT="dentiste" WHERE="Marseille" PAGES=20 docker-compose up scraper
```

---

## 🖥 CLI Reference

### `scrape` — Launch a crawl

```bash
pj-scraper scrape [OPTIONS]

Options:
  -w, --what TEXT        Business sector/type (required)   e.g. "restaurant"
  -l, --where TEXT       Geographic zone (required)        e.g. "Paris", "75001"
  -p, --pages INT        Max result pages  [default: 5]
  -o, --output-dir PATH  Output directory  [default: data]
  --delay FLOAT          Min delay between requests (s) [default: 2.0]
  --playwright/--no-playwright  Enable JS rendering [default: enabled]
  --proxy-file PATH      Path to proxies YAML file
  -v, --verbose          Debug logging
```

**Examples:**

```bash
# Scrape restaurants in Paris (5 pages)
pj-scraper scrape --what "restaurant" --where "Paris"

# Scrape plumbers in Lyon, 20 pages, with 3s delay
pj-scraper scrape --what "plombier" --where "Lyon" --pages 20 --delay 3.0

# Fast mode without Playwright (static pages only)
pj-scraper scrape --what "hotel" --where "Nice" --no-playwright

# With proxy rotation
pj-scraper scrape --what "dentiste" --where "Bordeaux" --proxy-file config/proxies.yaml
```

### `export` — Re-export from SQLite

```bash
pj-scraper export --db data/pagesjaunes.db --format json --city Lyon --min-rating 4.0
```

### `stats` — Database statistics

```bash
pj-scraper stats --db data/pagesjaunes.db
```

Output example:
```
📊  Statistiques de la base
────────────────────────────────────────
  Total établissements    : 1,247
  Avec téléphone          : 1,189 (95.3%)
  Avec site web           : 734 (58.9%)
  Avec note               : 892 (71.5%)
  Note moyenne            : 4.12/5

  Top 5 villes :
    Paris                     487 établissements
    Lyon                      312 établissements
    ...
```

---

## 📦 Data Schema

Each scraped record contains up to **30 fields**:

| Field | Type | Description |
|-------|------|-------------|
| `listing_id` | str | Unique Pages Jaunes identifier |
| `name` | str | Business name |
| `category` | str | Main activity category |
| `subcategories` | list | Secondary categories |
| `description` | str | Public business description |
| `address_street` | str | Street address |
| `address_city` | str | City |
| `address_postal_code` | str | Postal code |
| `latitude` | float | GPS latitude |
| `longitude` | float | GPS longitude |
| `phone` | str | Public phone (normalized) |
| `website` | str | Business website |
| `email` | str | Public email |
| `social_facebook` | str | Facebook URL |
| `social_instagram` | str | Instagram URL |
| `social_linkedin` | str | LinkedIn URL |
| `opening_hours` | dict | `{day: [hours]}` |
| `rating` | float | Average rating (0–5) |
| `reviews_count` | int | Total review count |
| `rating_distribution` | dict | `{1: n, 2: n, 3: n, 4: n, 5: n}` |
| `scraped_at` | ISO 8601 | Timestamp of collection |

---

## ⚖️ GDPR / RGPD Compliance

This scraper is designed with **privacy by design** principles:

- ✅ **Only public business data** — information voluntarily published by professionals on Pages Jaunes
- ✅ **No private individual data** — strictly B2B commercial listings (no personal names, no private addresses)
- ✅ **Respectful rate limiting** — minimum 2 second delay between requests, AutoThrottle enabled
- ✅ **No data sale or redistribution** — collected data should be used in compliance with local regulations
- ⚠️ **Your responsibility** — ensure your use case complies with GDPR Article 6 (lawful basis) and Pages Jaunes Terms of Service

> **Legal note**: Web scraping of publicly available data is generally permitted under EU case law (Ryanair v PR Aviation, CJEU 2015) when not circumventing technical measures. Always verify compliance with your specific use case.

---

## 🧪 Running Tests

```bash
# Install test dependencies
pip install pytest pytest-asyncio pytest-cov

# Run all tests
pytest tests/ -v

# With coverage report
pytest tests/ --cov=pagesjaunes --cov-report=html
open htmlcov/index.html
```

---

## ⚙️ Configuration

### Proxy Setup

Create `config/proxies.yaml`:
```yaml
proxies:
  - http://user:password@proxy1.example.com:8080
  - socks5://user:password@proxy2.example.com:1080
```

Or set environment variable:
```bash
export PROXIES="http://proxy1:8080,http://proxy2:8080"
export PROXY_ENABLED=true
```

### Custom Settings

Override any Scrapy setting via environment or CLI:
```bash
# More aggressive (faster, higher ban risk)
pj-scraper scrape --what "hotel" --where "Paris" --delay 0.5

# More conservative (slower, safer)
pj-scraper scrape --what "hotel" --where "Paris" --delay 5.0
```

---

## 🔧 Technical Stack

| Component | Technology |
|-----------|-----------|
| Spider framework | **Scrapy 2.11** |
| JS rendering | **Playwright (Chromium)** |
| Anti-detection | Custom UA rotation + proxy middleware |
| Storage | **SQLite** (primary) + CSV + JSON Lines |
| CLI | **Click 8** |
| Containerization | **Docker + docker-compose** |
| Testing | **pytest + pytest-asyncio** |
| Python | **3.11+** |

---

## 📄 License

MIT — see [LICENSE](LICENSE)

---

*Built as a professional portfolio project demonstrating advanced Python web scraping techniques.*

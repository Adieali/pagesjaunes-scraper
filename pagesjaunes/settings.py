"""
Scrapy Settings — Pages Jaunes Pro Scraper
"""

BOT_NAME = "pagesjaunes_scraper"

SPIDER_MODULES = ["pagesjaunes.spiders"]
NEWSPIDER_MODULE = "pagesjaunes.spiders"

# ── Conformité & respect des règles ──────────────────────────────────────────
# Respecter robots.txt (recommandé, mais PJ bloque les bots par robots.txt)
ROBOTSTXT_OBEY = False  # Overridable via CLI --respect-robots

# ── Throttling / Délais respectueux ──────────────────────────────────────────
DOWNLOAD_DELAY = 2.0            # Délai minimum entre requêtes (secondes)
RANDOMIZE_DOWNLOAD_DELAY = True # Varie entre 0.5x et 1.5x du délai
CONCURRENT_REQUESTS = 4
CONCURRENT_REQUESTS_PER_DOMAIN = 2
AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 2
AUTOTHROTTLE_MAX_DELAY = 10
AUTOTHROTTLE_TARGET_CONCURRENCY = 2.0
AUTOTHROTTLE_DEBUG = False

# ── Playwright (pour pages JS-rendues) ───────────────────────────────────────
DOWNLOAD_HANDLERS = {
    "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
    "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
}

TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"

PLAYWRIGHT_BROWSER_TYPE = "chromium"
PLAYWRIGHT_LAUNCH_OPTIONS = {
    "headless": True,
    "args": [
        "--no-sandbox",
        "--disable-blink-features=AutomationControlled",
        "--disable-dev-shm-usage",
    ],
}
PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT = 30000  # 30s
PLAYWRIGHT_ABORT_REQUEST = "pagesjaunes.utils.abort_non_essential"

# ── Middlewares ───────────────────────────────────────────────────────────────
DOWNLOADER_MIDDLEWARES = {
    "scrapy.downloadermiddlewares.useragent.UserAgentMiddleware": None,
    "pagesjaunes.middlewares.RandomUserAgentMiddleware": 400,
    "pagesjaunes.middlewares.ProxyRotationMiddleware": 410,
    "pagesjaunes.middlewares.RetryOnBanMiddleware": 420,
    "scrapy.downloadermiddlewares.retry.RetryMiddleware": 550,
    "scrapy_playwright.middleware.ScrapyPlaywrightDownloadMiddleware": 800,
}

SPIDER_MIDDLEWARES = {
    "pagesjaunes.middlewares.StatsMiddleware": 100,
}

# ── Pipelines ─────────────────────────────────────────────────────────────────
ITEM_PIPELINES = {
    "pagesjaunes.pipelines.ValidationPipeline": 100,
    "pagesjaunes.pipelines.CleaningPipeline": 200,
    "pagesjaunes.pipelines.DuplicateFilterPipeline": 300,
    "pagesjaunes.pipelines.SQLitePipeline": 400,
    "pagesjaunes.pipelines.CSVPipeline": 500,
    "pagesjaunes.pipelines.JSONPipeline": 600,
}

# ── Retry ─────────────────────────────────────────────────────────────────────
RETRY_ENABLED = True
RETRY_TIMES = 3
RETRY_HTTP_CODES = [429, 500, 502, 503, 504, 403]
RETRY_BACKOFF_BASE = 2.0

# ── Cache (désactivé en prod, utile en dev) ───────────────────────────────────
HTTPCACHE_ENABLED = False
HTTPCACHE_EXPIRATION_SECS = 86400
HTTPCACHE_DIR = ".scrapy/httpcache"
HTTPCACHE_IGNORE_HTTP_CODES = [403, 429, 500]

# ── Flux de sortie ────────────────────────────────────────────────────────────
FEEDS = {}  # Géré par les pipelines custom

# ── Encodage & compression ────────────────────────────────────────────────────
FEED_EXPORT_ENCODING = "utf-8"

# ── Logs ──────────────────────────────────────────────────────────────────────
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s [%(name)s] %(levelname)s: %(message)s"

# ── Extensions ────────────────────────────────────────────────────────────────
EXTENSIONS = {
    "scrapy.extensions.telnet.TelnetConsole": None,
    "scrapy.extensions.corestats.CoreStats": 500,
    "scrapy.extensions.memusage.MemoryUsage": 500,
}

MEMUSAGE_ENABLED = True
MEMUSAGE_WARNING_MB = 512
MEMUSAGE_LIMIT_MB = 1024

# ── Cookies ───────────────────────────────────────────────────────────────────
COOKIES_ENABLED = True
COOKIES_DEBUG = False

# ── Headers par défaut ────────────────────────────────────────────────────────
DEFAULT_REQUEST_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "DNT": "1",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

# ── Chemins de sortie (overridable via CLI) ───────────────────────────────────
OUTPUT_DIR = "data"
SQLITE_DB_PATH = "data/pagesjaunes.db"

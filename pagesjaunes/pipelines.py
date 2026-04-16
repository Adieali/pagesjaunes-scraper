"""
Pipelines de traitement des données collectées.

Chaîne de traitement :
  ValidationPipeline  → Valide les champs obligatoires
  CleaningPipeline    → Normalise et nettoie les données
  DuplicateFilter     → Élimine les doublons (par URL source)
  SQLitePipeline      → Persistance base de données locale
  CSVPipeline         → Export CSV (append)
  JSONPipeline        → Export JSON Lines (1 item / ligne)
"""

import csv
import hashlib
import json
import logging
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from itemadapter import ItemAdapter
from scrapy.exceptions import DropItem

logger = logging.getLogger(__name__)


# ── 1. Validation ──────────────────────────────────────────────────────────────

class ValidationPipeline:
    """Rejette les items sans nom d'établissement."""

    REQUIRED_FIELDS = ["name", "source_url"]

    def process_item(self, item, spider):
        adapter = ItemAdapter(item)
        for field in self.REQUIRED_FIELDS:
            if not adapter.get(field):
                raise DropItem(
                    f"Champ obligatoire manquant '{field}' — {adapter.get('source_url')}"
                )
        return item


# ── 2. Nettoyage ───────────────────────────────────────────────────────────────

class CleaningPipeline:
    """Normalise les données : téléphone, URL, rating, etc."""

    def process_item(self, item, spider):
        adapter = ItemAdapter(item)

        # Normalisation téléphone français
        phone = adapter.get("phone", "") or ""
        adapter["phone"] = self._normalize_phone(phone)

        # Normalisation URL
        website = adapter.get("website", "") or ""
        if website and not website.startswith(("http://", "https://")):
            adapter["website"] = f"https://{website}"

        # Rating entre 0 et 5
        rating = adapter.get("rating")
        if rating is not None and not (0 <= rating <= 5):
            adapter["rating"] = None

        # Nettoyage du nom
        name = adapter.get("name", "") or ""
        adapter["name"] = " ".join(name.split()).strip()

        return item

    @staticmethod
    def _normalize_phone(phone: str) -> str:
        digits = re.sub(r"\D", "", phone)
        if digits.startswith("33") and len(digits) == 11:
            digits = "0" + digits[2:]
        if len(digits) == 10 and digits.startswith("0"):
            return " ".join([digits[i:i+2] for i in range(0, 10, 2)])
        return phone  # Retourner tel quel si non reconnu


# ── 3. Filtre de doublons ──────────────────────────────────────────────────────

class DuplicateFilterPipeline:
    """Élimine les items déjà vus (par URL ou listing_id)."""

    def __init__(self):
        self.seen_urls: set[str] = set()

    def process_item(self, item, spider):
        adapter = ItemAdapter(item)
        key = adapter.get("listing_id") or adapter.get("source_url", "")
        if key in self.seen_urls:
            raise DropItem(f"Doublon ignoré: {key}")
        self.seen_urls.add(key)
        return item


# ── 4. SQLite ──────────────────────────────────────────────────────────────────

SQLITE_CREATE = """
CREATE TABLE IF NOT EXISTS businesses (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    listing_id          TEXT UNIQUE,
    source_url          TEXT,
    name                TEXT NOT NULL,
    category            TEXT,
    subcategories       TEXT,  -- JSON array
    description         TEXT,
    address_street      TEXT,
    address_city        TEXT,
    address_postal_code TEXT,
    address_department  TEXT,
    address_region      TEXT,
    latitude            REAL,
    longitude           REAL,
    phone               TEXT,
    website             TEXT,
    email               TEXT,
    social_facebook     TEXT,
    social_twitter      TEXT,
    social_instagram    TEXT,
    social_linkedin     TEXT,
    opening_hours       TEXT,  -- JSON object
    is_open_now         INTEGER,
    rating              REAL,
    reviews_count       INTEGER,
    rating_distribution TEXT,  -- JSON object
    search_query        TEXT,
    search_location     TEXT,
    scraped_at          TEXT,
    page_number         INTEGER,
    created_at          TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_city ON businesses(address_city);
CREATE INDEX IF NOT EXISTS idx_category ON businesses(category);
CREATE INDEX IF NOT EXISTS idx_rating ON businesses(rating);
CREATE INDEX IF NOT EXISTS idx_query ON businesses(search_query, search_location);
"""


class SQLitePipeline:
    """Stocke les items dans une base SQLite locale."""

    def __init__(self, db_path: str):
        self.db_path = db_path

    @classmethod
    def from_crawler(cls, crawler):
        return cls(
            db_path=crawler.settings.get("SQLITE_DB_PATH", "data/pagesjaunes.db")
        )

    def open_spider(self, spider):
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.executescript(SQLITE_CREATE)
        self.conn.commit()
        logger.info(f"SQLite ouvert: {self.db_path}")

    def close_spider(self, spider):
        self.conn.commit()
        self.conn.close()
        logger.info(f"SQLite fermé: {self.db_path}")

    def process_item(self, item, spider):
        adapter = ItemAdapter(item)
        data = dict(adapter)

        # Sérialisation des champs JSON
        for field in ("subcategories", "opening_hours", "rating_distribution"):
            val = data.get(field)
            data[field] = json.dumps(val, ensure_ascii=False) if val else None

        data["is_open_now"] = int(data.get("is_open_now") or 0)

        cols = [k for k in data if k in self._get_columns()]
        placeholders = ", ".join(["?"] * len(cols))
        col_names = ", ".join(cols)
        values = [data[c] for c in cols]

        try:
            self.conn.execute(
                f"INSERT OR REPLACE INTO businesses ({col_names}) VALUES ({placeholders})",
                values,
            )
        except sqlite3.Error as e:
            logger.error(f"SQLite erreur: {e} — item: {data.get('listing_id')}")

        return item

    def _get_columns(self) -> list[str]:
        cursor = self.conn.execute("PRAGMA table_info(businesses)")
        return [row[1] for row in cursor.fetchall()]


# ── 5. CSV ─────────────────────────────────────────────────────────────────────

CSV_FIELDS = [
    "listing_id", "name", "category", "address_street", "address_city",
    "address_postal_code", "address_region", "latitude", "longitude",
    "phone", "website", "email", "rating", "reviews_count",
    "search_query", "search_location", "scraped_at", "source_url",
]


class CSVPipeline:
    """Exporte les items dans un fichier CSV (mode append)."""

    def __init__(self, output_dir: str):
        self.output_dir = output_dir

    @classmethod
    def from_crawler(cls, crawler):
        return cls(output_dir=crawler.settings.get("OUTPUT_DIR", "data"))

    def open_spider(self, spider):
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.filepath = Path(self.output_dir) / f"pagesjaunes_{timestamp}.csv"
        self.file = open(self.filepath, "w", newline="", encoding="utf-8-sig")
        self.writer = csv.DictWriter(
            self.file,
            fieldnames=CSV_FIELDS,
            extrasaction="ignore",
        )
        self.writer.writeheader()
        logger.info(f"CSV: {self.filepath}")

    def close_spider(self, spider):
        self.file.close()
        logger.info(f"CSV fermé: {self.filepath}")

    def process_item(self, item, spider):
        adapter = ItemAdapter(item)
        self.writer.writerow(dict(adapter))
        return item


# ── 6. JSON Lines ──────────────────────────────────────────────────────────────

class JSONPipeline:
    """Exporte les items en JSON Lines (1 item par ligne, UTF-8)."""

    def __init__(self, output_dir: str):
        self.output_dir = output_dir

    @classmethod
    def from_crawler(cls, crawler):
        return cls(output_dir=crawler.settings.get("OUTPUT_DIR", "data"))

    def open_spider(self, spider):
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.filepath = Path(self.output_dir) / f"pagesjaunes_{timestamp}.jsonl"
        self.file = open(self.filepath, "w", encoding="utf-8")
        logger.info(f"JSON Lines: {self.filepath}")

    def close_spider(self, spider):
        self.file.close()
        logger.info(f"JSON Lines fermé: {self.filepath}")

    def process_item(self, item, spider):
        adapter = ItemAdapter(item)
        line = json.dumps(dict(adapter), ensure_ascii=False)
        self.file.write(line + "\n")
        return item

"""
Middleware de statistiques enrichies.
"""

import logging
import time

logger = logging.getLogger(__name__)


class StatsMiddleware:
    """
    Collecte des stats custom : temps de crawl, taux de succès, items/sec.
    """

    def __init__(self):
        self.start_time = None
        self.items_scraped = 0

    def spider_opened(self, spider):
        self.start_time = time.time()
        logger.info(f"Spider '{spider.name}' démarré.")

    def spider_closed(self, spider):
        elapsed = time.time() - self.start_time if self.start_time else 0
        rate = self.items_scraped / elapsed if elapsed > 0 else 0
        logger.info(
            f"Spider '{spider.name}' terminé — "
            f"{self.items_scraped} items en {elapsed:.1f}s "
            f"({rate:.2f} items/s)"
        )

    def item_scraped(self, item, response, spider):
        self.items_scraped += 1

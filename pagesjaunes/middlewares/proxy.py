"""
Middleware de rotation de proxies.
Supporte les proxies HTTP/HTTPS/SOCKS5 via variable d'environnement ou fichier YAML.
"""

import random
import logging
import os
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)


class ProxyRotationMiddleware:
    """
    Rotate les proxies à chaque requête.

    Configuration via :
      - Variable d'env PROXIES (liste séparée par virgules)
      - Fichier config/proxies.yaml
      - Setting PROXY_LIST dans scrapy settings
    """

    def __init__(self, proxies: list[str], enabled: bool):
        self.proxies = proxies
        self.enabled = enabled and bool(proxies)
        if self.enabled:
            logger.info(f"ProxyRotation: {len(proxies)} proxies chargés.")
        else:
            logger.info("ProxyRotation: désactivé (aucun proxy configuré).")

    @classmethod
    def from_crawler(cls, crawler):
        enabled = crawler.settings.getbool("PROXY_ENABLED", False)
        proxies = cls._load_proxies(crawler.settings)
        return cls(proxies, enabled)

    @staticmethod
    def _load_proxies(settings) -> list[str]:
        # 1. Variable d'environnement
        env_proxies = os.environ.get("PROXIES", "")
        if env_proxies:
            return [p.strip() for p in env_proxies.split(",") if p.strip()]

        # 2. Setting Scrapy
        setting_proxies = settings.getlist("PROXY_LIST", [])
        if setting_proxies:
            return setting_proxies

        # 3. Fichier YAML
        proxy_file = Path("config/proxies.yaml")
        if proxy_file.exists():
            with open(proxy_file) as f:
                data = yaml.safe_load(f)
                return data.get("proxies", [])

        return []

    def process_request(self, request, spider):
        if not self.enabled or not self.proxies:
            return
        proxy = random.choice(self.proxies)
        request.meta["proxy"] = proxy
        logger.debug(f"Proxy utilisé: {proxy}")

    def process_response(self, request, response, spider):
        if response.status in (403, 429):
            proxy = request.meta.get("proxy", "direct")
            logger.warning(f"Ban détecté ({response.status}) sur proxy: {proxy}")
        return response

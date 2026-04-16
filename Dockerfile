FROM python:3.11-slim

# ── Dépendances système pour Playwright ──────────────────────────────────────
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    ca-certificates \
    libnss3 \
    libatk-bridge2.0-0 \
    libdrm2 \
    libxkbcommon0 \
    libgbm1 \
    libasound2 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libpango-1.0-0 \
    libcairo2 \
    && rm -rf /var/lib/apt/lists/*

# ── Répertoire de travail ──────────────────────────────────────────────────────
WORKDIR /app

# ── Installation des dépendances Python ──────────────────────────────────────
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Installation Playwright (Chromium uniquement) ─────────────────────────────
RUN playwright install chromium && playwright install-deps chromium

# ── Copie du code source ──────────────────────────────────────────────────────
COPY . .
RUN pip install -e .

# ── Répertoire de données (volume mount point) ────────────────────────────────
RUN mkdir -p /app/data

# ── Utilisateur non-root pour la sécurité ─────────────────────────────────────
RUN useradd -m -u 1000 scraper && chown -R scraper:scraper /app
USER scraper

# ── Point d'entrée ────────────────────────────────────────────────────────────
ENTRYPOINT ["pj-scraper"]
CMD ["--help"]

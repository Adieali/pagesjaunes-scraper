#!/usr/bin/env python3
"""
CLI — Pages Jaunes Pro Scraper

Usage:
  pj-scraper scrape --what "restaurant" --where "Lyon" --pages 10
  pj-scraper scrape --what "plombier" --where "Marseille" --pages 5 --no-playwright
  pj-scraper export --db data/pagesjaunes.db --format csv
  pj-scraper stats --db data/pagesjaunes.db
"""

import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import click
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings


@click.group()
@click.version_option("1.0.0", prog_name="pj-scraper")
def cli():
    """Pages Jaunes Pro Scraper — Collecte de données B2B publiques conformes RGPD."""
    pass


# ── Commande : scrape ──────────────────────────────────────────────────────────

@cli.command()
@click.option(
    "--what", "-w",
    required=True,
    help='Secteur/métier à rechercher (ex: "restaurant", "plombier")',
)
@click.option(
    "--where", "-l",
    required=True,
    help='Zone géographique (ex: "Paris", "Lyon", "75001")',
)
@click.option(
    "--pages", "-p",
    default=5,
    show_default=True,
    type=int,
    help="Nombre maximum de pages de résultats à parcourir",
)
@click.option(
    "--output-dir", "-o",
    default="data",
    show_default=True,
    help="Répertoire de sortie pour CSV/JSON/SQLite",
)
@click.option(
    "--delay",
    default=2.0,
    show_default=True,
    type=float,
    help="Délai minimum entre requêtes (secondes)",
)
@click.option(
    "--playwright/--no-playwright",
    default=True,
    show_default=True,
    help="Activer/désactiver le rendu JavaScript (Playwright)",
)
@click.option(
    "--proxy-file",
    default=None,
    type=click.Path(exists=False),
    help="Chemin vers le fichier de proxies YAML",
)
@click.option(
    "--verbose", "-v",
    is_flag=True,
    help="Afficher les logs détaillés",
)
def scrape(what, where, pages, output_dir, delay, playwright, proxy_file, verbose):
    """
    Lance le scraping de Pages Jaunes pour un secteur et une zone donnés.

    \b
    Exemples:
      pj-scraper scrape --what "restaurant" --where "Paris" --pages 10
      pj-scraper scrape --what "dentiste" --where "Lyon" --pages 3 --delay 3.0
      pj-scraper scrape --what "hotel" --where "Marseille" --no-playwright
    """
    click.echo(
        click.style(
            f"\n🕷  Pages Jaunes Pro Scraper\n"
            f"   Secteur   : {what}\n"
            f"   Zone      : {where}\n"
            f"   Pages max : {pages}\n"
            f"   Sortie    : {output_dir}/\n",
            fg="cyan",
        )
    )

    # Configuration Scrapy
    os.environ["SCRAPY_SETTINGS_MODULE"] = "pagesjaunes.settings"
    settings = get_project_settings()
    settings.update(
        {
            "DOWNLOAD_DELAY": delay,
            "OUTPUT_DIR": output_dir,
            "SQLITE_DB_PATH": str(Path(output_dir) / "pagesjaunes.db"),
            "LOG_LEVEL": "DEBUG" if verbose else "INFO",
        }
    )

    if not playwright:
        settings.update(
            {
                "DOWNLOAD_HANDLERS": {},
                "DOWNLOADER_MIDDLEWARES": {
                    "scrapy.downloadermiddlewares.useragent.UserAgentMiddleware": None,
                    "pagesjaunes.middlewares.RandomUserAgentMiddleware": 400,
                    "pagesjaunes.middlewares.ProxyRotationMiddleware": 410,
                    "pagesjaunes.middlewares.RetryOnBanMiddleware": 420,
                },
            }
        )
        click.echo(click.style("  ⚠  Mode sans Playwright (JS désactivé)", fg="yellow"))

    if proxy_file:
        os.environ["PROXY_FILE"] = proxy_file
        settings["PROXY_ENABLED"] = True

    # Lancement du crawler
    process = CrawlerProcess(settings)
    process.crawl(
        "pagesjaunes",
        what=what,
        where=where,
        max_pages=pages,
    )
    process.start()

    click.echo(
        click.style(
            f"\n✅  Scraping terminé. Données sauvegardées dans {output_dir}/",
            fg="green",
        )
    )


# ── Commande : export ──────────────────────────────────────────────────────────

@cli.command()
@click.option(
    "--db",
    default="data/pagesjaunes.db",
    show_default=True,
    type=click.Path(exists=True),
    help="Chemin vers la base SQLite",
)
@click.option(
    "--format", "fmt",
    type=click.Choice(["csv", "json", "jsonl"], case_sensitive=False),
    default="csv",
    show_default=True,
    help="Format d'export",
)
@click.option(
    "--output", "-o",
    default=None,
    help="Fichier de sortie (auto-généré si non spécifié)",
)
@click.option(
    "--city",
    default=None,
    help="Filtrer par ville",
)
@click.option(
    "--category",
    default=None,
    help="Filtrer par catégorie",
)
@click.option(
    "--min-rating",
    default=None,
    type=float,
    help="Note minimale (ex: 4.0)",
)
def export(db, fmt, output, city, category, min_rating):
    """
    Exporte les données depuis la base SQLite vers CSV ou JSON.

    \b
    Exemples:
      pj-scraper export --db data/pagesjaunes.db --format json
      pj-scraper export --db data/pagesjaunes.db --city Lyon --min-rating 4.0
    """
    import csv as csvmod
    from datetime import datetime

    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row

    query = "SELECT * FROM businesses WHERE 1=1"
    params = []
    if city:
        query += " AND address_city LIKE ?"
        params.append(f"%{city}%")
    if category:
        query += " AND category LIKE ?"
        params.append(f"%{category}%")
    if min_rating:
        query += " AND rating >= ?"
        params.append(min_rating)

    rows = conn.execute(query, params).fetchall()
    conn.close()

    if not rows:
        click.echo(click.style("Aucune donnée trouvée avec ces filtres.", fg="yellow"))
        return

    # Nom de fichier auto
    if not output:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output = f"data/export_{ts}.{fmt if fmt != 'jsonl' else 'jsonl'}"

    Path(output).parent.mkdir(parents=True, exist_ok=True)
    data = [dict(row) for row in rows]

    if fmt == "csv":
        with open(output, "w", newline="", encoding="utf-8-sig") as f:
            writer = csvmod.DictWriter(f, fieldnames=data[0].keys())
            writer.writeheader()
            writer.writerows(data)
    elif fmt == "json":
        with open(output, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    elif fmt == "jsonl":
        with open(output, "w", encoding="utf-8") as f:
            for row in data:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

    click.echo(
        click.style(
            f"✅  {len(data)} enregistrements exportés → {output}", fg="green"
        )
    )


# ── Commande : stats ───────────────────────────────────────────────────────────

@cli.command()
@click.option(
    "--db",
    default="data/pagesjaunes.db",
    show_default=True,
    type=click.Path(exists=True),
    help="Chemin vers la base SQLite",
)
def stats(db):
    """Affiche les statistiques de la base de données collectée."""
    conn = sqlite3.connect(db)

    total = conn.execute("SELECT COUNT(*) FROM businesses").fetchone()[0]
    with_phone = conn.execute(
        "SELECT COUNT(*) FROM businesses WHERE phone IS NOT NULL AND phone != ''"
    ).fetchone()[0]
    with_website = conn.execute(
        "SELECT COUNT(*) FROM businesses WHERE website IS NOT NULL AND website != ''"
    ).fetchone()[0]
    with_rating = conn.execute(
        "SELECT COUNT(*) FROM businesses WHERE rating IS NOT NULL"
    ).fetchone()[0]
    avg_rating = conn.execute(
        "SELECT AVG(rating) FROM businesses WHERE rating IS NOT NULL"
    ).fetchone()[0]

    top_cities = conn.execute(
        "SELECT address_city, COUNT(*) as n FROM businesses "
        "GROUP BY address_city ORDER BY n DESC LIMIT 5"
    ).fetchall()

    top_cats = conn.execute(
        "SELECT category, COUNT(*) as n FROM businesses "
        "GROUP BY category ORDER BY n DESC LIMIT 5"
    ).fetchall()

    conn.close()

    click.echo(click.style("\n📊  Statistiques de la base\n" + "─" * 40, fg="cyan"))
    click.echo(f"  Total établissements    : {total:,}")
    click.echo(f"  Avec téléphone          : {with_phone:,} ({with_phone/total*100:.1f}%)" if total else "")
    click.echo(f"  Avec site web           : {with_website:,} ({with_website/total*100:.1f}%)" if total else "")
    click.echo(f"  Avec note               : {with_rating:,} ({with_rating/total*100:.1f}%)" if total else "")
    click.echo(f"  Note moyenne            : {avg_rating:.2f}/5" if avg_rating else "  Note moyenne            : N/A")

    if top_cities:
        click.echo(click.style("\n  Top 5 villes :", fg="yellow"))
        for city, n in top_cities:
            click.echo(f"    {city or 'N/A':<25} {n:>6} établissements")

    if top_cats:
        click.echo(click.style("\n  Top 5 catégories :", fg="yellow"))
        for cat, n in top_cats:
            click.echo(f"    {cat or 'N/A':<25} {n:>6} établissements")

    click.echo("")


if __name__ == "__main__":
    cli()

from setuptools import setup, find_packages

setup(
    name="pagesjaunes-pro-scraper",
    version="1.0.0",
    description="Scraper professionnel pour données B2B publiques Pages Jaunes (RGPD-compliant)",
    author="Adie A.",
    python_requires=">=3.11",
    packages=find_packages(),
    install_requires=[
        "Scrapy>=2.11.0",
        "scrapy-playwright>=0.0.33",
        "click>=8.1.7",
        "itemadapter>=0.9.0",
        "PyYAML>=6.0.1",
        "python-dotenv>=1.0.0",
    ],
    entry_points={
        "console_scripts": [
            "pj-scraper=cli.main:cli",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3.11",
        "License :: OSI Approved :: MIT License",
        "Topic :: Internet :: WWW/HTTP :: Indexing/Search",
    ],
)

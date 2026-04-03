# app/rss_parser.py
import asyncio
import feedparser
import logging
import time
from datetime import datetime, timezone
from typing import List, Dict, Optional, Tuple
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)

RSS_FEEDS = {
    "россия": [
        "https://ria.ru/export/rss2/archive/index.xml",
        "https://www.interfax.ru/rss.asp",
        "https://tass.ru/rss/v2.xml"
    ],
    "мир": [
        "https://tass.ru/rss/v2.xml",
        "https://www.interfax.ru/rss.asp"
    ],
    "экономика": [
        "https://www.kommersant.ru/RSS/section-economics.xml",
        "https://www.finam.ru/net/analysis/conews/rsspoint",
        "https://www.vedomosti.ru/rss/rubric/economics"
    ],
    "наука": [
        "https://nplus1.ru/rss",
        "https://elementy.ru/rss/news",
        "https://scientificrussia.ru/rss"
    ],
    "спорт": [
        "https://rsport.ria.ru/export/rss2/index.xml",
        "https://www.sport-express.ru/services/materials/news/se/",
        "https://tass.ru/rss/v2.xml"
    ],
    "культура": [
        "https://www.kommersant.ru/RSS/section-culture.xml",
        "https://snob.ru/rss"
    ]
}

REQUEST_TIMEOUT = 10.0
MAX_CONCURRENT_REQUESTS = 10
MAX_ARTICLES_PER_SOURCE = 30


async def fetch_rss_feed(client: httpx.AsyncClient, url: str) -> Optional[str]:
    try:
        response = await client.get(url, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        return response.text
    except Exception as e:
        logger.warning(f"RSS error {url}: {e}")
        return None


def parse_rss_content(xml: str, source_url: str, category: str) -> List[Dict]:
    feed = feedparser.parse(xml)

    items = []
    for entry in feed.entries[:MAX_ARTICLES_PER_SOURCE]:
        try:
            image_url = ""

            if hasattr(entry, "media_content") and entry.media_content:
                image_url = entry.media_content[0].get("url", "")
            elif hasattr(entry, "links"):
                for link in entry.links:
                    if link.get("type", "").startswith("image/"):
                        image_url = link.get("href", "")
                        break

            if hasattr(entry, "published_parsed") and entry.published_parsed:
                published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
            elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
                published = datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc)
            else:
                published = datetime.now(timezone.utc)
 
            items.append({
                "url": entry.link,
                "title": entry.title.strip() if entry.title else "",
                "description": getattr(entry, "summary", ""),
                "image_url": image_url,
                "source_name": extract_source_name(source_url) or "Lenta.ru",
                "published_at": published,
                "category": category
            })
        except Exception:
            continue

    return items


def extract_source_name(url: str) -> str:
    domain = urlparse(url).netloc.lower()
    domain = domain.replace("www.", "").replace("m.", "")

    source_map = {
        "ria.ru": "РИА Новости",
        "tass.ru": "ТАСС",
        "interfax.ru": "Интерфакс",
        "kommersant.ru": "Коммерсантъ",
        "nplus1.ru": "N+1",
        "elementy.ru": "Элементы",
        "sport-express.ru": "Спорт-Экспресс",
        "lenta.ru": "Lenta.ru",
        "vedomosti.ru": "Ведомости",
        "finam.ru": "Финам",
        "snob.ru": "Snob",
        "scientificrussia.ru": "Научная Россия",
        "rsport.ria.ru": "РИА Новости Спорт",
        "rbc.ru": "РБК",
        "iz.ru": "Известия",
        "mk.ru": "Московский комсомолец",
        "kp.ru": "Комсомольская правда",
        "aif.ru": "Аргументы и факты",
        "rg.ru": "Российская газета",
    }
    
    if domain in source_map:
        return source_map[domain]
    
    for key, name in source_map.items():
        if key in domain:
            return name
    
    parts = domain.split('.')
    if len(parts) >= 2:
        main_part = parts[-2]
        if main_part and len(main_part) > 2:
            return main_part.capitalize()
    
    return domain if domain else "Lenta.ru"


async def parse_category_async(category: str, urls: List[str], client: httpx.AsyncClient):
    semaphore = asyncio.Semaphore(5)

    async def fetch(url):
        async with semaphore:
            return url, await fetch_rss_feed(client, url)

    tasks = [fetch(url) for url in urls]
    results = await asyncio.gather(*tasks)

    all_news = []

    for url, xml in results:
        if not xml:
            continue
        items = parse_rss_content(xml, url, category)
        all_news.extend(items)

    seen = set()
    unique = []

    for item in all_news:
        if item["url"] not in seen:
            seen.add(item["url"])
            unique.append(item)

    unique.sort(key=lambda x: x["published_at"], reverse=True)

    return unique


async def update_category_async(db_session, category: str) -> Dict:
    start = time.time()

    async with httpx.AsyncClient(
        timeout=REQUEST_TIMEOUT,
        limits=httpx.Limits(max_keepalive_connections=MAX_CONCURRENT_REQUESTS)
    ) as client:
        news_items = await parse_category_async(
            category,
            RSS_FEEDS[category],
            client
        )

    from app import crud, schemas

    saved = 0
    errors = 0

    try:
        for item in news_items:
            try:
                news = schemas.NewsCreate(**item)
                await asyncio.to_thread(crud.create_or_update_news, db_session, news)
                saved += 1
            except Exception:
                errors += 1
    finally:
        db_session.close()

    return {
        "category": category,
        "parsed": len(news_items),
        "saved": saved,
        "errors": errors,
        "duration_ms": int((time.time() - start) * 1000)
    }


async def update_all_categories_async(db_session) -> Dict:
    from app.database import SessionLocal

    start = time.time()

    tasks = [
        update_category_async(SessionLocal(), category)
        for category in RSS_FEEDS.keys()
    ]

    results = await asyncio.gather(*tasks)

    total_parsed = sum(r["parsed"] for r in results)
    total_saved = sum(r["saved"] for r in results)
    total_errors = sum(r["errors"] for r in results)

    return {
        "status": "completed",
        "results": {r["category"]: r for r in results},
        "total_parsed": total_parsed,
        "total_saved": total_saved,
        "total_errors": total_errors,
        "duration_ms": int((time.time() - start) * 1000)
    }
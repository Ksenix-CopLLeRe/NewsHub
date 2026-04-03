# app/rss_parser.py
import asyncio
import feedparser
import logging
import time
from datetime import datetime, timezone
from typing import List, Dict, Optional, Tuple
import re
from urllib.parse import urlparse
from urllib.parse import urljoin

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
        response = await client.get(
            url,
            timeout=REQUEST_TIMEOUT,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (NewsHub; RSS fetcher)",
                "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml;q=0.9, */*;q=0.8",
            },
        )
        response.raise_for_status()
        return response.text
    except Exception as e:
        logger.warning(f"RSS error {url}: {e}")
        return None


_IMG_SRC_RE = re.compile(r"""<img[^>]+src=["']([^"']+)["']""", re.IGNORECASE)
_META_OG_IMAGE_RE = re.compile(
    r"""<meta[^>]+(?:property|name)=["'](?:og:image|twitter:image|twitter:image:src)["'][^>]+content=["']([^"']+)["']""",
    re.IGNORECASE,
)


def _extract_image_url(entry) -> str:
    """
    Пытаемся извлечь URL картинки из разных распространённых полей RSS/Atom.
    Возвращает пустую строку, если картинку определить не удалось.
    """
    # 1) media:content
    if hasattr(entry, "media_content") and entry.media_content:
        url = (entry.media_content[0] or {}).get("url") or ""
        if url:
            return url

    # 2) media:thumbnail
    if hasattr(entry, "media_thumbnail") and entry.media_thumbnail:
        url = (entry.media_thumbnail[0] or {}).get("url") or ""
        if url:
            return url

    # 3) enclosure / links rel=enclosure / type=image/*
    if hasattr(entry, "links"):
        for link in entry.links or []:
            href = (link or {}).get("href") or ""
            if not href:
                continue
            rel = ((link or {}).get("rel") or "").lower()
            link_type = ((link or {}).get("type") or "").lower()
            if rel == "enclosure" and link_type.startswith("image/"):
                return href
            if link_type.startswith("image/"):
                return href

    # 4) enclosures (у feedparser бывает entry.enclosures)
    if hasattr(entry, "enclosures") and entry.enclosures:
        for enc in entry.enclosures or []:
            href = (enc or {}).get("href") or (enc or {}).get("url") or ""
            if href:
                return href

    # 5) img внутри summary/description (часто у RSS так)
    summary = getattr(entry, "summary", "") or getattr(entry, "description", "") or ""
    if summary:
        m = _IMG_SRC_RE.search(summary)
        if m:
            return m.group(1).strip()

    return ""


async def _fetch_meta_image(client: httpx.AsyncClient, page_url: str) -> str:
    """Fallback: достать картинку со страницы (og:image / twitter:image)."""
    try:
        r = await client.get(page_url, timeout=5.0, follow_redirects=True)
        if r.status_code != 200:
            return ""
        html = r.text or ""
    except Exception:
        return ""

    m = _META_OG_IMAGE_RE.search(html)
    if not m:
        return ""
    img = m.group(1).strip()
    if not img:
        return ""
    # нормализуем protocol-relative и относительные ссылки
    if img.startswith("//"):
        base = urlparse(str(r.url))
        return f"{base.scheme}:{img}"
    return urljoin(str(r.url), img)


async def _enrich_images(items: List[Dict], client: httpx.AsyncClient) -> None:
    """
    Универсальный fallback для RSS без картинок:
    для небольшого числа свежих items подтягивает og:image со страницы статьи.
    """
    missing = [it for it in items if not (it.get("image_url") or "").strip()]
    if not missing:
        return

    # ограничиваем, чтобы не убивать производительность
    missing = missing[:25]

    sem = asyncio.Semaphore(8)

    async def one(it: Dict):
        url = (it.get("url") or "").strip()
        if not url:
            return
        async with sem:
            img = await _fetch_meta_image(client, url)
        if img:
            it["image_url"] = img

    await asyncio.gather(*(one(it) for it in missing))


def parse_rss_content(xml: str, source_url: str, category: str) -> List[Dict]:
    feed = feedparser.parse(xml)

    items = []
    for entry in feed.entries[:MAX_ARTICLES_PER_SOURCE]:
        try:
            image_url = _extract_image_url(entry)
            if image_url and hasattr(entry, "link") and entry.link:
                # На случай относительных ссылок в RSS
                image_url = urljoin(entry.link, image_url)

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
        # Если RSS не содержит картинок — пробуем получить их со страницы статьи
        await _enrich_images(items, client)
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
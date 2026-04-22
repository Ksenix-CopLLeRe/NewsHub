from datetime import datetime, timezone
from types import SimpleNamespace

import httpx
import pytest
import respx
from sqlalchemy.orm import sessionmaker

from app import models
from app.rss_parser import (
    RSS_FEEDS,
    _extract_image_url,
    extract_source_name,
    parse_rss_content,
    update_category_async,
)


MOCK_RSS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:media="http://search.yahoo.com/mrss/">
  <channel>
    <title>Test Feed</title>
    <link>https://ria.ru</link>
    <item>
      <title>Test Article One</title>
      <link>https://ria.ru/20260421/test-1.html</link>
      <description>Test description one</description>
      <pubDate>Mon, 21 Apr 2026 10:00:00 +0000</pubDate>
      <media:content url="https://ria.ru/images/test1.jpg" medium="image" width="640" height="480"/>
    </item>
    <item>
      <title>Test Article Two</title>
      <link>https://ria.ru/20260421/test-2.html</link>
      <description>Test description two</description>
      <pubDate>Mon, 21 Apr 2026 11:00:00 +0000</pubDate>
      <media:content url="https://ria.ru/images/test2.jpg" medium="image" width="640" height="480"/>
    </item>
  </channel>
</rss>"""


# ---------- parse_rss_content ----------

def test_parse_rss_content_returns_items():
    items = parse_rss_content(MOCK_RSS_XML, "https://ria.ru/export/rss2/archive/index.xml", "россия")
    assert len(items) == 2


def test_parse_rss_content_fields():
    items = parse_rss_content(MOCK_RSS_XML, "https://ria.ru/export/rss2/archive/index.xml", "россия")
    item = next(i for i in items if i["title"] == "Test Article One")
    assert item["url"] == "https://ria.ru/20260421/test-1.html"
    assert item["category"] == "россия"
    assert item["image_url"] == "https://ria.ru/images/test1.jpg"
    assert item["source_name"] == "РИА Новости"
    assert isinstance(item["published_at"], datetime)


def test_parse_rss_content_empty_feed():
    xml = '<?xml version="1.0"?><rss version="2.0"><channel><title>Empty</title></channel></rss>'
    items = parse_rss_content(xml, "https://example.com/rss", "россия")
    assert items == []


def test_parse_rss_content_preserves_feed_order():
    # parse_rss_content returns items in feed order (sorting happens in parse_category_async)
    items = parse_rss_content(MOCK_RSS_XML, "https://ria.ru/export/rss2/archive/index.xml", "россия")
    assert items[0]["title"] == "Test Article One"
    assert items[1]["title"] == "Test Article Two"


# ---------- _extract_image_url ----------

def test_extract_image_from_media_content():
    entry = SimpleNamespace(
        media_content=[{"url": "https://example.com/image.jpg"}],
        links=[],
        enclosures=[],
        summary="",
    )
    assert _extract_image_url(entry) == "https://example.com/image.jpg"


def test_extract_image_from_media_thumbnail():
    entry = SimpleNamespace(
        media_thumbnail=[{"url": "https://example.com/thumb.jpg"}],
        links=[],
        enclosures=[],
        summary="",
    )
    assert _extract_image_url(entry) == "https://example.com/thumb.jpg"


def test_extract_image_from_enclosure_link():
    entry = SimpleNamespace(
        links=[{"href": "https://example.com/photo.jpg", "rel": "enclosure", "type": "image/jpeg"}],
        enclosures=[],
        summary="",
    )
    assert _extract_image_url(entry) == "https://example.com/photo.jpg"


def test_extract_image_from_img_tag_in_summary():
    entry = SimpleNamespace(
        links=[],
        enclosures=[],
        summary='<p><img src="https://example.com/inline.jpg" alt="photo"/></p>',
    )
    assert _extract_image_url(entry) == "https://example.com/inline.jpg"


def test_extract_image_prefers_media_content_over_summary():
    entry = SimpleNamespace(
        media_content=[{"url": "https://example.com/media.jpg"}],
        links=[],
        enclosures=[],
        summary='<img src="https://example.com/summary.jpg"/>',
    )
    assert _extract_image_url(entry) == "https://example.com/media.jpg"


def test_extract_image_returns_empty_when_no_image():
    entry = SimpleNamespace(
        links=[],
        enclosures=[],
        summary="No images here, just plain text.",
    )
    assert _extract_image_url(entry) == ""


# ---------- extract_source_name ----------

@pytest.mark.parametrize("url,expected", [
    ("https://ria.ru/export/rss2/archive/index.xml", "РИА Новости"),
    ("https://tass.ru/rss/v2.xml", "ТАСС"),
    ("https://www.interfax.ru/rss.asp", "Интерфакс"),
    ("https://www.kommersant.ru/RSS/section-economics.xml", "Коммерсантъ"),
    ("https://nplus1.ru/rss", "N+1"),
    ("https://www.sport-express.ru/rss", "Спорт-Экспресс"),
])
def test_extract_source_name_known_domains(url, expected):
    assert extract_source_name(url) == expected


def test_extract_source_name_unknown_domain_uses_domain_part():
    result = extract_source_name("https://mynewssite.org/feed")
    assert result == "Mynewssite"


def test_extract_source_name_empty_url_returns_default():
    result = extract_source_name("")
    assert result == "Lenta.ru"


# ---------- update_category_async (integration with real DB + mocked HTTP) ----------

async def test_update_category_saves_news_to_db(test_engine):
    TestSession = sessionmaker(bind=test_engine)
    session = TestSession()

    async with respx.mock:
        for url in RSS_FEEDS["россия"]:
            respx.get(url).mock(return_value=httpx.Response(200, text=MOCK_RSS_XML))

        result = await update_category_async(session, "россия")
        # update_category_async closes the session itself

    assert result["category"] == "россия"
    assert result["parsed"] > 0
    assert result["saved"] > 0
    assert result["errors"] == 0

    verify = TestSession()
    try:
        items = verify.query(models.NewsItem).filter_by(category="россия").all()
        assert len(items) > 0
        titles = [item.title for item in items]
        assert "Test Article One" in titles
        assert "Test Article Two" in titles
    finally:
        verify.close()


async def test_update_category_deduplicates_across_sources(test_engine):
    # All 3 sources for "россия" return the same articles — after dedup only 2 unique items saved
    TestSession = sessionmaker(bind=test_engine)
    session = TestSession()

    async with respx.mock:
        for url in RSS_FEEDS["россия"]:
            respx.get(url).mock(return_value=httpx.Response(200, text=MOCK_RSS_XML))

        result = await update_category_async(session, "россия")

    assert result["parsed"] == 2  # 2 unique URLs across all sources
    assert result["saved"] == 2


async def test_update_category_handles_failed_source(test_engine):
    TestSession = sessionmaker(bind=test_engine)
    session = TestSession()

    urls = RSS_FEEDS["россия"]

    async with respx.mock:
        # First source fails, others succeed
        respx.get(urls[0]).mock(side_effect=httpx.ConnectError("timeout"))
        for url in urls[1:]:
            respx.get(url).mock(return_value=httpx.Response(200, text=MOCK_RSS_XML))

        result = await update_category_async(session, "россия")

    # Should still save items from the successful sources
    assert result["saved"] > 0

"""FR-02 — 5개 필드가 누락 없이 추출되는지 + E-02 파싱 실패 처리."""

import unittest
from pathlib import Path

import _path  # noqa: F401
import rss

FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "sample_rss.xml"

ATOM_SAMPLE = """<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>Atom 기사 제목</title>
    <link rel="alternate" href="https://example.com/atom-1"/>
    <id>urn:uuid:atom-1</id>
    <published>2026-07-27T08:30:00+09:00</published>
    <summary>본문 요약</summary>
  </entry>
</feed>""".encode("utf-8")


class TestParse(unittest.TestCase):
    def test_rss2_fields_extracted(self):
        items = rss.parse(FIXTURE.read_bytes(), source="fixture")
        self.assertEqual(len(items), 6)
        first = items[0]
        for field in ("title", "link", "pub_date", "description", "guid"):
            self.assertIn(field, first)
        self.assertEqual(first["source"], "fixture")

    def test_html_stripped_from_description(self):
        items = rss.parse(FIXTURE.read_bytes())
        agent = next(i for i in items if "에이전트" in i["title"])
        self.assertNotIn("<", agent["description"])
        self.assertIn("LLM", agent["description"])

    def test_atom_link_from_href(self):
        items = rss.parse(ATOM_SAMPLE)
        self.assertEqual(items[0]["link"], "https://example.com/atom-1")
        self.assertEqual(items[0]["guid"], "urn:uuid:atom-1")
        self.assertEqual(items[0]["pub_date"], "2026-07-27T08:30:00+09:00")

    def test_limit_respected(self):
        self.assertEqual(len(rss.parse(FIXTURE.read_bytes(), limit=2)), 2)

    def test_broken_xml_raises_e02(self):
        with self.assertRaises(rss.FeedError) as ctx:
            rss.parse(b"<rss><channel><item></rss>")
        self.assertEqual(ctx.exception.code, "E-02")

    def test_feed_without_items_raises_e02(self):
        with self.assertRaises(rss.FeedError) as ctx:
            rss.parse(b"<rss version='2.0'><channel><title>t</title></channel></rss>")
        self.assertEqual(ctx.exception.code, "E-02")

    def test_missing_guid_yields_empty_string_not_error(self):
        items = rss.parse(FIXTURE.read_bytes())
        cloud = next(i for i in items if "클라우드" in i["title"])
        self.assertEqual(cloud["guid"], "")


if __name__ == "__main__":
    unittest.main()

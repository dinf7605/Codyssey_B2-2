"""R1 — 날짜 포맷 변환. PRD가 지목한 최우선 검증 지점."""

import unittest

import _path  # noqa: F401
from date_utils import parse_pubdate, to_notion_iso


class TestToNotionIso(unittest.TestCase):
    def test_rfc822_kst(self):
        # RSS 2.0 표준. 국내 피드 대부분이 이 형태다.
        self.assertEqual(
            to_notion_iso("Mon, 27 Jul 2026 08:30:00 +0900"),
            "2026-07-27T08:30:00+09:00",
        )

    def test_etnews_actual_pubdate(self):
        # 1순위 피드(전자신문 Section901)에서 실제로 받은 값. 2026-07-29 확인.
        # 새 피드를 추가하면 그 피드의 실제 샘플을 여기에 먼저 넣는다.
        self.assertEqual(
            to_notion_iso("Wed, 29 Jul 2026 11:25:06 +0900"),
            "2026-07-29T11:25:06+09:00",
        )

    def test_google_news_actual_pubdate(self):
        # 백업 피드는 GMT로 준다. 9시간 밀리면 전날로 저장되므로 반드시 확인한다.
        self.assertEqual(
            to_notion_iso("Wed, 29 Jul 2026 02:02:00 GMT"),
            "2026-07-29T11:02:00+09:00",
        )

    def test_rfc822_gmt_converted_to_kst(self):
        # Google News는 GMT로 준다. KST로 바꿔야 날짜가 하루 밀리지 않는다.
        self.assertEqual(
            to_notion_iso("Sun, 26 Jul 2026 23:10:00 GMT"),
            "2026-07-27T08:10:00+09:00",
        )

    def test_iso8601_passthrough(self):
        self.assertEqual(
            to_notion_iso("2026-07-27T08:30:00+09:00"), "2026-07-27T08:30:00+09:00"
        )

    def test_iso8601_zulu(self):
        self.assertEqual(
            to_notion_iso("2026-07-26T23:10:00Z"), "2026-07-27T08:10:00+09:00"
        )

    def test_naive_datetime_treated_as_kst(self):
        self.assertEqual(
            to_notion_iso("2026-07-27 08:30:00"), "2026-07-27T08:30:00+09:00"
        )

    def test_date_only(self):
        self.assertEqual(to_notion_iso("2026-07-27"), "2026-07-27T00:00:00+09:00")

    def test_unparseable_returns_none_not_exception(self):
        # E-08. 예외를 던지면 시나리오 전체가 죽는다. None이어야 부분 저장이 된다.
        for bad in ["어제 오후 3시", "", None, "not a date", "2026/13/45"]:
            with self.subTest(bad=bad):
                self.assertIsNone(to_notion_iso(bad))

    def test_parse_pubdate_is_timezone_aware(self):
        dt = parse_pubdate("Mon, 27 Jul 2026 08:30:00 +0900")
        self.assertIsNotNone(dt.tzinfo)


if __name__ == "__main__":
    unittest.main()

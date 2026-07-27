"""FR-04 — 중복방지키가 '같은 기사면 같은 값'을 유지하는지 검증."""

import unittest

import _path  # noqa: F401
from dedupe import dedupe_key, normalize_link


class TestDedupeKey(unittest.TestCase):
    def test_guid_takes_priority(self):
        key = dedupe_key({"guid": "abc-123", "link": "https://example.com/a"})
        self.assertEqual(key, "abc-123")

    def test_link_hash_when_guid_missing(self):
        key = dedupe_key({"guid": "", "link": "https://example.com/a"})
        self.assertEqual(len(key), 16)
        self.assertNotEqual(key, "")

    def test_tracking_params_do_not_change_key(self):
        # 같은 기사에 utm이 붙었다고 새 기사로 저장되면 매일 중복이 쌓인다.
        plain = dedupe_key({"link": "https://example.com/a"})
        tagged = dedupe_key({"link": "https://example.com/a?utm_source=rss&fbclid=xyz"})
        self.assertEqual(plain, tagged)

    def test_trailing_slash_and_case_normalized(self):
        self.assertEqual(
            dedupe_key({"link": "https://Example.com/a/"}),
            dedupe_key({"link": "https://example.com/a"}),
        )

    def test_meaningful_query_preserved(self):
        # 기사 식별에 쓰이는 파라미터까지 지우면 서로 다른 기사가 같은 키가 된다.
        self.assertNotEqual(
            dedupe_key({"link": "https://example.com/view?id=1"}),
            dedupe_key({"link": "https://example.com/view?id=2"}),
        )

    def test_empty_article_yields_empty_key(self):
        self.assertEqual(dedupe_key({}), "")

    def test_normalize_link_strips_utm(self):
        self.assertEqual(
            normalize_link("https://example.com/a?utm_medium=feed"),
            "https://example.com/a",
        )


if __name__ == "__main__":
    unittest.main()

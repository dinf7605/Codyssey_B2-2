"""FR-03 — 필터 결과가 항상 0건 또는 1건으로 확정되는지 검증."""

import unittest

import _path  # noqa: F401
import article_filter


def article(title, description="", pub_date="Mon, 27 Jul 2026 08:00:00 +0900"):
    return {
        "title": title,
        "description": description,
        "pub_date": pub_date,
        "link": "https://example.com/x",
        "guid": "",
    }


class TestSelect(unittest.TestCase):
    def test_tier1_matches_title_only(self):
        chosen, reason = article_filter.select(
            [article("생성형 AI 에이전트 확산"), article("일반 산업 뉴스")]
        )
        self.assertEqual(reason["tier"], 1)
        self.assertIn("AI", reason["matched"])
        self.assertEqual(chosen["title"], "생성형 AI 에이전트 확산")

    def test_tier1_ignores_body_match(self):
        # 본문에만 1순위 키워드가 있으면 1순위로 잡히면 안 된다.
        chosen, reason = article_filter.select(
            [article("평범한 제목", description="본문에 인공지능 언급")]
        )
        self.assertIsNone(chosen)
        self.assertIsNone(reason["tier"])

    def test_tier2_fallback_uses_body(self):
        chosen, reason = article_filter.select(
            [article("공정 경쟁 가열", description="GPU 수요가 늘었다")]
        )
        self.assertEqual(reason["tier"], 2)
        self.assertEqual(chosen["title"], "공정 경쟁 가열")

    def test_tier2_not_used_when_tier1_exists(self):
        _, reason = article_filter.select(
            [article("반도체 공정 경쟁"), article("LLM 신모델 공개")]
        )
        self.assertEqual(reason["tier"], 1)

    def test_exclude_keyword_drops_candidate(self):
        chosen, reason = article_filter.select([article("[채용] AI 개발자 공채")])
        self.assertIsNone(chosen)
        self.assertEqual(reason["excluded"], 1)

    def test_latest_wins_among_candidates(self):
        chosen, _ = article_filter.select(
            [
                article("AI 뉴스 A", pub_date="Mon, 27 Jul 2026 07:00:00 +0900"),
                article("AI 뉴스 B", pub_date="Mon, 27 Jul 2026 09:00:00 +0900"),
                article("AI 뉴스 C", pub_date="Mon, 27 Jul 2026 08:00:00 +0900"),
            ]
        )
        self.assertEqual(chosen["title"], "AI 뉴스 B")

    def test_broken_date_sorts_last_but_still_selectable(self):
        chosen, _ = article_filter.select([article("AI 뉴스 X", pub_date="깨진 날짜")])
        self.assertEqual(chosen["title"], "AI 뉴스 X")

    def test_empty_pool_is_normal_skip(self):
        chosen, reason = article_filter.select([])
        self.assertIsNone(chosen)
        self.assertEqual(reason["candidates"], 0)

    def test_ai_does_not_match_inside_english_word(self):
        # 'said', 'again' 같은 단어에 'ai'가 들어 있어도 매칭되면 안 된다.
        chosen, _ = article_filter.select([article("Company said it will retain staff")])
        self.assertIsNone(chosen)

    def test_korean_keyword_matches_with_particle(self):
        # 조사가 붙어도 매칭돼야 한다.
        chosen, reason = article_filter.select([article("인공지능이 바꾼 업무 방식")])
        self.assertEqual(reason["tier"], 1)
        self.assertIsNotNone(chosen)

    def test_case_insensitive(self):
        _, reason = article_filter.select([article("chatgpt 신기능 공개")])
        self.assertEqual(reason["tier"], 1)


if __name__ == "__main__":
    unittest.main()

"""end-to-end 흐름 — 정상 스킵(E-03/E-04)이 '실패'로 취급되지 않는지 검증.

성공 기준 S1은 "7일 연속 실행 성공(또는 정상 스킵 로그)"이므로,
정상 스킵과 오류의 종료 코드가 반드시 구분돼야 한다.
"""

import io
import unittest
from contextlib import redirect_stdout
from pathlib import Path

import _path  # noqa: F401
import notion_store
import pipeline

FIXTURE = str(Path(__file__).resolve().parent.parent / "fixtures" / "sample_rss.xml")


def run(argv):
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        code = pipeline.main(argv)
    return code, buffer.getvalue()


class TestPipeline(unittest.TestCase):
    def test_dry_run_selects_latest_tier1_article(self):
        code, out = run(["--dry-run"])
        self.assertEqual(code, 0)
        self.assertIn("생성형 AI 에이전트", out)
        # 제외 키워드가 걸린 기사는 절대 선택되면 안 된다.
        self.assertNotIn("[채용]", out)
        self.assertNotIn("[프로모션]", out)

    def test_dry_run_makes_no_external_calls(self):
        _, out = run(["--dry-run"])
        self.assertIn("건너뜀", out)

    def test_no_match_is_normal_skip_not_error(self):
        empty = Path(_path.ROOT) / "fixtures" / "_no_match.xml"
        empty.write_text(
            "<rss version='2.0'><channel><item>"
            "<title>날씨 흐림</title><link>https://example.com/w</link>"
            "<pubDate>Mon, 27 Jul 2026 08:00:00 +0900</pubDate>"
            "<description>비가 온다</description></item></channel></rss>",
            encoding="utf-8",
        )
        self.addCleanup(empty.unlink)
        code, out = run(["--fixture", str(empty), "--no-ai", "--skip-notion"])
        self.assertEqual(code, 0)  # E-03은 실패가 아니다
        self.assertIn("정상 스킵", out)

    def test_duplicate_skips_before_ai_call(self):
        original = notion_store.exists
        notion_store.exists = lambda *a, **k: True
        self.addCleanup(lambda: setattr(notion_store, "exists", original))

        code, out = run(["--fixture", FIXTURE, "--database-id", "x", "--notion-token", "y"])
        self.assertEqual(code, 0)
        self.assertIn("AI 호출 안 함", out)  # FR-04 검사 위치가 AI보다 앞
        self.assertNotIn("5/요약", out)

    def test_feed_error_exits_nonzero(self):
        broken = Path(_path.ROOT) / "fixtures" / "_broken.xml"
        broken.write_text("<rss><item>", encoding="utf-8")
        self.addCleanup(broken.unlink)
        code, out = run(["--fixture", str(broken), "--no-ai", "--skip-notion"])
        self.assertEqual(code, 1)
        self.assertIn("E-02", out)

    def test_record_has_all_four_required_properties(self):
        _, out = run(["--dry-run"])
        for label in ("title", "summary", "link", "published_iso"):
            self.assertIn(label, out)


if __name__ == "__main__":
    unittest.main()

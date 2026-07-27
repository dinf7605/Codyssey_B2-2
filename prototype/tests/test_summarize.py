"""FR-05 / E-05 / E-06 / E-07 — 요약 후처리와 재시도 상한 검증.

Gemini를 실제로 부르지 않는다(R5: 테스트로 한도를 소모하지 않는다).
"""

import unittest

import _path  # noqa: F401
import summarize
from summarize import SUMMARY_FAILED, SummaryError, postprocess


class TestPostprocess(unittest.TestCase):
    def test_three_bullets_pass_through(self):
        raw = "- 첫째 줄\n- 둘째 줄\n- 셋째 줄"
        self.assertEqual(postprocess(raw).splitlines(), ["- 첫째 줄", "- 둘째 줄", "- 셋째 줄"])

    def test_more_than_three_lines_truncated(self):
        # E-07. 재호출하지 않고 앞 3줄만 남긴다.
        raw = "\n".join(f"- 줄 {i}" for i in range(1, 7))
        self.assertEqual(len(postprocess(raw).splitlines()), 3)

    def test_long_line_cut_to_60_chars(self):
        raw = "- " + "가" * 100
        line = postprocess(raw).splitlines()[0]
        self.assertEqual(len(line) - 2, 60)  # '- ' 접두사 제외

    def test_preamble_dropped(self):
        raw = "다음은 기사 요약입니다:\n- 실제 요약 1\n- 실제 요약 2"
        lines = postprocess(raw).splitlines()
        self.assertEqual(lines, ["- 실제 요약 1", "- 실제 요약 2"])

    def test_bullet_symbol_variants_normalized(self):
        raw = "• 첫째\n* 둘째"
        self.assertEqual(postprocess(raw).splitlines(), ["- 첫째", "- 둘째"])

    def test_blank_lines_ignored(self):
        raw = "\n\n- 하나\n\n- 둘\n"
        self.assertEqual(len(postprocess(raw).splitlines()), 2)

    def test_empty_response(self):
        self.assertEqual(postprocess(""), "")
        self.assertEqual(postprocess(None), "")


class TestRetryPolicy(unittest.TestCase):
    """NFR-04/05 — 호출 1회 원칙과 재시도 상한 2회."""

    def setUp(self):
        self.calls = []
        self.article = {"title": "t", "description": "c"}

    def _patch(self, behavior):
        self.original = summarize._call_gemini
        summarize._call_gemini = behavior
        self.addCleanup(lambda: setattr(summarize, "_call_gemini", self.original))

    def test_success_calls_api_exactly_once(self):
        def ok(prompt, key):
            self.calls.append(prompt)
            return "- 요약"

        self._patch(ok)
        result = summarize.summarize(self.article, api_key="fake", sleep=lambda s: None)
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(result, "- 요약")

    def test_429_retries_at_most_twice_then_gives_up(self):
        def always_429(prompt, key):
            self.calls.append(prompt)
            raise SummaryError("E-05", "429")

        self._patch(always_429)
        result = summarize.summarize(self.article, api_key="fake", sleep=lambda s: None)
        self.assertEqual(len(self.calls), 3)  # 최초 1 + 재시도 2
        self.assertEqual(result, SUMMARY_FAILED)  # 저장은 계속 진행된다

    def test_auth_error_does_not_retry(self):
        def auth_fail(prompt, key):
            self.calls.append(prompt)
            raise SummaryError("E-10", "403")

        self._patch(auth_fail)
        with self.assertRaises(SummaryError):
            summarize.summarize(self.article, api_key="fake", sleep=lambda s: None)
        self.assertEqual(len(self.calls), 1)  # E-10은 재시도 무의미

    def test_recovers_on_second_attempt(self):
        def flaky(prompt, key):
            self.calls.append(prompt)
            if len(self.calls) == 1:
                raise SummaryError("E-06", "일시 오류")
            return "- 성공"

        self._patch(flaky)
        result = summarize.summarize(self.article, api_key="fake", sleep=lambda s: None)
        self.assertEqual(result, "- 성공")
        self.assertEqual(len(self.calls), 2)


class TestPrompt(unittest.TestCase):
    def test_prompt_contains_article_fields(self):
        prompt = summarize.build_prompt({"title": "제목X", "description": "본문Y"})
        self.assertIn("제목X", prompt)
        self.assertIn("본문Y", prompt)

    def test_long_body_is_truncated(self):
        prompt = summarize.build_prompt({"title": "t", "description": "가" * 9000})
        self.assertLess(len(prompt), 5000)


if __name__ == "__main__":
    unittest.main()

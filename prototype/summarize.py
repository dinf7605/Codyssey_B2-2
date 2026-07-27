"""FR-05. Gemini 3줄 요약.

핵심 원칙 두 가지를 코드로 강제한다.
  - NFR-04: 기사 1건당 호출 1회. 이 모듈은 요약 결과가 마음에 안 들어도
    재호출하지 않는다. 3줄 초과는 후처리로 자른다(E-07).
  - NFR-05: 재시도는 통신 실패/429일 때만, 최대 2회.
"""

import json
import os
import time
import urllib.error
import urllib.request

from config import GEMINI_MODEL, HTTP_TIMEOUT, MAX_RETRY, SUMMARY_MAX_CHARS, SUMMARY_MAX_LINES

API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"

# PRD FR-05 요약 프롬프트 명세. 수정 이력은 docs/프롬프트-이력.md 에 남긴다.
PROMPT_TEMPLATE = """너는 기술 뉴스를 요약하는 편집자야.
아래 기사를 정확히 3줄 이내로 요약해줘.

규칙:
- 각 줄은 "- "로 시작하는 불릿 형태
- 각 줄 60자 이내
- 사실만 전달하고 추측이나 의견을 넣지 말 것
- 기사에 없는 내용을 만들어내지 말 것
- 요약 외의 머리말, 맺음말, 설명은 출력하지 말 것

제목: {title}
본문: {content}"""

SUMMARY_FAILED = "요약 실패"  # E-06. 데이터 유실 방지가 요약 품질보다 우선


class SummaryError(Exception):
    def __init__(self, code, message):
        super().__init__(f"[{code}] {message}")
        self.code = code


def build_prompt(article):
    return PROMPT_TEMPLATE.format(
        title=article.get("title", ""),
        content=(article.get("description") or "")[:4000],
    )


def summarize(article, api_key=None, max_retry=MAX_RETRY, sleep=time.sleep):
    """요약문 문자열을 돌려준다. 최종 실패 시 '요약 실패'를 반환(예외 아님).

    호출 실패로 파이프라인 전체를 죽이면 원문 링크마저 잃는다(E-05/E-06 정책).
    """
    api_key = api_key or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise SummaryError("E-10", "GEMINI_API_KEY 환경변수가 없다")

    prompt = build_prompt(article)
    last_error = None

    for attempt in range(max_retry + 1):  # 최초 1회 + 재시도 max_retry회
        try:
            return postprocess(_call_gemini(prompt, api_key))
        except SummaryError as exc:
            last_error = exc
            if exc.code == "E-10" or attempt == max_retry:
                break
            sleep(5 * (attempt + 1))  # 429 대응: 간격을 늘려가며 재시도

    if last_error and last_error.code == "E-10":
        raise last_error
    return SUMMARY_FAILED


def postprocess(raw_text):
    """E-07. 모델이 3줄을 넘기거나 머리말을 붙여도 저장 형식을 강제한다."""
    lines = []
    for line in (raw_text or "").splitlines():
        line = line.strip()
        if not line:
            continue
        # 불릿이 아닌 머리말("다음은 요약입니다:")은 버린다.
        if line[0] in "-*•":
            line = line[1:].strip()
        elif lines or _looks_like_preamble(line):
            continue
        if not line:
            continue
        lines.append("- " + line[:SUMMARY_MAX_CHARS])
        if len(lines) == SUMMARY_MAX_LINES:
            break
    return "\n".join(lines)


def _looks_like_preamble(line):
    return line.endswith(":") or line.endswith("：") or "요약" in line and len(line) < 20


def _call_gemini(prompt, api_key):
    url = f"{API_BASE}/{GEMINI_MODEL}:generateContent"
    payload = json.dumps({"contents": [{"parts": [{"text": prompt}]}]}).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 429:
            raise SummaryError("E-05", "Gemini 호출 한도 초과(429)") from exc
        if exc.code in (401, 403):
            raise SummaryError("E-10", f"Gemini 인증/권한 오류({exc.code})") from exc
        raise SummaryError("E-06", f"Gemini HTTP 오류({exc.code})") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise SummaryError("E-06", f"Gemini 통신 실패: {exc}") from exc

    try:
        return body["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError) as exc:
        # 안전 필터에 걸리면 candidates가 비거나 finishReason만 온다.
        raise SummaryError("E-06", f"Gemini 응답 형식 예상 밖: {body}") from exc

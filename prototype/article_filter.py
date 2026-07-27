"""FR-03. 주제 필터링 — 기사 후보 풀에서 정확히 0건 또는 1건을 확정한다.

규칙 (PRD 키워드 정책):
    1. 제외 키워드가 제목/본문에 있으면 후보에서 뺀다.
    2. 1순위 키워드를 **제목에서만** 찾는다. 하나라도 있으면 그 그룹이 후보다.
    3. 1순위가 0건일 때만 2순위를 제목+본문에서 찾는다(fallback).
    4. 후보가 여럿이면 pub_date가 가장 최신인 1건.

선택 기준이 결정론적이어서 같은 입력이면 항상 같은 결과가 나온다(재현 가능).
"""

from config import EXCLUDE_KEYWORDS, TIER1_KEYWORDS, TIER2_KEYWORDS
from date_utils import parse_pubdate
from datetime import datetime, timezone

_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


def matched_keywords(text, keywords):
    """대소문자를 무시하고 매칭된 키워드 목록을 돌려준다.

    'AI'는 대문자 두 글자라 소문자 비교 시 'said', 'again' 같은 단어에
    부분 일치할 수 있다. 영문 키워드는 단어 경계를 확인한다.
    """
    if not text:
        return []
    lowered = text.lower()
    hits = []
    for keyword in keywords:
        if _contains(lowered, keyword.lower()):
            hits.append(keyword)
    return hits


def select(articles):
    """(선택된 기사 or None, 판정 근거 dict)를 돌려준다."""
    pool = [a for a in articles if not matched_keywords(_haystack(a), EXCLUDE_KEYWORDS)]
    excluded = len(articles) - len(pool)

    # 1순위: 제목만
    tier1 = [(a, matched_keywords(a.get("title", ""), TIER1_KEYWORDS)) for a in pool]
    tier1 = [(a, hits) for a, hits in tier1 if hits]
    if tier1:
        return _latest(tier1, tier=1, scanned=len(articles), excluded=excluded)

    # 2순위: 제목 + 본문 (1순위 실패 시에만)
    tier2 = [(a, matched_keywords(_haystack(a), TIER2_KEYWORDS)) for a in pool]
    tier2 = [(a, hits) for a, hits in tier2 if hits]
    if tier2:
        return _latest(tier2, tier=2, scanned=len(articles), excluded=excluded)

    # E-03. 매칭 0건 → 오류가 아니라 정상 스킵
    return None, {
        "tier": None,
        "matched": [],
        "scanned": len(articles),
        "excluded": excluded,
        "candidates": 0,
    }


def _latest(candidates, tier, scanned, excluded):
    chosen, hits = max(candidates, key=lambda pair: _sort_key(pair[0]))
    return chosen, {
        "tier": tier,
        "matched": hits,
        "scanned": scanned,
        "excluded": excluded,
        "candidates": len(candidates),
    }


def _sort_key(article):
    """날짜 파싱이 실패한 기사는 가장 오래된 것으로 취급해 뒤로 민다."""
    return parse_pubdate(article.get("pub_date")) or _EPOCH


def _haystack(article):
    return f"{article.get('title', '')} {article.get('description', '')}"


def _contains(lowered_text, keyword):
    """ASCII 키워드는 단어 경계까지 확인하고, 한글은 단순 포함으로 본다.

    한글은 조사가 붙어(예: '인공지능이') 단어 경계 매칭이 오히려 실패한다.
    """
    if not keyword.isascii():
        return keyword in lowered_text
    index = lowered_text.find(keyword)
    while index != -1:
        before = lowered_text[index - 1] if index > 0 else " "
        after_pos = index + len(keyword)
        after = lowered_text[after_pos] if after_pos < len(lowered_text) else " "
        if not _is_word_char(before) and not _is_word_char(after):
            return True
        index = lowered_text.find(keyword, index + 1)
    return False


def _is_word_char(char):
    return char.isalnum() and char.isascii()

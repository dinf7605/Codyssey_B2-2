"""FR-04. 중복 저장 방지.

중복방지키: RSS guid가 1순위, 없으면 원문 링크. 다만 링크는 그대로 쓰지 않고
정규화 후 SHA-1 앞 16자로 줄인다. 이유:
  - Google News 링크에는 매 요청마다 달라지는 추적 파라미터가 붙는다.
    (utm_*, fbclid 등) 원문 그대로 비교하면 같은 기사가 매일 새 기사로 보인다.
  - Notion Text 속성 필터로 조회하므로 길이가 짧고 고정폭이면 다루기 쉽다.

Make에서는 sha1 함수가 없으므로 `md5(정규화된_링크)`를 대신 쓴다.
알고리즘이 달라도 "같은 기사면 같은 키"라는 성질만 유지되면 되고,
한 번 정한 뒤에는 절대 바꾸지 않는다(바꾸면 과거 저장분과 매칭되지 않는다).
"""

import hashlib
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

TRACKING_PREFIXES = ("utm_",)
TRACKING_PARAMS = {"fbclid", "gclid", "igshid", "ref", "oc", "ved", "usg"}


def normalize_link(link):
    """추적 파라미터와 대소문자/후행 슬래시 차이를 제거한다."""
    if not link:
        return ""
    parts = urlsplit(link.strip())
    query = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if key.lower() not in TRACKING_PARAMS
        and not key.lower().startswith(TRACKING_PREFIXES)
    ]
    path = parts.path.rstrip("/") or "/"
    return urlunsplit(
        (parts.scheme.lower(), parts.netloc.lower(), path, urlencode(query), "")
    )


def dedupe_key(article):
    """기사 1건의 중복방지키. guid가 있으면 그대로, 없으면 링크 해시."""
    guid = (article.get("guid") or "").strip()
    if guid:
        return guid
    link = normalize_link(article.get("link"))
    if not link:
        return ""
    return hashlib.sha1(link.encode("utf-8")).hexdigest()[:16]

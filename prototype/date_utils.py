"""RSS pubDate -> Notion Date(ISO 8601) 변환.

PRD 7장 / R1: "개발 중 가장 흔한 실패 지점". 실제로 피드마다 포맷이 다르다.

  RFC 822  : Mon, 27 Jul 2026 08:30:00 +0900   (RSS 2.0 표준, ZDNet/전자신문)
  RFC 822  : Mon, 27 Jul 2026 08:30:00 GMT     (Google News)
  ISO 8601 : 2026-07-27T08:30:00+09:00         (Atom 피드)
  ISO(Z)   : 2026-07-27T08:30:00Z

변환 실패는 예외를 던지지 않고 None을 돌려준다(E-08: 발행일시를 비우고 나머지 저장).
"""

from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

KST = timezone(timedelta(hours=9))


def parse_pubdate(raw):
    """RSS 날짜 문자열을 timezone-aware datetime으로 변환. 실패 시 None."""
    if not raw:
        return None
    raw = raw.strip()

    # 1) RFC 822 (RSS 2.0 표준 경로)
    try:
        dt = parsedate_to_datetime(raw)
        if dt is not None:
            return _ensure_tz(dt)
    except (TypeError, ValueError):
        pass

    # 2) ISO 8601 (Atom). 파이썬 3.11+ 는 'Z'도 처리하지만 하위 호환용으로 치환한다.
    try:
        return _ensure_tz(datetime.fromisoformat(raw.replace("Z", "+00:00")))
    except ValueError:
        pass

    # 3) 타임존이 빠진 흔한 변형들
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y.%m.%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt).replace(tzinfo=KST)
        except ValueError:
            continue

    return None


def to_notion_iso(raw):
    """Notion Date 속성에 그대로 넣을 수 있는 KST 기준 ISO 8601 문자열. 실패 시 None.

    Notion은 offset이 붙은 ISO 8601을 요구한다. 한국 팀 프로젝트이므로
    어떤 타임존으로 들어오든 KST(+09:00)로 통일해 저장한다.
    """
    dt = parse_pubdate(raw)
    return None if dt is None else dt.astimezone(KST).isoformat()


def now_iso():
    """수집일시 속성용 현재 시각(KST, ISO 8601)."""
    return datetime.now(KST).isoformat()


def _ensure_tz(dt):
    """타임존이 없는 datetime은 KST로 간주한다(국내 피드 기준)."""
    return dt.replace(tzinfo=KST) if dt.tzinfo is None else dt

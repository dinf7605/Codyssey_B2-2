"""FR-02. RSS 수집 및 파싱 (표준 라이브러리만 사용).

RSS 2.0과 Atom을 모두 읽어 동일한 dict 형태로 정규화한다.
    {title, link, pub_date, description, guid, source}

PRD 3.2 / NFR-08: RSS를 제공하지 않는 사이트는 건드리지 않는다. 이 모듈은
피드 URL만 받으며 HTML 페이지를 파싱하는 경로가 존재하지 않는다.
"""

import re
import urllib.error
import urllib.request
from xml.etree import ElementTree

from config import HTTP_TIMEOUT, MAX_ITEMS

ATOM = "{http://www.w3.org/2005/Atom}"
CONTENT = "{http://purl.org/rss/1.0/modules/content/}"
DC = "{http://purl.org/dc/elements/1.1/}"

USER_AGENT = "NewsSummaryBot/1.0 (team project; RSS only)"


class FeedError(Exception):
    """E-01(응답 없음) / E-02(파싱 실패) 구분용. code에 PRD 에러코드를 담는다."""

    def __init__(self, code, message):
        super().__init__(f"[{code}] {message}")
        self.code = code


def fetch(url, timeout=HTTP_TIMEOUT):
    """피드 XML 원문을 가져온다. 네트워크 실패는 E-01."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read()
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise FeedError("E-01", f"RSS 응답 없음/타임아웃: {url} ({exc})") from exc


def parse(xml_bytes, source="", limit=MAX_ITEMS):
    """XML을 기사 dict 리스트로 정규화한다. 형식 오류는 E-02(재시도 무의미)."""
    try:
        root = ElementTree.fromstring(xml_bytes)
    except ElementTree.ParseError as exc:
        raise FeedError("E-02", f"RSS 파싱 실패: {exc}") from exc

    items = root.findall(".//item") or root.findall(f".//{ATOM}entry")
    if not items:
        raise FeedError("E-02", "item/entry 요소를 찾지 못함 (피드 구조 변경 의심)")

    return [_normalize(item, source) for item in items[:limit]]


def load(url, source="", limit=MAX_ITEMS):
    """fetch + parse 조합. 실제 파이프라인에서 쓰는 진입점."""
    return parse(fetch(url), source=source, limit=limit)


def _normalize(item, source):
    link = _text(item, "link") or _atom_link(item)
    return {
        "title": _clean(_text(item, "title") or _text(item, f"{ATOM}title")),
        "link": (link or "").strip(),
        "pub_date": (
            _text(item, "pubDate")
            or _text(item, f"{DC}date")
            or _text(item, f"{ATOM}published")
            or _text(item, f"{ATOM}updated")
            or ""
        ).strip(),
        "description": _clean(
            _text(item, "description")
            or _text(item, f"{CONTENT}encoded")
            or _text(item, f"{ATOM}summary")
            or _text(item, f"{ATOM}content")
        ),
        "guid": (_text(item, "guid") or _text(item, f"{ATOM}id") or "").strip(),
        "source": source,
    }


def _text(item, tag):
    node = item.find(tag)
    return node.text if node is not None and node.text else ""


def _atom_link(item):
    """Atom의 link는 텍스트가 아니라 href 속성에 들어 있다."""
    for node in item.findall(f"{ATOM}link"):
        if node.get("rel", "alternate") == "alternate":
            return node.get("href", "")
    return ""


def _clean(text):
    """description에 섞여 오는 HTML 태그와 CDATA 잔여물을 제거한다.

    요약 프롬프트에 태그가 섞여 들어가면 모델이 태그를 그대로 뱉는 사고가 난다.
    """
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    text = (
        text.replace("&nbsp;", " ")
        .replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", '"')
        .replace("&#39;", "'")
    )
    return re.sub(r"\s+", " ", text).strip()

"""FR-06. Notion 저장 + 중복 조회.

Notion DB 스키마는 docs/notion-db-스키마.md 와 1:1로 대응한다.
속성명을 Notion에서 바꾸면 여기 PROP_* 상수도 반드시 같이 바꿔야 한다
(Notion API는 속성명을 키로 쓰므로 이름이 틀리면 400이 난다).
"""

import json
import os
import urllib.error
import urllib.request

from config import HTTP_TIMEOUT

API_ROOT = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"

PROP_TITLE = "제목"
PROP_SUMMARY = "요약문"
PROP_URL = "원문 링크"
PROP_PUBLISHED = "발행일시"
PROP_SOURCE = "출처"
PROP_KEY = "중복방지키"
PROP_COLLECTED = "수집일시"


class NotionError(Exception):
    def __init__(self, code, message):
        super().__init__(f"[{code}] {message}")
        self.code = code


def exists(key, database_id=None, token=None):
    """FR-04. 중복방지키가 이미 저장돼 있으면 True. **AI 호출보다 먼저 부른다.**"""
    if not key:
        return False
    body = {
        "filter": {"property": PROP_KEY, "rich_text": {"equals": key}},
        "page_size": 1,
    }
    result = _request(
        "POST", f"/databases/{_db(database_id)}/query", body, token=token
    )
    return bool(result.get("results"))


def create_page(record, database_id=None, token=None):
    """요약 결과 1건을 새 행으로 저장한다."""
    properties = {
        PROP_TITLE: {"title": [{"text": {"content": record["title"][:2000]}}]},
        PROP_SUMMARY: {
            "rich_text": [{"text": {"content": (record.get("summary") or "")[:2000]}}]
        },
        PROP_KEY: {"rich_text": [{"text": {"content": record.get("key", "")}}]},
    }
    if record.get("link"):
        properties[PROP_URL] = {"url": record["link"]}
    # E-08. 날짜 변환에 실패했으면 속성 자체를 보내지 않는다(비워둔 채 나머지 저장).
    if record.get("published_iso"):
        properties[PROP_PUBLISHED] = {"date": {"start": record["published_iso"]}}
    if record.get("collected_iso"):
        properties[PROP_COLLECTED] = {"date": {"start": record["collected_iso"]}}
    if record.get("source"):
        properties[PROP_SOURCE] = {"select": {"name": record["source"]}}

    payload = {"parent": {"database_id": _db(database_id)}, "properties": properties}
    return _request("POST", "/pages", payload, token=token)


def _request(method, path, payload, token=None):
    token = token or os.environ.get("NOTION_TOKEN")
    if not token:
        raise NotionError("E-10", "NOTION_TOKEN 환경변수가 없다")
    request = urllib.request.Request(
        API_ROOT + path,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Notion-Version": NOTION_VERSION,
        },
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:300]
        if exc.code in (401, 403):
            # 통합(Integration)을 DB에 연결하지 않으면 404/403이 난다. 재시도 무의미.
            raise NotionError("E-10", f"Notion 인증/권한 오류({exc.code}): {detail}") from exc
        raise NotionError("E-09", f"Notion 저장 실패({exc.code}): {detail}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise NotionError("E-09", f"Notion 통신 실패: {exc}") from exc


def _db(database_id):
    database_id = database_id or os.environ.get("NOTION_DATABASE_ID")
    if not database_id:
        raise NotionError("E-10", "NOTION_DATABASE_ID 환경변수가 없다")
    return database_id

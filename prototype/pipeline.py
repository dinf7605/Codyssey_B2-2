"""PRD 5.1 전체 흐름을 그대로 옮긴 참조 구현.

Make 시나리오를 만들기 전에 이 스크립트로 로직을 먼저 확정한다.
Make 각 모듈이 무엇을 해야 하는지는 docs/make-시나리오-명세.md 에 대응된다.

    [1] 트리거 → [2] RSS 수집 → [3] 필터 → [4] 중복체크 → [5] AI 요약 → [6] 저장

사용 예:
    python pipeline.py --dry-run                 # 고정 샘플, 외부 호출 0회
    python pipeline.py --fixture fixtures/sample_rss.xml --no-ai
    python pipeline.py --feed "전자신문" --no-ai
    python pipeline.py                           # 실제 실행 (키 3개 필요)
"""

import argparse
import sys
from pathlib import Path

import article_filter
import notion_store
import rss
from config import FEEDS, MAX_ITEMS, MAX_RETRY, PRIMARY_FEED
from date_utils import now_iso, to_notion_iso
from dedupe import dedupe_key
from summarize import SUMMARY_FAILED, SummaryError, summarize

EXIT_OK = 0
EXIT_SKIP = 0  # 정상 스킵은 실패가 아니다 (E-03, E-04)
EXIT_ERROR = 1


def log(stage, message):
    print(f"[{stage}] {message}")


def run(args):
    # --- [2] RSS 수집 -----------------------------------------------------
    try:
        if args.fixture:
            source = "fixture"
            articles = rss.parse(
                Path(args.fixture).read_bytes(), source=source, limit=MAX_ITEMS
            )
        else:
            source = args.feed
            articles = rss.load(FEEDS[source], source=source, limit=MAX_ITEMS)
    except rss.FeedError as exc:
        log("2/수집", f"실패 → 종료: {exc}")
        return EXIT_ERROR
    log("2/수집", f"{source}에서 {len(articles)}건 수집")

    # --- [3] 주제 필터링 --------------------------------------------------
    article, reason = article_filter.select(articles)
    if article is None:
        log(
            "3/필터",
            f"매칭 0건 → [정상 스킵] (검사 {reason['scanned']}건, "
            f"제외 키워드로 배제 {reason['excluded']}건) / E-03",
        )
        return EXIT_SKIP
    log(
        "3/필터",
        f"{reason['tier']}순위 매칭 {reason['matched']} / "
        f"후보 {reason['candidates']}건 중 최신 1건 선택",
    )
    log("3/필터", f"선택: {article['title']}")

    # --- [4] 중복 체크 (반드시 AI 호출보다 앞) ------------------------------
    key = dedupe_key(article)
    log("4/중복", f"중복방지키 = {key}")
    if not args.skip_notion:
        try:
            if notion_store.exists(key, args.database_id, args.notion_token):
                log("4/중복", "이미 저장된 기사 → [정상 스킵] AI 호출 안 함 / E-04")
                return EXIT_SKIP
        except notion_store.NotionError as exc:
            log("4/중복", f"조회 실패 → 종료: {exc}")
            return EXIT_ERROR

    # --- [5] AI 요약 (기사 1건당 1회) ---------------------------------------
    if args.no_ai:
        summary = "- (dry-run: AI 호출 생략)"
        log("5/요약", "건너뜀 (--no-ai)")
    else:
        try:
            summary = summarize(article, args.gemini_key, max_retry=MAX_RETRY)
        except SummaryError as exc:
            log("5/요약", f"복구 불가 → 종료: {exc}")
            return EXIT_ERROR
        if summary == SUMMARY_FAILED:
            log("5/요약", "재시도 2회 실패 → '요약 실패'로 저장 진행 / E-06")
        else:
            log("5/요약", f"{len(summary.splitlines())}줄 생성")

    # --- 날짜 변환 (R1 최우선 검증 지점) ------------------------------------
    published = to_notion_iso(article.get("pub_date"))
    if published is None and article.get("pub_date"):
        log("6/저장", f"날짜 변환 실패 → 발행일시 비우고 저장 / E-08 (원본: {article['pub_date']!r})")

    record = {
        "title": article["title"],
        "summary": summary,
        "link": article["link"],
        "published_iso": published,
        "collected_iso": now_iso(),
        "source": article.get("source") or source,
        "key": key,
    }

    # --- [6] Notion 저장 ---------------------------------------------------
    if args.skip_notion:
        log("6/저장", "건너뜀 (--skip-notion). 저장 예정 레코드:")
        _print_record(record)
        return EXIT_OK

    for attempt in range(MAX_RETRY + 1):
        try:
            page = notion_store.create_page(record, args.database_id, args.notion_token)
            log("7/종료", f"저장 완료: {page.get('url', page.get('id'))}")
            return EXIT_OK
        except notion_store.NotionError as exc:
            if exc.code == "E-10" or attempt == MAX_RETRY:
                log("6/저장", f"실패 → 종료 + 알림 대상: {exc}")
                return EXIT_ERROR
            log("6/저장", f"실패, 재시도 {attempt + 1}/{MAX_RETRY}: {exc}")
    return EXIT_ERROR


def _print_record(record):
    for label, value in record.items():
        head, *rest = str(value).splitlines() or [""]
        print(f"    {label:14} {head}")
        for line in rest:
            print(f"    {'':14} {line}")


def main(argv=None):
    parser = argparse.ArgumentParser(description="뉴스 요약 자동화 참조 구현")
    parser.add_argument("--feed", default=PRIMARY_FEED, choices=list(FEEDS))
    parser.add_argument("--fixture", help="네트워크 대신 로컬 RSS 파일 사용")
    parser.add_argument("--no-ai", action="store_true", help="Gemini 호출 생략")
    parser.add_argument("--skip-notion", action="store_true", help="Notion 호출 생략")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="샘플 피드 + AI/Notion 호출 없음 (외부 호출 0회, 크레딧 소모 0)",
    )
    parser.add_argument("--gemini-key", help="미지정 시 GEMINI_API_KEY 환경변수")
    parser.add_argument("--notion-token", help="미지정 시 NOTION_TOKEN 환경변수")
    parser.add_argument("--database-id", help="미지정 시 NOTION_DATABASE_ID 환경변수")
    args = parser.parse_args(argv)

    if args.dry_run:
        args.fixture = args.fixture or str(Path(__file__).parent / "fixtures" / "sample_rss.xml")
        args.no_ai = True
        args.skip_notion = True

    return run(args)


if __name__ == "__main__":
    sys.exit(main())

"""피드 후보를 비교해 선정 근거를 만든다 (미결 O1).

긴 한 줄 명령을 붙여넣다 줄이 끊기는 사고를 막기 위한 개발용 보조 스크립트다.
파이프라인은 이 파일을 import하지 않는다.

    python check_feed.py                 # config.FEEDS 전체 비교
    python check_feed.py <피드주소>       # 임의의 주소 하나만

확인 항목은 docs/조원별-실행가이드.md 5장(B 담당)의 선정 기준과 같다.
"""

import sys

import config
import rss
from article_filter import matched_keywords, select
from date_utils import to_notion_iso

SAMPLE = 20


def inspect(name, url):
    print(f"\n{'=' * 62}\n[{name}]\n{url}\n{'-' * 62}")

    try:
        articles = rss.load(url, name, SAMPLE)
    except rss.FeedError as exc:
        print(f"  실패: {exc}")
        print("  -> 후보 탈락. 주소가 맞는지, RSS가 맞는지 확인할 것")
        return None

    if not articles:
        print("  기사 0건 -> 후보 탈락")
        return None

    with_guid = sum(1 for a in articles if a["guid"])
    lengths = [len(a["description"]) for a in articles]
    avg_len = sum(lengths) // len(lengths)
    bad_dates = [a for a in articles if to_notion_iso(a["pub_date"]) is None]

    # 실제 파이프라인과 같은 규칙으로 판정한다(1순위는 제목만, 2순위는 본문까지).
    chosen, info = select(articles)
    tier1 = [a for a in articles if matched_keywords(a["title"], config.TIER1_KEYWORDS)]

    print(f"  기사 수          : {len(articles)}건")
    print(f"  guid 제공        : {with_guid}/{len(articles)}건"
          f"  {'(전부 있음 - 좋음)' if with_guid == len(articles) else '(누락 있음 - 주의)'}")
    print(f"  description 평균 : {avg_len}자"
          f"  {'(요약 가능)' if avg_len >= 80 else '(너무 짧음 - 요약 품질 위험)'}")
    print(f"  날짜 변환 실패   : {len(bad_dates)}건"
          f"  {'' if not bad_dates else '(R1 위험 - 아래 샘플을 test_date_utils.py에 추가할 것)'}")
    print(f"  제외 키워드 제거 : {info['excluded']}건")
    print(f"  1순위(제목) 매칭 : {len(tier1)}건")
    if chosen is None:
        print("  최종 판정        : 매칭 0건 (E-03 정상 스킵)")
    else:
        print(f"  최종 판정        : {info['tier']}순위로 후보 {info['candidates']}건")

    print(f"\n  pubDate 샘플     : {articles[0]['pub_date']!r}")
    print(f"  -> 변환 결과     : {to_notion_iso(articles[0]['pub_date'])!r}")
    if bad_dates:
        print(f"  변환 실패 샘플   : {bad_dates[0]['pub_date']!r}")

    if chosen:
        print(f"\n  오늘 선택될 기사 : {chosen['title'][:52]}")
        print(f"  매칭된 키워드    : {info['matched']}")

    print("\n  1순위 매칭 기사 (최대 3건):")
    for a in tier1[:3]:
        print(f"    - {a['title'][:56]}")
    if not tier1:
        print("    (없음 - 이 시간대에는 2순위 fallback으로 넘어간다)")

    return {
        "name": name,
        "guid_ok": with_guid == len(articles),
        "desc_ok": avg_len >= 80,
        "date_ok": not bad_dates,
        "matched": len(tier1),
    }


def verdict(results):
    print(f"\n{'=' * 62}\n선정 판단\n{'-' * 62}")
    print(f"  {'피드':<16} {'guid':<6} {'본문':<6} {'날짜':<6} {'매칭':<6}")
    for r in results:
        print(f"  {r['name']:<16} "
              f"{'O' if r['guid_ok'] else 'X':<6} "
              f"{'O' if r['desc_ok'] else 'X':<6} "
              f"{'O' if r['date_ok'] else 'X':<6} "
              f"{r['matched']:<6}")

    best = [r for r in results if r["guid_ok"] and r["desc_ok"] and r["matched"] > 0]
    print()
    if best:
        pick = max(best, key=lambda r: r["matched"])
        print(f"  추천: {pick['name']}")
        print("  근거: guid를 전부 제공하므로 중복방지키가 안정적이고,")
        print("        본문이 요약에 충분하며, 키워드 매칭 기사가 있다.")
    else:
        print("  전 후보가 기준 미달이다. guid 없는 피드를 쓸 수밖에 없다면")
        print("  링크의 추적 파라미터를 제거한 뒤 해시할 것 (명세서 [6] 참고).")

    print("\n  확정 후 할 일:")
    print("    1) config.py 의 FEEDS / PRIMARY_FEED 수정")
    print("    2) 위 pubDate 샘플을 tests/test_date_utils.py 에 케이스로 추가")
    print("    3) docs/make-시나리오-명세.md [2]절의 URL 수정")


def main():
    if len(sys.argv) > 1:
        feeds = {f"직접입력{i + 1}": u for i, u in enumerate(sys.argv[1:])}
    else:
        feeds = config.FEEDS

    results = [r for r in (inspect(n, u) for n, u in feeds.items()) if r]
    if results:
        verdict(results)


if __name__ == "__main__":
    main()

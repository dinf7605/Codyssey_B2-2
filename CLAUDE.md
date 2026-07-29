# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 이 저장소의 성격

**실제 제품은 Make(노코드 자동화 툴)의 시각적 시나리오다.** 이 저장소의 Python 코드는
그 시나리오를 만들기 전에 로직을 확정하기 위한 **참조 구현(reference implementation)**이며,
운영되지 않는다. 따라서:

- 코드를 고쳤으면 `docs/make-시나리오-명세.md`의 대응 항목도 같이 고쳐야 한다. 둘이 어긋나면
  실제 운영되는 쪽(Make)이 틀리게 된다.
- "이 기능을 코드로 더 잘 만들 수 있다"는 개선 제안은 대개 부적절하다. 과제 요건이 Make 사용이다.
- 코드의 목적은 **Make에서 검증하기 비싼 것(크레딧 소모, API 한도)을 공짜로 검증하는 것**이다.

### 참조 구현과 Make의 의도된 차이

아래 두 가지는 버그가 아니라 Make의 제약을 받아들인 결과다.
**"코드와 다르니 맞춰야 한다"고 판단해서 고치지 말 것.** 근거는 PRD v1.1과 명세서에 적혀 있다.

| 항목 | 참조 구현 | Make | 이유 |
|---|---|---|---|
| 키워드 fallback | 1순위 실패 시 2순위 (2단계) | 1·2순위를 OR로 합친 단일 Filter | Make Filter는 번들을 하나씩 통과시켜 "전부 훑은 뒤 0건이었는지" 판정이 불가능 |
| 중복방지키 해시 | `sha1(정규화된 링크)[:16]` | `md5(링크)` | Make에 sha1이 없다. 각 환경 안에서 일관되기만 하면 된다 |

## 명령어

```bash
# 전체 테스트 (52건, 외부 호출 0회)
cd prototype/tests && python -m unittest discover -s . -p "test_*.py"

# 단일 테스트 파일 / 단일 케이스
cd prototype/tests && python -m unittest test_date_utils -v
cd prototype/tests && python -m unittest test_article_filter.TestSelect.test_latest_wins_among_candidates

# 파이프라인 전체 흐름 (샘플 피드, AI/Notion 호출 없음)
cd prototype && python pipeline.py --dry-run

# 실제 RSS만 확인 (AI/Notion 호출 없음)
cd prototype && python pipeline.py --feed "전자신문" --no-ai --skip-notion

# 피드 후보 비교 (guid/본문길이/날짜변환/키워드매칭을 한 번에)
cd prototype && python check_feed.py
```

의존성 없음 — 표준 라이브러리만 쓴다. `pip install` 불필요.
테스트는 `tests/_path.py`를 import해 상위 폴더를 `sys.path`에 넣는 방식이라 `tests/`에서 실행해야 한다.

## 아키텍처

`pipeline.py`가 PRD 5.1의 7단계 흐름을 그대로 오케스트레이션하고, 각 단계는 독립 모듈이다.

```
rss.py          → article_filter.py → dedupe.py → notion_store.exists() → summarize.py → notion_store.create_page()
[2]수집            [3]필터              키 생성      [4]중복체크             [5]요약         [6]저장
```

`config.py`가 키워드·피드·한도를 전부 들고 있고 나머지 모듈이 여기서 읽어 간다.

### 반드시 지켜야 하는 불변 조건

이 네 가지는 PRD의 성공 기준(S3/S4/S5)과 직결되므로 코드를 바꿀 때 깨뜨리면 안 된다.

1. **중복 체크는 AI 호출보다 앞에 온다.** 순서를 바꾸면 이미 저장된 기사에도 API를 쓰게 되어
   무료 한도 방어가 무너진다. `pipeline.run()`의 `[4]`가 `[5]`보다 먼저다.
2. **기사 1건당 AI 호출 1회.** 요약이 3줄을 넘어도 재호출하지 않고 `summarize.postprocess()`로
   자른다(E-07). 재시도는 통신 실패 시에만, 최대 2회.
3. **정상 스킵과 오류는 다르다.** 매칭 0건(E-03)과 중복(E-04)은 종료 코드 **0**이다.
   1을 반환하게 만들면 "7일 연속 성공"(S1) 측정이 깨지고 불필요한 알림이 나간다.
4. **중복방지키 생성 규칙은 한 번 정하면 바꾸지 않는다.** 바꾸면 이미 저장된 레코드와 매칭되지 않아
   전부 중복 저장된다. Make는 `md5`, 참조 구현은 `sha1[:16]`으로 알고리즘이 다른데, 이는 의도된 것이다
   (각 환경 안에서 일관되기만 하면 된다).

### 에러 코드 규약

`FeedError` / `SummaryError` / `NotionError`는 모두 `code` 속성에 PRD 10장의 에러 코드(E-01~E-10)를
담는다. 새 실패 경로를 추가할 때도 반드시 코드를 붙인다 — `docs/에러-테스트-케이스.md`의
테스트 케이스와 1:1로 대응되어야 하고, 이 대응 관계 자체가 제출물이다.

`E-10`(인증/권한)은 어느 모듈에서든 **재시도하지 않는다**. 설정 문제라 재시도로 풀리지 않는다.

### 실패해도 저장은 진행한다

E-05/E-06(요약 실패), E-08(날짜 변환 실패)은 예외를 위로 던지지 않는다.
각각 `"요약 실패"` 문자열과 `None`을 돌려주고 나머지 필드는 저장한다.
**데이터 유실 방지가 필드 완전성보다 우선**이라는 것이 PRD가 정한 방침이다.

## 날짜 처리

`date_utils.to_notion_iso()`는 PRD가 "개발 중 가장 흔한 실패 지점"(R1)으로 지목한 지점이다.
RFC 822 / ISO 8601 / 타임존 없는 변형을 모두 받아 **KST 기준 ISO 8601**로 통일하며,
실패 시 예외 대신 `None`을 반환한다. 새 피드를 추가하면 그 피드의 실제 `pubDate` 샘플을
`tests/test_date_utils.py`에 케이스로 먼저 추가한다.

## 한글 키워드 매칭

`article_filter._contains()`는 ASCII 키워드에만 단어 경계를 적용한다.
- 영문: `AI`가 `said`, `again`에 부분 일치하면 안 되므로 경계 확인이 필요하다.
- 한글: 조사가 붙으므로(`인공지능이`) 경계를 요구하면 오히려 매칭에 실패한다. 단순 포함으로 본다.

## 크레딧/한도 절약

개발 중에는 `--dry-run`과 `fixtures/sample_rss.xml`을 쓴다(PRD R5).
샘플 피드에는 제외 키워드, 본문 전용 매칭, 깨진 날짜, guid 누락 케이스가 의도적으로 섞여 있으므로
새 함정을 발견하면 여기에 추가한다. Gemini/Notion을 실제로 호출하는 테스트는 작성하지 않는다.

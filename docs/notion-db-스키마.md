# Notion DB 스키마 및 연동 설정

담당: D. **속성명은 코드(`prototype/notion_store.py`의 `PROP_*`)와 Make 매핑에 그대로 쓰인다.**
Notion에서 이름을 바꾸면 두 곳 모두 같이 고쳐야 한다 (Notion API는 속성명을 키로 쓴다).

## 1. DB 생성

- 이름: `기술 뉴스 아카이브`
- 형태: 전체 페이지 데이터베이스(Full page database). 인라인 DB는 API에서 다루기 번거롭다.

## 2. 속성 정의

| 속성명 | 타입 | 필수 | 매핑 소스 | 만들 때 주의 |
|---|---|---|---|---|
| `제목` | Title | ✅ | RSS title | 새 DB의 기본 Title 속성 이름을 `이름`→`제목`으로 바꾼다 |
| `요약문` | Text | ✅ | Gemini 응답 | 불릿 3줄이 줄바꿈으로 들어간다 |
| `원문 링크` | URL | ✅ | RSS link | 공백 포함 이름이니 오타 주의 |
| `발행일시` | Date | ✅ | RSS pubDate | **Include time 켜기** |
| `출처` | Select | ⬜ | 피드명 상수 | 옵션을 미리 만들어 둘 것 (아래 참고) |
| `중복방지키` | Text | ⬜ | guid 또는 링크 해시 | 조회 대상. Text여야 `equals` 필터가 된다 |
| `수집일시` | Date | ⬜ | 실행 시각 | Include time 켜기 |
| `감성` | Select | ⬜ | 보너스 B2 | 긍정 / 중립 / 부정 |
| `썸네일` | Files | ⬜ | 보너스 B1 | |

> **Select 속성 주의**: Notion API로 존재하지 않는 옵션명을 보내면 자동 생성되지만,
> 오타가 나면 `전자신문`과 `전자 신문`이 별개 옵션으로 쌓인다.
> 피드명은 `prototype/config.py`의 `FEEDS` 키를 **그대로** 쓴다 (현재 확정값: `전자신문`).

## 3. 통합(Integration) 연결 — 여기서 제일 많이 막힌다

1. https://www.notion.so/my-integrations → New integration
2. 이름 지정, Capabilities에 **Read content / Insert content / Update content** 체크
3. Internal Integration Secret 복사 (`ntn_`으로 시작) → Make의 Notion Connection에 입력
4. **DB 페이지로 가서** `...` 메뉴 → `연결`(Connections) → 만든 통합 추가

> 4번을 빼먹으면 키가 맞아도 `404 object_not_found`가 난다. 증상이 "권한"이 아니라 "없음"으로 보여서 헷갈린다.

## 4. Database ID 찾기

DB를 브라우저에서 연 뒤 주소:

```
https://www.notion.so/<workspace>/<32자리_영숫자>?v=<뷰ID>
                                   ^^^^^^^^^^^^^^ 이게 Database ID
```

`?v=` 앞의 32자리다. 하이픈은 있어도 없어도 된다.

## 5. 검수 체크 (성공 기준 S2 — 매핑 정확도 100%)

저장된 레코드를 전수로 볼 때 확인할 것:

- [ ] `제목`이 비어 있지 않다
- [ ] `요약문`이 3줄 이하이고 각 줄이 `- `로 시작한다
- [ ] `원문 링크`를 클릭하면 실제 기사가 열린다 (URL 타입이라 클릭 가능해야 정상)
- [ ] `발행일시`에 **시각까지** 들어 있다 (날짜만 있으면 Include time 미설정)
- [ ] `발행일시`가 KST 기준이다 (GMT 피드를 쓰면 9시간 밀려 전날로 보인다)
- [ ] `중복방지키`가 모든 행에서 서로 다르다 (성공 기준 S3)

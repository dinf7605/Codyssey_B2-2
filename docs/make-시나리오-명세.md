# Make 시나리오 구성 명세

`prototype/`의 파이썬 참조 구현과 1:1로 대응한다. Make는 GUI 작업이라 대신 만들어 줄 수 없지만,
**각 모듈에 무엇을 넣어야 하는지는 여기 전부 적혀 있다.** 화면 보면서 그대로 따라 넣으면 된다.

담당: A(통합) / B(2~6번) / C(10~11번) / D(7~9, 12번)

---

## 0. 시작 전 계정 설정 (A 담당, 한 번만)

| 항목 | 값 | 안 하면 생기는 일 |
|---|---|---|
| Make 프로필 타임존 | `Asia/Seoul` | 스케줄이 UTC로 돌아 09:00이 18:00에 실행된다 |
| Connection 등록 | Notion, Google(Gemini) | 모듈에 키를 직접 타이핑하면 NFR-06 위반 |
| 시나리오 설정 → Sequential processing | **켜기** | 번들이 병렬 처리되며 중복 저장이 새어 나온다 |

---

## 1. 모듈 구성 (전체 12개)

> 아래 `{{2.title}}` 같은 표기의 숫자는 **모듈 번호**다. 순서가 다르면 번호를 바꿔 쓴다.

### [1] Schedule — 트리거

| 설정 | 값 |
|---|---|
| Run scenario | Every day |
| Time | `09:00` |
| Advanced scheduling | 사용 안 함 |

> FR-01. 15분 간격 같은 반복 트리거를 쓰지 않는다. 무료 플랜 크레딧을 하루에 태운다.

### [2] RSS — Retrieve RSS feed items

| 설정 | 값 |
|---|---|
| URL | `https://rss.etnews.com/Section901.xml` (전자신문, 미결 O1 확정) |
| Maximum number of returned items | `20` |

> ⚠️ PRD 초안의 1순위였던 ZDNet Korea(`news_xml.asp`)는 **404라 못 쓴다.**
> `prototype/config.py`의 `FEEDS`와 항상 같은 값을 유지할 것.
> 피드를 바꿀 때는 `cd prototype && python check_feed.py` 로 먼저 실측한다.

**출력 필드**: `title`, `url`, `dateCreated`, `description`, `id`

⚠️ Make의 RSS 모듈은 필드명이 RSS 규격과 다르다. **화면에서 확인한 실제 이름은 아래가 맞다.**

| RSS 규격 | Make 모듈 |
|---|---|
| `link` | **`url`** |
| `pubDate` | **`dateCreated`** |
| `guid` | **`id`** |

`guid`라는 이름으로 매핑하면 에러 없이 **빈 값**이 나온다. 중복방지키가 조용히
링크 해시로 넘어가므로 알아채기 어렵다 — [6]에서 반드시 `"id"`를 쓸 것.

> 🔑 **날짜 관련 핵심**: RSS 모듈이 주는 `dateCreated`는 **문자열이 아니라 이미 Date 타입**이다.
> 그래서 Notion Date 속성에 그냥 매핑하면 대개 그대로 들어간다. R1이 터지는 경우는 두 가지뿐이다.
> ① HTTP 모듈 + XML 파서로 직접 만든 경우 ② 피드가 비표준 포맷을 쓰는 경우.
> 그때만 아래 [12]의 `parseDate` 우회를 쓴다.

### [3] Filter — "주제 매칭" (모듈 사이의 렌치 아이콘)

Label: `주제 매칭`

## 🚨 Make Filter의 AND/OR 구조를 먼저 이해할 것

Make의 Filter는 **OR가 조건을 더하는 게 아니라 그룹을 나눈다.**

```
전체 판정 = (그룹1의 조건 전부 AND) OR (그룹2의 조건 전부 AND) OR ...
```

즉 `Add OR rule`은 **새 그룹을 만든다.** "제외 5개를 AND, 주제 키워드를 OR"로 넣으면
실제 의미는 `(제외조건들) OR (키워드1) OR (키워드2) ...` 가 되어 **제외 그룹만 참이어도
통과한다** — AI와 무관한 기사가 전부 흘러간다. 아래처럼 구성해야 한다.

### 조건 (그룹 2개, 각 그룹은 조건 6개)

**그룹 1 — 핵심 키워드를 제목에서만 찾는다**

| 왼쪽 | 연산자 | 오른쪽 |
|---|---|---|
| `{{2.title}}` | Text: Does not contain | `광고` |
| `{{2.title}}` | Text: Does not contain | `협찬` |
| `{{2.title}}` | Text: Does not contain | `이벤트` |
| `{{2.title}}` | Text: Does not contain | `채용` |
| `{{2.title}}` | Text: Does not contain | `프로모션` |
| `{{2.title}}` | **Text: Matches pattern** | `(?i)(\b(AI\|LLM\|ChatGPT\|Gemini\|Claude)\b\|인공지능\|생성형)` |

**그룹 2** — `Add OR rule`로 새 그룹을 만들고, 제외 5개를 **똑같이 다시 넣은 뒤** 마지막 줄만 바꾼다.

| 왼쪽 | 연산자 | 오른쪽 |
|---|---|---|
| (제외 5개 동일) | | |
| `{{2.title + " " + 2.description}}` | **Text: Matches pattern** | `(?i)(머신러닝\|딥러닝\|반도체\|데이터센터\|\bGPU\b)` |

> **키워드를 정규식 한 줄로 묶는 이유**: 키워드 하나당 조건 한 줄로 하면 그룹마다 제외 5개를
> 반복해야 해서 조건이 72개가 된다. 정규식으로 묶으면 12개로 끝난다.
>
> **`\b`(단어 경계)를 영문에만 붙이는 이유**: `AI`는 `said`, `again` 안에도 들어 있어 경계가
> 없으면 오탐이 난다. 한글은 조사가 붙으므로(`인공지능이`) 경계를 요구하면 오히려 매칭에
> 실패한다. 참조 구현 `article_filter._contains()`와 같은 정책이다.
>
> **그룹을 둘로 나눈 이유**: 실측 결과 `한국은행 "주가 하방 압력 제한적"` 같은 경제 기사가
> 본문에 "AI"가 한 번 언급됐다는 이유로 걸렸다. 핵심 키워드는 제목에서만 봐야 주제가 맞다.

> ⚠️ **PRD와 다른 점(의도적 단순화, PRD v1.1 FR-03에 반영됨)**
> PRD 초안은 "1순위가 0건일 때만 2순위"라는 2단계 fallback이지만, Make의 Filter는 번들을
> 하나씩 통과시키는 구조라 "전부 훑고 나서 1순위가 하나도 없었는지"를 판단할 수 없다.
>
> **v1은 위처럼 1·2순위를 OR로 합친 단일 Filter로 간다.** 그 결과 [6]에서 고르는 것은
> "1순위 우선"이 아니라 **"통과분 중 가장 최신 1건"**이다. 즉 1순위 기사가 있는 날에도
> 2순위 기사가 더 최신이면 그쪽이 선택될 수 있다. 두 키워드군 모두 관심 주제이므로 수용한다.
>
> 정석 2단계로 가려면 Aggregator를 한 겹 더 쌓고 Router로 갈라야 한다(모듈 16개 이상).
> 참조 구현 `prototype/article_filter.py`는 정석 2단계로 되어 있으니, 발표 때
> "원래 설계는 이렇고 Make 제약 때문에 이렇게 바꿨다"를 설명하는 근거로 쓸 것.

### [4] Array aggregator

| 설정 | 값 |
|---|---|
| Source Module | `[2] RSS` |
| Aggregated fields | `title`, `url`, `dateCreated`, `description`, **`id`** (guid 아님) |

> 🔑 이 모듈이 있는 이유: **Filter를 통과한 번들이 0개면 뒤 모듈이 아예 실행되지 않는다.**
> Aggregator는 입력이 0개여도 "빈 배열 1개"를 반드시 내보낸다.
> 이게 없으면 "매칭 0건"을 감지해서 로그를 남기는 것 자체가 불가능하다.

### [5] Filter — "매칭 있음"

```
{{length(4.array)}}   Numeric: greater than   0
```

통과 못 하면 여기서 조용히 끝난다 = **E-03 정상 스킵**. 알림을 붙이지 않는다.

### [6] Tools — Set multiple variables

아래 5개를 만든다. **`선택기사`를 먼저 만들고 나머지가 그걸 참조하는 방식은 쓰지 말 것** —
Make의 "Set multiple variables"는 같은 모듈 안에서 방금 만든 변수를 참조하는 것이 보장되지 않는다.
번거롭더라도 각 변수가 `first(sort(...))`를 각자 다시 쓴다.

| 변수명 | 값 |
|---|---|
| `제목` | `{{get(first(sort(4.array; desc; dateCreated)); "title")}}` |
| `링크` | `{{get(first(sort(4.array; desc; dateCreated)); "url")}}` |
| `본문` | `{{substring(get(first(sort(4.array; desc; dateCreated)); "description"); 0; 4000)}}` |
| `발행일시` | `{{get(first(sort(4.array; desc; dateCreated)); "dateCreated")}}` |
| `중복방지키` | `{{ifempty(get(first(sort(4.array; desc; dateCreated)); "id"); md5(get(first(sort(4.array; desc; dateCreated)); "url")))}}` |

> **`sort(...; desc; dateCreated)`를 쓰는 근거**: FR-03의 선택 규칙은 "pubDate가 가장 최신인 1건"이다.
> 그냥 `first(4.array)`로 해도 대부분 맞는다(RSS는 보통 최신순으로 온다). 하지만 그건 **피드의 정렬 습관에
> 의존하는 것**이라, 피드가 정렬을 바꾸면 조용히 엉뚱한 기사가 선택된다. 명시적으로 정렬해 두면
> 참조 구현 `article_filter._latest()`와 판정 기준이 같아지고, 선택 결과가 재현 가능해진다.
>
> **`md5`를 쓰는 근거**: Make에는 sha1이 없다. 알고리즘은 달라도 "같은 링크면 같은 키"만 지키면 된다.
> 단, **한 번 정하면 절대 바꾸지 말 것.** 바꾸는 순간 과거 저장분과 매칭이 안 돼 전부 중복 저장된다.
>
> ⚠️ **필드명은 `"guid"`가 아니라 `"id"`다.** Make RSS 모듈이 guid를 `id`로 노출한다.
> `"guid"`로 쓰면 에러 없이 빈 값이 나오고 `ifempty` 때문에 조용히 링크 해시로 넘어간다.
>
> ⚠️ 참조 구현은 링크의 추적 파라미터(`utm_*` 등)를 떼고 해시하지만, Make 수식에는 그 정리 단계가 없다.
> **id(guid)를 주는 피드를 고르면 이 문제 자체가 사라진다.** 확정 피드인 전자신문은 `id`를
> `20260729000137` 형태의 기사 고유번호로 20/20건 제공하므로 해당 사항이 없다.
> id 없는 피드를 쓸 수밖에 없다면 `{{md5(replace(링크; "/\?utm_.*$/"; ""))}}` 형태로 정리 후 해시한다.
>
> **확정 전에 실제 값을 볼 것**: `[2] RSS` 우클릭 → `Run this module only` → OUTPUT의 `id` 확인.
> 중복방지키는 한 번 정하면 바꿀 수 없으므로 이 확인을 건너뛰지 않는다.

### [7] Notion — Search Objects / Get many Database Items

| 설정 | 값 |
|---|---|
| Database ID | 기술 뉴스 아카이브 DB |
| Filter | `중복방지키` `Equals` `{{6.중복방지키}}` |
| Limit | `1` |

### [8] Array aggregator

Source Module: `[7] Notion`. ([4]와 같은 이유 — 0건일 때 흐름이 끊기는 걸 막는다.)

### [9] Filter — "중복 아님"

```
{{length(8.array)}}   Numeric: equal to   0
```

통과 못 하면 **E-04 정상 스킵**. 👉 **이 필터는 반드시 [10] Gemini보다 앞에 있어야 한다** (설계 원칙 1, NFR-04).

### [10] HTTP — Make a request (Gemini 호출)

| 설정 | 값 |
|---|---|
| URL | `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent` |
| Method | `POST` |
| Headers | `Content-Type: application/json` / `x-goog-api-key: (Connection 또는 Keychain에 저장한 키)` |
| Body type | `Raw` / `JSON (application/json)` |
| Parse response | `Yes` |

Request content:

```json
{
  "contents": [
    {
      "parts": [
        { "text": "너는 기술 뉴스를 요약하는 편집자야.\n아래 기사를 정확히 3줄 이내로 요약해줘.\n\n규칙:\n- 각 줄은 \"- \"로 시작하는 불릿 형태\n- 각 줄 60자 이내\n- 사실만 전달하고 추측이나 의견을 넣지 말 것\n- 기사에 없는 내용을 만들어내지 말 것\n- 요약 외의 머리말, 맺음말, 설명은 출력하지 말 것\n\n제목: {{6.제목}}\n본문: {{6.본문}}" }
      ]
    }
  ]
}
```

응답에서 쓸 값: `{{10.data.candidates[1].content.parts[1].text}}`
(Make 배열 인덱스는 **1부터** 시작한다. 0으로 쓰면 빈 값이 나온다.)

**에러 핸들러** (모듈 우클릭 → Add error handler):
- `Break` 지정, Number of attempts `2`, Interval `5분` → E-05/E-06 재시도 상한
- 최종 실패 시에도 저장은 진행돼야 하므로 → 아래 [11]에서 `ifempty`로 방어

### [11] Tools — Set variable (요약문 후처리)

| 변수명 | 값 |
|---|---|
| `요약문` | `{{ifempty(join(slice(split(10.data.candidates[1].content.parts[1].text; newline); 0; 3); newline); "요약 실패")}}` |

> **E-07**(3줄 초과)을 재호출 없이 잘라내는 식이다. `split` → `slice(0,3)` → `join`.
> 응답이 비면 `요약 실패` 문자열로 대체 → **E-06: 데이터 유실 방지가 요약 품질보다 우선**.

### [12] Notion — Create a Database Item

| Notion 속성 | 매핑 값 |
|---|---|
| 제목 (Title) | `{{6.제목}}` |
| 요약문 (Text) | `{{11.요약문}}` |
| 원문 링크 (URL) | `{{6.링크}}` |
| 발행일시 (Date) | `{{6.발행일시}}` |
| 출처 (Select) | 피드명 상수 — `전자신문` (`config.py`의 `FEEDS` 키와 글자까지 동일하게) |
| 중복방지키 (Text) | `{{6.중복방지키}}` |
| 수집일시 (Date) | `{{now}}` |

**발행일시가 안 들어갈 때 (R1 발동 시)** — 아래 순서로 시도한다:

```
1차: {{6.발행일시}}                                              (Date 타입 그대로)
2차: {{formatDate(6.발행일시; "YYYY-MM-DDTHH:mm:ssZ"; "Asia/Seoul")}}
3차: {{parseDate(6.발행일시; "ddd, DD MMM YYYY HH:mm:ss ZZ"; "Asia/Seoul")}}   (문자열로 올 때)
4차: 속성을 비우고 나머지만 저장                                    (E-08)
```

**에러 핸들러**: `Break`, attempts `2`, interval `5분` → 실패 시 E-09 알림 대상.

---

## 2. 크레딧 추정 (PRD 8.1 수정 필요)

PRD는 실행당 6~8 크레딧으로 잡았지만, 위 구성은 모듈이 12개다.

| 항목 | 계산 |
|---|---|
| 정상 저장되는 날 | 약 10~14 ops (Filter는 소모 없음, Aggregator·변수·HTTP는 소모) |
| 정상 스킵되는 날 | 약 4~6 ops |
| 월 30일 운영 | 대략 **300~420 ops** |
| 무료 한도 | 1,000 ops/월 |

여유는 있지만 PRD 추정치의 약 2배다. **개발 중 테스트 실행이 여기서 나간다** — R5대로 `python pipeline.py --dry-run`으로
로직을 먼저 확정하고, Make 실기 테스트는 횟수를 세어 가며 하는 게 맞다.
M1 첫 주에 실제 소모량을 한 번 재서 이 표를 확정할 것.

---

## 3. 자주 터지는 지점

| 증상 | 원인 | 조치 |
|---|---|---|
| 주제와 무관한 기사가 전부 통과 | Filter의 OR가 **그룹을 나눈다**는 걸 놓침 | 제외 조건을 각 OR 그룹에 **모두** 넣는다 ([3] 참고) |
| 중복방지키가 항상 링크 해시 | 필드명을 `guid`로 씀 → 빈 값 | Make RSS는 **`id`**. `ifempty`가 조용히 대체하므로 값 확인 필수 |
| 필터 뒤 모듈이 아예 실행 안 됨 | 통과 번들 0개 → 흐름 종료 | Aggregator를 끼워 빈 배열 1건을 만든다 ([4],[8]) |
| Gemini 응답이 빈 값 | 배열 인덱스를 `[0]`으로 씀 | Make는 **1부터** 시작 |
| Notion 400 `property does not exist` | 속성명 오타/변경 | Notion 화면의 속성명과 글자 하나까지 같아야 함 |
| Notion 404 | 통합을 DB에 연결 안 함 | DB 페이지 → `...` → Connections → 통합 추가 |
| 09:00이 아닌 시각에 실행 | 프로필 타임존 미설정 | Make 프로필 → Time zone → Asia/Seoul |
| 같은 기사가 매일 저장됨 | guid 없는 피드 + 링크에 추적 파라미터 | `md5`로 감싸기 전에 파라미터를 떼거나 guid 있는 피드로 교체 |

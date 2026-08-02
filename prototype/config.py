"""PRD 3.1 / FR-02 / FR-03에서 정한 설정값을 한 곳에 모은다.

Make 시나리오에서도 동일한 값을 써야 하므로, 여기 값을 바꾸면
docs/make-시나리오-명세.md 의 대응 항목도 함께 고쳐야 한다.
"""

# --- FR-02. RSS 피드 (미결 O1 확정: 2026-07-29) ----------------------------
# 근거는 `python check_feed.py` 실측. ZDNet Korea(news_xml.asp)는 404라 후보에서 뺐다.
FEEDS = {
    # 1순위. guid 20/20건, description 평균 248자, pubDate 변환 실패 0건.
    "전자신문": "https://rss.etnews.com/Section901.xml",
    # 백업: 키워드가 URL에 박혀 있어 사전 필터가 가능하다. 다만 description이
    # 평균 41자뿐이라 요약 품질이 떨어진다 — 1순위가 죽었을 때만 쓴다.
    "Google News": (
        "https://news.google.com/rss/search"
        "?q=AI+OR+인공지능+when:1d&hl=ko&gl=KR&ceid=KR:ko"
    ),
}

PRIMARY_FEED = "전자신문"
BACKUP_FEED = "Google News"

# 회당 조회 상한 (FR-02)
MAX_ITEMS = 20

# --- FR-03. 키워드 정책 ---------------------------------------------------
# 1순위: 제목에서만 매칭. 제목에 있으면 기사 주제일 확률이 높다.
TIER1_KEYWORDS = ["AI", "인공지능", "LLM", "생성형", "ChatGPT", "Gemini", "Claude"]

# 2순위: 1순위가 0건일 때만 본문(description)까지 확대. 수집 실패일을 줄인다.
TIER2_KEYWORDS = ["머신러닝", "딥러닝", "반도체", "GPU", "데이터센터"]

# 제외: 홍보성 기사는 요약 품질이 낮고 API 호출이 낭비된다.
EXCLUDE_KEYWORDS = ["광고", "협찬", "이벤트", "채용", "프로모션"]

# --- FR-05. AI 요약 -------------------------------------------------------
# 미결 O2 확정 (2026-07-29). gemini-2.5-flash는 "신규 사용자에게 더 이상 제공되지 않음"
# 404를 반환했다. 무료 한도가 열려 있는 모델은 AI Studio > 비율 제한에서 확인한다
# (RPD가 0/0이면 그 계정에서 못 쓴다).
GEMINI_MODEL = "gemini-3.5-flash"
SUMMARY_MAX_LINES = 3
SUMMARY_MAX_CHARS = 60

# --- 공통 ----------------------------------------------------------------
TIMEZONE = "Asia/Seoul"
MAX_RETRY = 2  # NFR-05. 모든 재시도는 최대 2회
HTTP_TIMEOUT = 20

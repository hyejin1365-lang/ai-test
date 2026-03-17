# ⚡ AI PULSE — 실시간 AI 트렌드 대시보드

> 실제 RSS 기반 자동 수집 | GitHub Pages + Actions | 매일 오전 7시 KST 자동 갱신

---

## 📁 프로젝트 구조

```
ai-pulse/
├── index.html              # 메인 대시보드 (HTML)
├── style.css               # 스타일 (다크/라이트, 반응형)
├── app.js                  # 프론트엔드 로직 (렌더링, 차트)
├── fetch_ai_news.py        # RSS 수집 스크립트 (Python)
├── requirements.txt        # Python 의존성
├── data/
│   └── ai_news.json        # 수집된 뉴스 데이터 (자동 생성)
└── .github/
    └── workflows/
        └── collect_news.yml  # GitHub Actions (매일 오전 7시 KST)
```

---

## 🚀 배포 방법 (5단계)

### 1단계 — GitHub 저장소 생성
```
저장소 이름: ai-pulse
공개(Public) 설정
```

### 2단계 — 파일 업로드
```bash
git init
git add .
git commit -m "🚀 Initial commit — AI PULSE"
git remote add origin https://github.com/YOUR_USERNAME/ai-pulse.git
git push -u origin main
```

### 3단계 — 첫 번째 수집 실행 (수동)
```
GitHub 저장소 → Actions 탭
→ "AI PULSE — 일간 뉴스 자동 수집"
→ "Run workflow" 클릭
```
→ `data/ai_news.json` 파일이 자동 생성됩니다.

### 4단계 — GitHub Pages 활성화
```
Settings → Pages
→ Source: Deploy from a branch
→ Branch: main / (root)
→ Save
```
→ `https://YOUR_USERNAME.github.io/ai-pulse` 로 접속 가능!

### 5단계 — 자동화 확인
```
매일 오전 7시 KST에 자동 실행됩니다.
Actions 탭에서 실행 기록 확인 가능.
```

---

## 📡 수집 소스 목록

| 분류 | 소스 | RSS URL |
|------|------|---------|
| 🟣 논문 | ArXiv AI | `https://rss.arxiv.org/rss/cs.AI` |
| 🟣 논문 | ArXiv ML | `https://rss.arxiv.org/rss/cs.LG` |
| 🟣 논문 | ArXiv CV | `https://rss.arxiv.org/rss/cs.CV` |
| 🟣 논문 | ArXiv CL | `https://rss.arxiv.org/rss/cs.CL` |
| 🔵 공식 | OpenAI | `https://openai.com/news/rss.xml` |
| 🔵 공식 | HuggingFace | `https://huggingface.co/blog/feed.xml` |
| 🔵 공식 | Google AI | `http://googleaiblog.blogspot.com/atom.xml` |
| 🔵 공식 | DeepMind | `https://deepmind.google/blog/rss.xml` |
| 🔵 공식 | LangChain | `https://blog.langchain.dev/rss/` |
| 🟢 뉴스 | VentureBeat AI | `https://venturebeat.com/category/ai/feed/` |
| 🟢 뉴스 | MIT Tech Review | `https://www.technologyreview.com/feed/` |
| 🟢 뉴스 | MarkTechPost | `https://www.marktechpost.com/feed/` |
| 🟢 뉴스 | KDnuggets | `https://www.kdnuggets.com/feed` |
| 🟢 뉴스 | AI Business | `https://aibusiness.com/rss.xml` |
| 🔴 도구 | Replicate | `https://replicate.com/blog/rss` |
| 🟡 도구 | NVIDIA Dev | `https://developer.nvidia.com/blog/feed` |

---

## 🖥️ 대시보드 기능

- **오늘의 AI**: 카테고리 필터, 실시간 검색, 중요도 태그
- **주간 리포트**: 분야별 차트, 핵심 키워드 히트맵, TOP 5 논문/도구, TXT 다운로드
- **월간 인사이트**: 소스별 누적 차트, 키워드 TOP 20, 추천 기사 TOP 10
- **다크/라이트 모드** 토글
- **완전 반응형** (모바일/태블릿/데스크탑)

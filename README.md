# AI 트렌드 대시보드

실제 RSS 피드를 자동 수집하는 AI 트렌드 대시보드입니다.

## 📁 저장 구조 (B방식)

```
data/
├── ai_news.json           ← 오늘 데이터 (대시보드 기본)
├── history/
│   ├── 2026-03-17.json    ← 날짜별 스냅샷 (무한 누적)
│   ├── 2026-03-18.json
│   └── ...
├── weekly.json            ← 최근 7일 집계 (매일 자동 갱신)
└── monthly.json           ← 최근 30일 집계 (매일 자동 갱신)
```

## 🚀 GitHub 배포 방법

1. GitHub에서 `ai-pulse` 퍼블릭 저장소 생성
2. 이 폴더 파일을 모두 push
3. **Settings → Actions → General → Read and write permissions** 설정
4. **Actions 탭 → Run workflow** 클릭 (첫 데이터 생성)
5. **Settings → Pages → Branch: main / root** 설정

## 📡 수집 소스 (20개)

### 🇰🇷 국내
- AI타임스, 바이라인네트워크, 디지털투데이, 전자신문, 더에이아이

### 🎬 영상AI
- Replicate Blog, NVIDIA Dev Blog

### 🎨 디자인AI
- HuggingFace Blog

### 📄 논문
- ArXiv AI (cs.AI), ArXiv ML (cs.LG), ArXiv CV (cs.CV), ArXiv CL (cs.CL)

### 💻 개발AI
- OpenAI, Google AI Blog, DeepMind, LangChain Blog, MarkTechPost

### 📊 비즈니스
- VentureBeat AI, MIT Tech Review, AI Business

## ⏰ 자동 스케줄

- **일간 수집**: 매일 07:00 KST → `data/history/YYYY-MM-DD.json` + `data/ai_news.json`
- **주간 집계**: 자동 생성 → `data/weekly.json` (최근 7일)
- **월간 집계**: 자동 생성 → `data/monthly.json` (최근 30일)

## 📊 탭 구성

| 탭 | 데이터 소스 | 주요 기능 |
|---|---|---|
| 오늘의 AI | `ai_news.json` | 뉴스 카드, 필터, 검색, 오늘 요약 |
| 주간 리포트 | `weekly.json` | 일별 타임라인, 카테고리 바차트, TOP5 목록 |
| 월간 인사이트 | `monthly.json` | 누적 트렌드 라인차트, 소스 순위, 키워드 히트맵 |

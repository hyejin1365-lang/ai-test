#!/usr/bin/env python3
"""
AI 트렌드 — RSS + 블로그 크롤링 수집 스크립트 v13

변경 사항 (v11):
  1. 핵심 포인트: 헤드라인 카피 → 원문 인사이트 서술문
  2. 해외 기사 one_line_kr: 영어 one_line 한국어 번역 (배치)
  3. 이미지·디자인AI 소스 추가 (Leonardo AI, Canva AI, DALL-E News 등)
  4. 블로그 크롤링 날짜 추출 개선 (상위 컨테이너 time 태그 탐색)
  5. 주간/월간 집계에 content_highlights, cat_highlights 추가
"""

import json, feedparser, requests, re, os, glob, asyncio
try:
    from google import genai as _genai_mod
    _GENAI_AVAILABLE = True
except ImportError:
    _GENAI_AVAILABLE = False
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from bs4 import BeautifulSoup

KST     = timezone(timedelta(hours=9))
NOW_KST = datetime.now(KST)
TODAY   = NOW_KST.strftime("%Y-%m-%d")

SCRAPE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

# ── 카테고리 순서 ──────────────────────────────────────
CATEGORY_ORDER = [
    "콘텐츠",         # 한국 미디어
    "영상AI",         # 영상 생성 AI
    "이미지·디자인AI", # 이미지/디자인 통합
    "LLM",            # 거대언어모델
    "개발AI",         # 개발 도구·프레임워크
    "AI법률",         # AI 법률·규제·정책
    "논문",           # ArXiv / 학술 (수집은 하되 필터 탭 없음)
    "비즈니스",       # 뉴스·인사이트 (수집은 하되 필터 탭 없음)
]

# ── Google News RSS 헬퍼 ──────────────────────────────
def gnews(query, limit=5):
    q = requests.utils.quote(query)
    return {
        "url":   f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en",
        "limit": limit,
        "badge": "gnews",
        "lang":  "en",
    }

# ── RSS 피드 목록 ──────────────────────────────────────
RSS_FEEDS = [

    # ══════════════════════════════════════════════════
    # 🇰🇷  콘텐츠 — 한국 AI 미디어
    # ══════════════════════════════════════════════════
    {"name":"AI타임스",
     "url":"https://www.aitimes.com/rss/allArticle.xml",
     "category":"콘텐츠","badge":"kr-news","lang":"ko","limit":10},
    {"name":"바이라인네트워크",
     "url":"https://byline.network/feed/",
     "category":"콘텐츠","badge":"kr-news","lang":"ko","limit":7},
    {"name":"디지털투데이",
     "url":"https://www.digitaltoday.co.kr/rss/allArticle.xml",
     "category":"콘텐츠","badge":"kr-news","lang":"ko","limit":7},
    {"name":"전자신문",
     "url":"http://rss.etnews.com/Section901.xml",
     "category":"콘텐츠","badge":"kr-news","lang":"ko","limit":7},
    {"name":"더에이아이",
     "url":"http://www.newstheai.com/rss/allArticle.xml",
     "category":"콘텐츠","badge":"kr-news","lang":"ko","limit":6},

    # ══════════════════════════════════════════════════
    # 🎬  영상AI — Runway · Sora · Pika · Kling · Luma
    # ══════════════════════════════════════════════════
    # Sora / OpenAI 공식
    {"name":"OpenAI (Sora)",
     "url":"https://openai.com/news/rss.xml",
     "category":"영상AI","badge":"official","lang":"en","limit":5},
    # Kling AI
    {**gnews("Kling AI video generation Kuaishou", 4),
     "name":"Kling AI News","category":"영상AI"},
    # Luma AI
    {**gnews("Luma AI Dream Machine Ray2", 4),
     "name":"Luma AI News","category":"영상AI"},
    # Replicate 공식 블로그
    {"name":"Replicate Blog",
     "url":"https://replicate.com/blog/rss",
     "category":"영상AI","badge":"tool","lang":"en","limit":4},
    # TechCrunch AI
    {"name":"TechCrunch AI",
     "url":"https://techcrunch.com/category/artificial-intelligence/feed/",
     "category":"영상AI","badge":"news","lang":"en","limit":5},

    # ★ Adobe Premiere / After Effects AI 기능
    {**gnews("Adobe Premiere Pro After Effects AI feature update", 4),
     "name":"Adobe Video AI News","category":"영상AI"},
    # ★ DaVinci Resolve AI (Blackmagic)
    {**gnews("DaVinci Resolve AI feature Blackmagic update", 4),
     "name":"DaVinci Resolve AI","category":"영상AI"},
    # ★ CapCut AI 영상 편집
    {**gnews("CapCut AI video editing feature new", 4),
     "name":"CapCut AI News","category":"영상AI"},
    # ★ YouTube Creator AI 도구
    {**gnews("YouTube AI creator tools auto dubbing captions feature", 4),
     "name":"YouTube Creator AI","category":"영상AI"},
    # ★ Descript (팟캐스트/영상 편집 AI)
    {**gnews("Descript AI video podcast editing update", 3),
     "name":"Descript AI News","category":"영상AI"},
    # ★ HeyGen (AI 아바타 영상)
    {**gnews("HeyGen AI avatar video generation update", 4),
     "name":"HeyGen AI News","category":"영상AI"},
    # ★ Synthesia (AI 기업 영상)
    {**gnews("Synthesia AI video avatar presenter", 3),
     "name":"Synthesia AI News","category":"영상AI"},

    # ══════════════════════════════════════════════════
    # 🖼️  이미지·디자인AI — Midjourney · Flux · Stability · Leonardo · Canva
    # ══════════════════════════════════════════════════
    # Midjourney 공식 업데이트 피드
    {"name":"Midjourney Updates",
     "url":"https://updates.midjourney.com/feed",
     "category":"이미지·디자인AI","badge":"official","lang":"en","limit":6},
    # Midjourney 뉴스
    {**gnews("Midjourney AI image generation new features", 5),
     "name":"Midjourney News","category":"이미지·디자인AI"},
    # Flux (Black Forest Labs)
    {**gnews("Flux AI image generation Black Forest Labs", 4),
     "name":"Flux AI News","category":"이미지·디자인AI"},
    # Ideogram
    {**gnews("Ideogram AI image generator update", 4),
     "name":"Ideogram News","category":"이미지·디자인AI"},
    # Adobe Firefly
    {**gnews("Adobe Firefly AI generative image update", 4),
     "name":"Adobe Firefly News","category":"이미지·디자인AI"},
    # Leonardo AI ★ 신규 추가
    {**gnews("Leonardo AI image generation art", 4),
     "name":"Leonardo AI News","category":"이미지·디자인AI"},
    # DALL-E / OpenAI 이미지 ★ 신규 추가
    {**gnews("DALL-E OpenAI image generation API", 3),
     "name":"DALL-E News","category":"이미지·디자인AI"},
    # Canva AI ★ 신규 추가
    {**gnews("Canva AI Magic Studio design tool", 3),
     "name":"Canva AI News","category":"이미지·디자인AI"},
    # ComfyUI / Stable Diffusion 커뮤니티 ★ 신규 추가
    {**gnews("ComfyUI Stable Diffusion image generation", 3),
     "name":"ComfyUI News","category":"이미지·디자인AI"},

    # ★ Figma AI (디자인 AI 기능 공식 업데이트)
    {**gnews("Figma AI design features update new", 5),
     "name":"Figma AI News","category":"이미지·디자인AI"},
    # HuggingFace 공식 블로그
    {"name":"HuggingFace Blog",
     "url":"https://huggingface.co/blog/feed.xml",
     "category":"이미지·디자인AI","badge":"official","lang":"en","limit":5},
    # HuggingFace Daily Papers
    {"name":"HuggingFace Papers",
     "url":"https://papers.takara.ai/api/feed",
     "category":"이미지·디자인AI","badge":"paper","lang":"en","limit":5},

    # ══════════════════════════════════════════════════
    # 🧠  LLM — Anthropic · Mistral · Perplexity · DeepSeek · Meta · Gemini · Grok
    # ══════════════════════════════════════════════════
    {**gnews("Mistral AI LLM open source model", 5),
     "name":"Mistral AI News","category":"LLM"},
    {**gnews("Perplexity AI search LLM update", 4),
     "name":"Perplexity News","category":"LLM"},
    {**gnews("DeepSeek AI model open source release", 5),
     "name":"DeepSeek News","category":"LLM"},
    {**gnews("Meta AI Llama model open source", 5),
     "name":"Meta AI News","category":"LLM"},
    {**gnews("Google Gemini AI model update", 5),
     "name":"Google Gemini News","category":"LLM"},
    {**gnews("Grok xAI Elon Musk language model", 4),
     "name":"xAI Grok News","category":"LLM"},
    {"name":"OpenAI Blog",
     "url":"https://openai.com/blog/rss.xml",
     "category":"LLM","badge":"official","lang":"en","limit":5},
    {"name":"Simon Willison",
     "url":"https://simonwillison.net/atom/entries/",
     "category":"LLM","badge":"official","lang":"en","limit":5},
    {"name":"Import AI",
     "url":"https://importai.substack.com/feed",
     "category":"LLM","badge":"news","lang":"en","limit":4},

    # Claude 공식 릴리스 노트 (Anthropic 블로그 RSS)
    {"name":"Anthropic News",
     "url":"https://www.anthropic.com/rss.xml",
     "category":"LLM","badge":"official","lang":"en","limit":5},
    # Claude 관련 Google News
    {**gnews("Claude AI Anthropic new feature release update", 5),
     "name":"Claude AI News","category":"LLM"},

    # ══════════════════════════════════════════════════
    # 💻  개발AI — 개발 도구·프레임워크
    # ══════════════════════════════════════════════════
    {"name":"Google AI Blog",
     "url":"http://googleaiblog.blogspot.com/atom.xml",
     "category":"개발AI","badge":"official","lang":"en","limit":4},
    {"name":"DeepMind",
     "url":"https://deepmind.google/blog/rss.xml",
     "category":"개발AI","badge":"official","lang":"en","limit":4},
    {"name":"LangChain Blog",
     "url":"https://blog.langchain.dev/rss/",
     "category":"개발AI","badge":"official","lang":"en","limit":4},
    {"name":"Together AI Blog",
     "url":"https://www.together.ai/blog/rss.xml",
     "category":"개발AI","badge":"official","lang":"en","limit":4},
    {"name":"Weights & Biases",
     "url":"https://wandb.ai/fully-connected/rss.xml",
     "category":"개발AI","badge":"official","lang":"en","limit":4},
    {"name":"Latent Space",
     "url":"https://www.latent.space/feed",
     "category":"개발AI","badge":"news","lang":"en","limit":4},
    {"name":"MarkTechPost",
     "url":"https://www.marktechpost.com/feed/",
     "category":"개발AI","badge":"news","lang":"en","limit":5},
    {"name":"Bloomberg Tech",
     "url":"https://feeds.bloomberg.com/technology/news.rss",
     "category":"개발AI","badge":"news","lang":"en","limit":4},
    {"name":"Wired AI",
     "url":"https://www.wired.com/feed/rss",
     "category":"개발AI","badge":"news","lang":"en","limit":4},

    # ══════════════════════════════════════════════════
    # 📄  논문 — ArXiv (수집 O / 필터탭 X)
    # ══════════════════════════════════════════════════
    {"name":"ArXiv AI",
     "url":"https://rss.arxiv.org/rss/cs.AI",
     "category":"논문","badge":"paper","lang":"en","limit":8},
    {"name":"ArXiv ML",
     "url":"https://rss.arxiv.org/rss/cs.LG",
     "category":"논문","badge":"paper","lang":"en","limit":6},
    {"name":"ArXiv CV",
     "url":"https://rss.arxiv.org/rss/cs.CV",
     "category":"논문","badge":"paper","lang":"en","limit":5},
    {"name":"ArXiv CL",
     "url":"https://rss.arxiv.org/rss/cs.CL",
     "category":"논문","badge":"paper","lang":"en","limit":5},

    # ══════════════════════════════════════════════════
    # ⚖️  AI법률 — AI 법률·규제·정책 (수집 O / 필터탭 O)
    # ══════════════════════════════════════════════════
    {"name":"AI법률 뉴스(국내)",
     "url":"https://news.google.com/rss/search?q=AI+%EB%B2%95%EB%A5%A0+%EA%B7%9C%EC%A0%9C+%EC%A0%95%EC%B1%85&hl=ko&gl=KR&ceid=KR:ko",
     "category":"AI법률","badge":"gnews","lang":"ko","limit":6},
    {**gnews("AI regulation law policy EU act 2025 2026", 5),
     "name":"AI Regulation News","category":"AI법률"},
    {**gnews("artificial intelligence copyright law lawsuit ruling", 4),
     "name":"AI Copyright Law","category":"AI법률"},
    {**gnews("AI ethics governance policy government", 4),
     "name":"AI Policy News","category":"AI법률"},

    # ══════════════════════════════════════════════════
    # 📊  비즈니스 — 뉴스·인사이트 (수집 O / 필터탭 X)
    # ══════════════════════════════════════════════════
    {"name":"VentureBeat AI",
     "url":"https://venturebeat.com/category/ai/feed/",
     "category":"비즈니스","badge":"news","lang":"en","limit":5},
    {"name":"MIT Tech Review",
     "url":"https://www.technologyreview.com/feed/",
     "category":"비즈니스","badge":"news","lang":"en","limit":4},
    {"name":"AI Business",
     "url":"https://aibusiness.com/rss.xml",
     "category":"비즈니스","badge":"news","lang":"en","limit":4},
    {"name":"Last Week in AI",
     "url":"https://lastweekin.ai/feed",
     "category":"비즈니스","badge":"news","lang":"en","limit":4},
    {"name":"The Sequence",
     "url":"https://thesequence.substack.com/feed",
     "category":"비즈니스","badge":"news","lang":"en","limit":3},
    {"name":"Ahead of AI",
     "url":"https://magazine.sebastianraschka.com/feed",
     "category":"비즈니스","badge":"news","lang":"en","limit":3},
]

# ── 키워드 ─────────────────────────────────────────────
HOT_KEYWORDS = [
    "gpt","llm","agent","에이전트","multimodal","멀티모달","diffusion",
    "transformer","claude","gemini","llama","reasoning","추론","생성형",
    "video generation","image generation","rag","fine-tuning","파인튜닝",
    "benchmark","open source","오픈소스","인공지능","딥러닝","chatgpt",
    "sora","runway","midjourney","stable diffusion","flux","pika","luma","kling",
    "grok","mistral","phi","qwen","deepseek","딥시크","elevenlabs","perplexity",
    "anthropic","ideogram","adobe firefly","leonardo","dall-e","canva",
    "claude","figma","capcut","heygen","synthesia","descript",
    "AI법률","AI규제","저작권","규제","정책","davinci resolve","premiere",
    "content creator","video editing","영상편집","콘텐츠 제작","youtube ai",
]
KR_AI_KEYWORDS = [
    "인공지능","AI","머신러닝","딥러닝","챗봇","생성형","자연어",
    "이미지 생성","영상 생성","클로드","제미나이","챗GPT","라마",
    "LLM","에이전트","파운데이션 모델","딥시크","미드저니",
    "runway","sora","pika","플럭스","레오나르도",
    "클로드","피그마","캡컷","AI규제","AI법률","저작권","영상편집",
]

BADGE_LABEL_MAP = {
    "gnews":    "뉴스집계",
    "paper":    "논문",
    "official": "공식",
    "news":     "뉴스",
    "tool":     "도구",
    "kr-news":  "국내",
    "crawled":  "공식블로그",
}

# ─────────────────────────────────────────────────────
# 유틸 함수
# ─────────────────────────────────────────────────────
def clean_html(text):
    if not text: return ""
    t = re.sub(r'<[^>]+>', '', text)
    for r, s in [('&amp;','&'),('&lt;','<'),('&gt;','>'),
                 ('&nbsp;',' '),('&#8216;',"'"),('&#8217;',"'"),
                 ('&#8220;','"'),('&#8221;','"')]:
        t = t.replace(r, s)
    t = re.sub(r'\s+', ' ', t).strip()
    return t[:280] + "…" if len(t) > 280 else t

def one_line_summary(text, max_len=120):
    """
    본문 전체를 한 줄로 압축 요약 (extractive).
    - 수치·기업명·기능명이 포함된 문장 우선
    - 여러 문장이면 핵심 문장 1개 선택 후 max_len 내로 압축
    """
    if not text:
        return ""
    text = clean_html(text)
    # 문장 분리 (한/영 공통)
    sents = re.split(r'(?<=[.!?다요됨음])\s+', text)
    sents = [s.strip() for s in sents if len(s.strip()) > 12]
    if not sents:
        return (text[:max_len].rstrip() + "…") if len(text) > max_len else text

    # 핵심 문장 점수: 수치·기업명·기능명 포함 여부
    SIGNAL_PATS = [
        r'\d+[%억만원달러]',          # 수치
        r'(?:출시|출범|공개|발표|도입|업데이트|업그레이드|런칭|launch|release|introduce|announc)',
        r'(?:신규|새로운|처음|최초|first|new feature|now available)',
        r'(?:AI|LLM|GPT|Claude|Gemini|Sora|Runway|Midjourney|Figma|CapCut)',
    ]
    def score(s):
        sc = 0
        for p in SIGNAL_PATS:
            if re.search(p, s, re.IGNORECASE):
                sc += 1
        # 너무 짧거나 너무 긴 문장 페널티
        if len(s) < 20: sc -= 1
        if len(s) > 200: sc -= 1
        return sc

    best = max(sents, key=score)
    if len(best) <= max_len:
        return best
    # max_len 초과 시 자연스럽게 자르기
    truncated = best[:max_len].rsplit(' ', 1)[0]
    return truncated + "…"

def is_ai_related(title, summary, lang):
    if lang != "ko": return True
    text = (title + " " + summary).lower()
    return any(kw.lower() in text for kw in KR_AI_KEYWORDS)

# 신규 기능/플랫폼 출시 감지 패턴
LAUNCH_PATTERNS = [
    r'(?:출시|출범|런칭|공개|선보|새롭게|새로운 기능|신규 기능|업데이트)',
    r'(?:launch(?:es|ed)?|release[sd]?|introduc(?:es|ed|ing)|announc(?:es|ed|ing))',
    r'(?:now available|just released|new feature|new model|new tool)',
    r'(?:unveil[s]?|debut[s]?|roll[s]? out|ship[s]?)',
]

def get_importance(title, summary=""):
    text = (title + " " + summary).lower()
    n = sum(1 for kw in HOT_KEYWORDS if kw in text)

    # ★ 신규 기능/플랫폼 출시 → hot 우선 승격
    is_launch = any(re.search(p, title + " " + summary, re.IGNORECASE)
                    for p in LAUNCH_PATTERNS)
    if is_launch and n >= 1:
        return {"label":"🔥 핫",  "class":"hot"}

    if n >= 3: return {"label":"🔥 핫",  "class":"hot"}
    if n >= 1: return {"label":"⭐ 추천","class":"star"}
    return       {"label":"🆕 신규","class":"new"}

# ─────────────────────────────────────────────────────
# ★ 시간 파싱 (원문 timezone 우선)
# ─────────────────────────────────────────────────────
def parse_date_kst(entry, lang='en'):
    """
    RSS 날짜 → KST 변환
    ① raw 문자열에 timezone 정보가 있으면 정확히 변환
    ② timezone 없으면 한국어 피드(lang=ko)는 이미 KST로 간주
    ③ 영어 피드 timezone 없으면 UTC 가정 후 KST 변환
    """
    for attr in ('published', 'updated'):
        raw = getattr(entry, attr, None)
        if not raw:
            continue
        # RFC 2822 형식 (e.g., "Mon, 17 Mar 2026 04:01:00 +0000")
        try:
            dt = parsedate_to_datetime(raw)
            return dt.astimezone(KST).strftime("%Y-%m-%d %H:%M")
        except Exception:
            pass
        # ISO 8601 형식
        try:
            dt = datetime.fromisoformat(raw.replace('Z', '+00:00'))
            if dt.tzinfo is None:
                tz = KST if lang == 'ko' else timezone.utc
                dt = dt.replace(tzinfo=tz)
            return dt.astimezone(KST).strftime("%Y-%m-%d %H:%M")
        except Exception:
            pass

    # feedparser parsed struct
    for attr in ('published_parsed', 'updated_parsed'):
        t = getattr(entry, attr, None)
        if t:
            try:
                if lang == 'ko':
                    dt = datetime(*t[:6], tzinfo=KST)
                else:
                    dt = datetime(*t[:6], tzinfo=timezone.utc).astimezone(KST)
                return dt.strftime("%Y-%m-%d %H:%M")
            except Exception:
                pass

    return NOW_KST.strftime("%Y-%m-%d %H:%M")

def get_thumbnail(entry):
    if getattr(entry, 'media_thumbnail', None):
        return entry.media_thumbnail[0].get('url', '')
    for enc in getattr(entry, 'enclosures', []):
        if 'image' in enc.get('type', ''):
            return enc.get('url', '')
    body = (getattr(entry, 'summary', '') or
            (entry.content[0].get('value', '') if getattr(entry, 'content', None) else ''))
    m = re.search(r'<img[^>]+src=["\'](https?:[^"\']+)["\']', body)
    if m: return m.group(1)
    return ""

# ─────────────────────────────────────────────────────
# ★ 번역 기능 (해외 기사 → 한국어)
# ─────────────────────────────────────────────────────
_translator = None


# ─────────────────────────────────────────────────────
# ★ Gemini AI 클라이언트 (요약 + 번역)
# ─────────────────────────────────────────────────────
_gemini_client = None
_GEMINI_MODEL  = "gemini-2.5-flash"   # 무료 티어 지원 모델 (250 RPD)

def get_gemini_client():
    """Gemini 클라이언트 반환. GEMINI_API_KEY 없으면 None."""
    global _gemini_client
    if _gemini_client is not None:
        return _gemini_client
    if not _GENAI_AVAILABLE:
        return None
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        print("  ⚠️  GEMINI_API_KEY 환경변수 없음 — deep-translator로 fallback")
        return None
    try:
        _gemini_client = _genai_mod.Client(api_key=api_key)
        return _gemini_client
    except Exception as e:
        print(f"  ⚠️  Gemini 클라이언트 초기화 실패: {e}")
        return None


def fetch_article_body(url: str, max_chars: int = 2000) -> str:
    """
    기사 URL에서 본문 텍스트 추출 (BeautifulSoup).
    실패하거나 본문이 짧으면 빈 문자열 반환.
    """
    try:
        r = requests.get(
            url, timeout=4,
            headers={"User-Agent": "Mozilla/5.0 (compatible; AIPulseBot/1.0)"},
            allow_redirects=True
        )
        if r.status_code != 200:
            return ""
        soup = BeautifulSoup(r.text, "lxml")
        # 불필요 태그 제거
        for tag in soup(["script", "style", "nav", "header", "footer",
                          "aside", "form", "noscript", "iframe"]):
            tag.decompose()
        # 본문 후보 태그 순서대로 시도
        body = ""
        for selector in ["article", "main", '[class*="post-content"]',
                          '[class*="article-body"]', '[class*="entry-content"]',
                          '[class*="content"]']:
            el = soup.select_one(selector)
            if el:
                body = el.get_text(separator=" ", strip=True)
                break
        if not body:
            body = " ".join(p.get_text(strip=True) for p in soup.find_all("p"))
        body = re.sub(r"\s+", " ", body).strip()
        return body[:max_chars] if len(body) > 100 else ""
    except Exception:
        return ""


def ai_summarize_batch(items: list, client) -> int:
    """
    Gemini API로 기사 목록을 일괄 요약.
    - 영어 기사: title_kr(번역) + one_line_kr(AI 요약) 생성
    - 국문 기사: one_line_kr(AI 요약)만 생성, title_kr 불필요
    - 전체 기사 원문 크롤링 시도, 실패 시 RSS summary fallback
    - RPM 초과 방지: 건당 3초 간격(RPM 여유 충분), 429 시 최대 3회 재시도
    반환값: 성공 건수
    """
    import time as _time
    import json as _json

    if not client:
        return 0

    SLEEP_INTERVAL = 3     # 건당 대기(초) — RPM=10, 74건×3초=222초 여유
    MAX_RETRY      = 3     # 429 시 최대 재시도 횟수
    RETRY_BASE     = 15    # 재시도 초기 대기(초), 지수 백오프

    ok = 0
    for idx, it in enumerate(items, 1):
        lang  = it.get("lang", "en")
        title = it.get("title", "")
        summ  = clean_html(it.get("summary", "") or "")

        # ── 원문: 병렬 사전 크롤링 캐시 우선, 없으면 RSS summary fallback ──
        body = it.get("_body", "")
        source_text = body if len(body) > 200 else summ
        if not source_text:
            source_text = title

        # ── 언어별 프롬프트 분기 ──
        if lang == "ko":
            # 국문 기사: 제목은 이미 한국어이므로 번역 불필요, 요약만 생성
            prompt = f"""다음 AI 기사의 핵심을 한 문장으로 요약하세요.

제목: {title}
본문/요약: {source_text[:1500]}

출력 형식 (JSON만, 설명 없이):
{{
  "one_line_kr": "본문 전체의 핵심 내용을 한국어로 한 문장 요약. 신규 기능·수치·회사명을 반드시 포함. 60자 이내. 마침표로 끝낼 것."
}}"""
        else:
            # 영어 기사: 제목 번역 + 내용 요약 동시 생성
            prompt = f"""다음 AI 기사를 분석하세요.

제목(영어): {title}
본문/요약: {source_text[:1500]}

출력 형식 (JSON만, 설명 없이):
{{
  "title_kr": "제목을 자연스러운 한국어로 번역 (50자 이내)",
  "one_line_kr": "본문 전체 핵심을 한국어로 한 문장 요약. 신규 기능·수치·회사명 포함. 60자 이내. 마침표로 끝낼 것."
}}"""

        # ── 재시도 루프 ──
        for attempt in range(MAX_RETRY):
            try:
                resp = client.models.generate_content(
                    model=_GEMINI_MODEL,
                    contents=prompt,
                )
                raw = resp.text.strip()
                m = re.search(r"\{[\s\S]*?\}", raw)
                if m:
                    data = _json.loads(m.group())
                    it["one_line_kr"] = data.get("one_line_kr", "").strip()[:120]
                    if lang != "ko":
                        it["title_kr"] = data.get("title_kr", "").strip()[:80]
                    ok += 1
                break  # 성공 시 재시도 루프 탈출

            except Exception as e:
                err = str(e)
                if "429" in err or "RESOURCE_EXHAUSTED" in err:
                    wait = RETRY_BASE * (2 ** attempt)   # 15 → 30 → 60초
                    print(f"  ⚠️  RPM 한도({idx}번째): {wait}초 대기 후 재시도...")
                    _time.sleep(wait)
                else:
                    # 429 이외 오류는 재시도 안 함
                    break

        # ── 건당 대기 (RPM 초과 방지) ──
        if idx < len(items):
            _time.sleep(SLEEP_INTERVAL)

    return ok


def get_translator():
    global _translator
    if _translator is None:
        try:
            from deep_translator import GoogleTranslator
            _translator = GoogleTranslator(source='auto', target='ko')
        except ImportError:
            _translator = False
    return _translator if _translator else None

def translate_to_ko(text, max_len=180):
    """영어 텍스트 → 한국어 번역. 실패 시 원문 반환."""
    if not text: return ""
    translator = get_translator()
    if not translator: return text
    try:
        return translator.translate(text[:max_len]) or text
    except Exception:
        return text

def batch_translate_items(items):
    """
    전체 기사(영어+국문) AI 요약 처리.
    - 영어: Gemini로 title_kr(번역) + one_line_kr(AI 요약)
    - 국문: Gemini로 one_line_kr(AI 요약)만, title_kr 불필요
    - Fallback: 영어→deep-translator 번역, 국문→one_line 그대로 복사
    우선순위: hot → star → new, 오늘 기사 우선
    """
    # ── 필드 초기화 ──
    for it in items:
        if "title_kr" not in it:    it["title_kr"]    = ""
        if "one_line_kr" not in it: it["one_line_kr"] = ""

    # ── 대상 선정: 영어 + 국문 모두, hot→star→new 순 ──
    def _priority_key(it):
        cls = it.get("importance", {}).get("class", "new")
        return {"hot": 0, "star": 1, "new": 2}.get(cls, 3)

    all_targets = sorted(items, key=_priority_key)

    # 오늘 기사 우선 + 이미 요약된 기사 제외 (재처리 방지 → 실행시간 단축)
    today_first = [i for i in all_targets if i.get("date", "")[:10] == TODAY]
    rest        = [
        i for i in all_targets
        if i not in today_first and not i.get("one_line_kr", "").strip()
    ]
    targets     = (today_first + rest)[:200]  # 최대 200건 (한도 250 여유분 확보)
    target_ids  = {it.get("id", it.get("url")) for it in targets}

    ko_targets = [i for i in targets if i.get("lang") == "ko"]
    en_targets = [i for i in targets if i.get("lang") == "en"]
    today_cnt  = len([i for i in targets if i.get("date", "")[:10] == TODAY])
    print(f"  🌐 AI 요약 대상: 총 {len(targets)}건 (국문 {len(ko_targets)} / 영문 {len(en_targets)} / 오늘 {today_cnt}건)")

    # ── ① Gemini AI 요약 시도 (영어+국문 전체) ──
    gemini_ok = 0
    gemini_client = get_gemini_client()
    if gemini_client:
        print(f"  🤖 Gemini AI 요약 시작... (국문 {len(ko_targets)}건 포함)")
        gemini_ok = ai_summarize_batch(targets, gemini_client)
        print(f"  ✅ Gemini 완료: {gemini_ok}건")

    # ── ② Fallback 처리 ──
    needs_fallback_en = [
        it for it in en_targets
        if not it.get("one_line_kr")
    ]
    needs_fallback_ko = [
        it for it in ko_targets
        if not it.get("one_line_kr")
    ]

    # 영어 fallback: deep-translator 번역
    if needs_fallback_en:
        translator = get_translator()
        if translator:
            print(f"  🔄 영어 Fallback: {len(needs_fallback_en)}건 (deep-translator)")
            for it in needs_fallback_en:
                if not it.get("title_kr"):
                    it["title_kr"]    = translate_to_ko(it.get("title", "")[:120])
                if not it.get("one_line_kr"):
                    src = it.get("one_line", "") or it.get("title", "")
                    it["one_line_kr"] = translate_to_ko(src)

    # 국문 fallback: one_line 그대로 복사 (이미 한국어)
    if needs_fallback_ko:
        print(f"  🔄 국문 Fallback: {len(needs_fallback_ko)}건 (one_line 복사)")
        for it in needs_fallback_ko:
            it["one_line_kr"] = it.get("one_line", "") or it.get("title", "")

    # ── 미처리 항목 보장 ──
    for it in items:
        if it.get("id", it.get("url")) not in target_ids:
            if not it.get("one_line_kr"):
                it["one_line_kr"] = it.get("one_line", "") or it.get("title", "")

    total_ok = sum(1 for i in targets if i.get("one_line_kr"))
    en_ok    = sum(1 for i in en_targets if i.get("title_kr") and i.get("one_line_kr"))
    ko_ok    = sum(1 for i in ko_targets if i.get("one_line_kr"))
    print(f"  📊 완료: 영문 {en_ok}/{len(en_targets)}건 (번역+요약) / 국문 {ko_ok}/{len(ko_targets)}건 (요약)")

# ─────────────────────────────────────────────────────
# ★ 블로그 크롤러 (RSS 없는 공식 플랫폼)
# ─────────────────────────────────────────────────────
BLOG_CONFIGS = [
    # ── Runway 공식 블로그 ─────────────────────────────
    {
        "name":     "Runway Blog",
        "base_url": "https://runwayml.com",
        "list_url": "https://runwayml.com/blog",
        "category": "영상AI",
        "badge":    "crawled",
        "lang":     "en",
        "limit":    5,
        "link_pattern": r"^(?:news/|/news/)",
        "link_base": "https://runwayml.com/",
    },
    # ── Anthropic 공식 뉴스 ───────────────────────────
    {
        "name":     "Anthropic Blog",
        "base_url": "https://www.anthropic.com",
        "list_url": "https://www.anthropic.com/news",
        "category": "LLM",
        "badge":    "crawled",
        "lang":     "en",
        "limit":    5,
        "link_pattern": r"^/news/[a-z]",
        "link_base": "https://www.anthropic.com",
    },
    # ── Stability AI 뉴스 ─────────────────────────────
    {
        "name":     "Stability AI Blog",
        "base_url": "https://stability.ai",
        "list_url": "https://stability.ai/news",
        "category": "이미지·디자인AI",
        "badge":    "crawled",
        "lang":     "en",
        "limit":    5,
        "link_pattern": r"^/news/[a-z]",
        "link_base": "https://stability.ai",
    },
    # ── ElevenLabs 공식 블로그 ────────────────────────
    {
        "name":     "ElevenLabs Blog",
        "base_url": "https://elevenlabs.io",
        "list_url": "https://elevenlabs.io/blog",
        "category": "영상AI",
        "badge":    "crawled",
        "lang":     "en",
        "limit":    5,
        "link_pattern": r"^/blog/[a-z]",
        "link_base": "https://elevenlabs.io",
    },
    # ── Pika Labs 블로그 ──────────────────────────────
    {
        "name":     "Pika Blog",
        "base_url": "https://pika.art",
        "list_url": "https://pika.art/blog",
        "category": "영상AI",
        "badge":    "crawled",
        "lang":     "en",
        "limit":    5,
        "link_pattern": r"^/blog/[a-z]",
        "link_base": "https://pika.art",
    },
    # ── Figma 공식 블로그 (AI 기능 업데이트) ★ 신규 ──
    {
        "name":     "Figma Blog",
        "base_url": "https://www.figma.com",
        "list_url": "https://www.figma.com/blog/",
        "category": "이미지·디자인AI",
        "badge":    "crawled",
        "lang":     "en",
        "limit":    5,
        "link_pattern": r"^/blog/[a-z0-9]",
        "link_base": "https://www.figma.com",
    },
    # ── HeyGen 공식 블로그 ★ 신규 ─────────────────────
    {
        "name":     "HeyGen Blog",
        "base_url": "https://www.heygen.com",
        "list_url": "https://www.heygen.com/blog",
        "category": "영상AI",
        "badge":    "crawled",
        "lang":     "en",
        "limit":    5,
        "link_pattern": r"^/blog/[a-z0-9]",
        "link_base": "https://www.heygen.com",
    },
]

def _find_time_in_container(element, depth=5):
    """링크 태그로부터 상위 컨테이너를 탐색하며 <time> 태그 검색"""
    # 1) 링크 내부 먼저
    t = element.find("time")
    if t: return t
    # 2) 상위 컨테이너 탐색
    node = element.parent
    for _ in range(depth):
        if not node: break
        t = node.find("time")
        if t: return t
        node = node.parent
    return None

def scrape_blog(cfg):
    """공식 블로그 크롤링 → 아이템 리스트 반환"""
    items = []
    try:
        resp = requests.get(cfg["list_url"], headers=SCRAPE_HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")

        seen_hrefs = set()
        count = 0
        for a in soup.find_all("a", href=True):
            if count >= cfg["limit"]:
                break
            href = a.get("href", "").strip()
            if not re.match(cfg["link_pattern"], href):
                continue
            # 절대 URL로 변환
            if href.startswith("/"):
                full_url = cfg["link_base"].rstrip("/") + href
            elif href.startswith("http"):
                full_url = href
            else:
                full_url = cfg["link_base"].rstrip("/") + "/" + href.lstrip("/")

            if full_url in seen_hrefs:
                continue
            seen_hrefs.add(full_url)

            # 제목 추출
            title_el = a.find(["h1","h2","h3","h4","h5"])
            if title_el:
                title = title_el.get_text(strip=True)
            else:
                direct_texts = [t.strip() for t in a.find_all(string=True, recursive=False) if t.strip()]
                title = direct_texts[0] if direct_texts else ''
                if not title:
                    first = a.find(string=True)
                    title = first.strip() if first else ''
            title = re.sub(r'\s+', ' ', title)[:120].strip()
            # 네비게이션 필터
            if len(title) < 15 or (len(title.split()) == 1 and title[0].isupper()):
                continue

            # ★ 날짜 추출 개선: 상위 컨테이너에서 <time> 탐색
            date_str = ""
            time_el = _find_time_in_container(a, depth=6)
            if time_el:
                # datetime 속성 우선, 없으면 텍스트
                date_str = time_el.get("datetime", "") or time_el.get_text(strip=True)
            if not date_str:
                # 텍스트에서 날짜 패턴 검색
                text_block = a.get_text(" ", strip=True)
                m = re.search(
                    r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2},? \d{4}',
                    text_block, re.IGNORECASE
                )
                if m:
                    date_str = m.group(0)

            kst_date = _parse_scraped_date(date_str)

            # ★ 날짜 필터: 오늘 날짜 기사만 수집 (날짜 추출 실패 → 제외)
            if kst_date is None:
                print(f"    ↳ 날짜 없음 제외: {title[:40]}")
                continue
            if kst_date[:10] != TODAY:
                print(f"    ↳ 날짜 불일치 제외({kst_date[:10]}): {title[:40]}")
                continue

            # 요약
            summary = ""
            parent = a.parent
            if parent:
                p_el = parent.find("p")
                if p_el:
                    summary = clean_html(p_el.get_text(strip=True))

            items.append({
                "id":           f"{abs(hash(title+full_url))%999999:06d}",
                "title":        title,
                "summary":      summary,
                "one_line":     one_line_summary(summary or title),
                "one_line_kr":  "",   # 이후 배치 번역에서 채움
                "url":          full_url,
                "source":       cfg["name"],
                "category":     cfg["category"],
                "badge":        cfg["badge"],
                "lang":         cfg["lang"],
                "date":         kst_date,
                "collect_date": TODAY,
                "thumbnail":    "",
                "importance":   get_importance(title, summary),
            })
            count += 1

        print(f"  ✅ {cfg['name']} (크롤링): {count}건")
    except Exception as e:
        print(f"  ❌ {cfg['name']} (크롤링): {e}")
    return items


def _parse_scraped_date(raw: str) -> str:
    """크롤링으로 얻은 날짜 문자열을 KST 형식으로 변환"""
    if not raw:
        return NOW_KST.strftime("%Y-%m-%d %H:%M")
    # ISO 8601 (시간 포함)
    try:
        dt = datetime.fromisoformat(raw.replace('Z', '+00:00'))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(KST).strftime("%Y-%m-%d %H:%M")
    except Exception:
        pass
    # 텍스트 날짜 (예: "March 11, 2026" or "Mar 11, 2026")
    MONTHS = {
        "jan":1,"feb":2,"mar":3,"apr":4,"may":5,"jun":6,
        "jul":7,"aug":8,"sep":9,"oct":10,"nov":11,"dec":12
    }
    m = re.search(
        r'(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]* (\d{1,2}),? (\d{4})',
        raw, re.IGNORECASE
    )
    if m:
        month = MONTHS.get(m.group(1).lower()[:3], 1)
        day   = int(m.group(2))
        year  = int(m.group(3))
        dt = datetime(year, month, day, tzinfo=timezone.utc).astimezone(KST)
        return dt.strftime("%Y-%m-%d %H:%M")
    return None  # 날짜 추출 실패 → None 반환 (필터에서 제외)

# ─────────────────────────────────────────────────────
# RSS 수집
# ─────────────────────────────────────────────────────

async def _fetch_feed_async(session, feed_info):
    """단일 RSS 피드 비동기 fetch."""
    try:
        async with session.get(
            feed_info["url"],
            headers=SCRAPE_HEADERS,
            timeout=aiohttp.ClientTimeout(total=20),
            ssl=False,
        ) as resp:
            text = await resp.text()
    except Exception as e:
        print(f"  ⚠️  RSS 피드 오류 [{feed_info['name']}]: {type(e).__name__}: {e}")
        return []
    import feedparser as _fp
    feed  = _fp.parse(text)
    count = 0
    lang  = feed_info.get("lang", "en")
    items = []
    for entry in feed.entries:
        if count >= feed_info["limit"]: break
        title   = clean_html(entry.get("title", "제목 없음"))
        link    = entry.get("link", "#")
        raw_summary = (
            entry.get("summary", "") or
            (entry.content[0].get("value", "") if getattr(entry, "content", None) else "")
        )
        summary = clean_html(raw_summary)
        if not is_ai_related(title, summary, lang): continue
        item_date = parse_date_kst(entry, lang)
        # ★ 오늘 날짜 기사만 수집 (어제 이전 기사 제외)
        if item_date[:10] != TODAY:
            continue
        items.append({
            "id":           f"{abs(hash(title+link))%999999:06d}",
            "title":        title,
            "summary":      summary,
            "one_line":     one_line_summary(summary or title),
            "one_line_kr":  "",
            "url":          link,
            "source":       feed_info["name"],
            "category":     feed_info["category"],
            "badge":        feed_info["badge"],
            "lang":         lang,
            "date":         item_date,
            "collect_date": TODAY,
            "thumbnail":    get_thumbnail(entry),
            "importance":   get_importance(title, summary),
        })
        count += 1
    return items


async def _fetch_article_async(session, item):
    """단일 기사 본문 비동기 fetch."""
    url = item.get("url", "")
    if not url:
        return
    try:
        async with session.get(
            url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; AIPulseBot/1.0)"},
            timeout=aiohttp.ClientTimeout(total=4),
            ssl=False,
        ) as resp:
            if resp.status != 200:
                return
            text = await resp.text()
    except Exception:
        return
    from bs4 import BeautifulSoup as _BS
    soup = _BS(text, "lxml")
    for tag in soup(["script","style","nav","header","footer","aside","form","noscript","iframe"]):
        tag.decompose()
    body = ""
    for selector in ["article","main",'[class*="post-content"]',
                      '[class*="article-body"]','[class*="entry-content"]','[class*="content"]']:
        el = soup.select_one(selector)
        if el:
            body = el.get_text(separator=" ", strip=True)
            break
    if not body:
        body = " ".join(p.get_text(strip=True) for p in soup.find_all("p"))
    import re as _re
    body = _re.sub(r"\s+", " ", body).strip()
    if len(body) > 200:
        item["_body"] = body[:2000]


async def fetch_all_rss_async(feeds):
    """전체 RSS 피드 병렬 수집 (10개씩 세마포어)."""
    import aiohttp as _aio
    sem = asyncio.Semaphore(10)
    async def _bounded(session, feed):
        async with sem:
            items = await _fetch_feed_async(session, feed)
            if items:
                print(f"  📰 {feed['name']}: {len(items)}건")
            return items
    async with _aio.ClientSession() as session:
        tasks = [_bounded(session, f) for f in feeds]
        results = await asyncio.gather(*tasks, return_exceptions=True)
    all_items = []
    err_count = 0
    for i, r in enumerate(results):
        if isinstance(r, list):
            all_items.extend(r)
        elif isinstance(r, Exception):
            err_count += 1
            print(f"  ❌ RSS gather 오류 [{feeds[i]['name']}]: {type(r).__name__}: {r}")
    if err_count:
        print(f"  ⚠️  gather 수준 오류 합계: {err_count}건")
    return all_items


async def fetch_all_bodies_async(items):
    """전체 기사 본문 병렬 크롤링 (8개씩 세마포어)."""
    import aiohttp as _aio
    sem = asyncio.Semaphore(8)
    async def _bounded(session, item):
        async with sem:
            await _fetch_article_async(session, item)
    async with _aio.ClientSession() as session:
        tasks = [_bounded(session, it) for it in items]
        await asyncio.gather(*tasks, return_exceptions=True)


def fetch_feed(feed_info):
    items = []
    try:
        resp = requests.get(
            feed_info["url"],
            headers=SCRAPE_HEADERS,
            timeout=5,
        )
        resp.raise_for_status()
        feed  = feedparser.parse(resp.text)
        count = 0
        lang  = feed_info.get("lang", "en")
        for entry in feed.entries:
            if count >= feed_info["limit"]: break
            title   = clean_html(entry.get("title", "제목 없음"))
            link    = entry.get("link", "#")
            raw_summary = (
                entry.get("summary", "") or
                (entry.content[0].get("value", "") if getattr(entry, "content", None) else "")
            )
            summary = clean_html(raw_summary)
            if not is_ai_related(title, summary, lang): continue
            items.append({
                "id":           f"{abs(hash(title+link))%999999:06d}",
                "title":        title,
                "summary":      summary,
                "one_line":     one_line_summary(summary or title),
                "one_line_kr":  "",  # 이후 배치 번역
                "url":          link,
                "source":       feed_info["name"],
                "category":     feed_info["category"],
                "badge":        feed_info["badge"],
                "lang":         lang,
                "date":         item_date,
                "collect_date": TODAY,
                "thumbnail":    get_thumbnail(entry),
                "importance":   get_importance(title, summary),
            })
            count += 1
        status = f"{count}건"
        if count == 0:
            status = "0건 (AI 관련 없거나 빈 피드)"
        print(f"  ✅ {feed_info['name']}: {status}")
    except Exception as e:
        print(f"  ❌ {feed_info['name']}: {e}")
    return items

# ─────────────────────────────────────────────────────
# 집계
# ─────────────────────────────────────────────────────
EXTRACT_KEYWORDS = [
    "LLM","Agent","에이전트","RAG","GPT","Claude","클로드","Gemini","제미나이",
    "Llama","라마","Diffusion","Multimodal","멀티모달","Fine-tuning","파인튜닝",
    "Transformer","Reasoning","추론","Vision","Benchmark","Open Source","오픈소스",
    "Video AI","Image Generation","이미지 생성","생성형 AI","DeepSeek","딥시크",
    "Sora","Runway","Midjourney","Stable Diffusion","Flux","Pika","Luma","Kling",
    "인공지능","ChatGPT","Grok","Mistral","Phi","Qwen","ElevenLabs",
    "Anthropic","Perplexity","Ideogram","Adobe Firefly","Leonardo","DALL-E","Canva AI",
    "Together AI","ComfyUI",
]

def extract_keywords(items):
    freq = {}
    for item in items:
        text = (item["title"] + " " + item["summary"]).lower()
        for kw in EXTRACT_KEYWORDS:
            if kw.lower() in text:
                freq[kw] = freq.get(kw, 0) + 1
    return [{"keyword":k,"count":v}
            for k,v in sorted(freq.items(), key=lambda x:-x[1])[:20]]

def make_stats(items):
    cat, src = {}, {}
    for it in items:
        cat[it["category"]] = cat.get(it["category"],0)+1
        src[it["source"]]   = src.get(it["source"],0)+1
    ordered_cat = {k:cat[k] for k in CATEGORY_ORDER if k in cat}
    sorted_src  = [{"source":k,"count":v}
                   for k,v in sorted(src.items(), key=lambda x:-x[1])]
    return ordered_cat, sorted_src

# ─────────────────────────────────────────────────────
# ★ 핵심 포인트 — 구체적·실용적 인사이트 서술문 (v9)
# ─────────────────────────────────────────────────────

# 출처 태그 제거 패턴: [디지털투데이 AI리포터], [연합뉴스] 등
_SOURCE_TAG_RE = re.compile(r'^\[[^\]]{1,40}\]\s*')

def _strip_source_tag(text: str) -> str:
    """[출처명] 형태 태그 제거"""
    return _SOURCE_TAG_RE.sub('', text).strip()

def _extract_first_sentence(text: str, max_len: int = 130) -> str:
    """
    텍스트에서 첫 완결 서술 문장 추출 (v10).
    - 출처 태그 제거
    - 서술형 완결 문장 우선 (발표했다, 공개했다 등)
    - 짧은 의문문은 건너뛰고 더 구체적인 문장 찾기
    """
    text = _strip_source_tag(text)
    if not text:
        return ""

    # ① 서술형 완결 문장 우선 탐색
    stmt_endings = ['발표했다.', '공개했다.', '밝혔다.', '출시했다.', '나섰다.',
                    '됩니다.', '했습니다.', '됐다.', '체결했다.', '선보였다.',
                    '이다.', '었다.', '였다.']
    for ending in stmt_endings:
        idx = text.find(ending)
        if 12 < idx <= max_len:
            return text[:idx + len(ending)].strip()

    # ② 마침표 + 공백
    m = re.search(r'.{12,}?[.。]\s', text)
    if m and m.end() <= max_len + 5:
        candidate = text[:m.end()].strip()
        # 너무 짧은 문장(의문문)이면 다음 서술문 찾기
        if len(candidate) < 22:
            m2 = re.search(r'.{20,}?[.。]\s', text[m.end():])
            if m2 and (m.end() + m2.end()) <= max_len + 20:
                return text[:m.end() + m2.end()].strip()
        return candidate

    # ③ 단순 마침표
    idx = text.find('.')
    if 15 < idx <= max_len:
        return text[:idx + 1].strip()

    # ④ 길이 제한 (완결 문장 우선)
    if len(text) > max_len:
        for sep in ['다.', '습니다.', '이다.', '했다.']:
            ridx = text[:max_len].rfind(sep)
            if ridx > 15:
                return text[:ridx + len(sep)].strip()
        return text[:max_len].rstrip() + '.'

    return text.rstrip()


def _finalize(text: str) -> str:
    """
    최종 후처리:
    - 말줄임표 → 완결 문장으로 정리
    - 문장 끝 마침표 보장
    - 출처 태그 재차 제거
    """
    if not text:
        return ""
    text = _strip_source_tag(text.strip())

    # 말줄임으로 끝나는 경우 → 마지막 완결 문장 찾기
    if text.endswith('…') or text.endswith('...'):
        for sep in ['다.', '했다.', '됩니다.', '습니다.', '이다.', '었다.', '였다.']:
            idx = text.rfind(sep)
            if idx > 15:
                return text[:idx + len(sep)].strip()
        text = re.sub(r'[…\.]+$', '', text).strip() + '.'

    # 문장 미완결 보정
    if text and not text[-1] in ('.', '!', '?', '다', '요', '됨', '음'):
        text = text + '.'

    return text


def make_key_point(item) -> str:
    """
    뉴스 아이템 → 구체적·실용적 인사이트 한 줄 서술문 (v10)

    원칙:
    1. 수치·기업명·기능명 등 구체적 팩트 포함
    2. summary에서 핵심 첫 문장 추출 + 출처태그 완전 제거
    3. 영어 기사는 one_line_kr → title 한국어화 순서로
    4. 말줄임 없는 완결 문장
    5. "~는 방법", "~할 수 있습니다" 등 번역 어체 보정
    """
    title   = item.get("title", "").strip()
    summary = item.get("summary", "").strip()
    lang    = item.get("lang", "en")

    if lang == "ko":
        # ① summary에서 구체적 첫 문장 추출 (출처 태그 이중 제거)
        if summary and len(summary) > 20:
            clean_sum = _strip_source_tag(summary)
            sent = _extract_first_sentence(clean_sum, max_len=130)
            if sent and len(sent) > 15:
                return _finalize(_strip_source_tag(sent))

        # ② summary가 짧거나 없으면 title 사용
        title_clean = _strip_source_tag(title)
        return _finalize(title_clean)

    else:
        # ① 번역된 one_line_kr (출처 태그 제거)
        kr = _strip_source_tag(item.get("one_line_kr", "").strip())
        # 번역 어체 자연스럽게 보정
        if kr and len(kr) > 10:
            # "~는 방법" 형태 → "~을 설명한다" 형태
            kr = re.sub(r'하는 방법\.$', '하는 방법을 공개했다.', kr)
            kr = re.sub(r'을 사용할 수 있습니다\.$', '을 API로 제공한다.', kr)
            kr = re.sub(r'할 수 있습니다\.$', '한다.', kr)
            return _finalize(kr)

        # ② summary 앞부분 추출 후 번역
        if summary and len(summary) > 20:
            # arxiv 헤더 제거
            clean_sum = re.sub(r'^arXiv:\S+\s+Announce Type:[^\n]*\n?', '', summary)
            clean_sum = re.sub(r'^Abstract:\s*', '', clean_sum).strip()
            snippet = clean_sum[:150].split(". ")[0].strip()
            if snippet and len(snippet) > 20:
                translated = translate_to_ko(snippet[:130])
                if translated and len(translated) > 10 and translated != snippet:
                    return _finalize(translated)

        # ③ title 번역 (구체 키워드 보존)
        title_kr = translate_to_ko(title[:90])
        return _finalize(title_kr) if title_kr and title_kr != title else _finalize(title)


def build_daily_summary(items, keywords):
    # ★ 오늘 날짜 기사만 인사이트/요약에 사용
    today_items = [i for i in items if (i.get("date") or "").startswith(TODAY)]
    # 오늘 기사가 너무 적으면 collect_date 기준 fallback
    if len(today_items) < 3:
        today_items = [i for i in items if (i.get("collect_date") or "") == TODAY]
    if len(today_items) == 0:
        today_items = items  # 최후 fallback

    kr   = sum(1 for i in today_items if i.get("lang")=="ko")
    cats = {c: sum(1 for i in today_items if i["category"]==c) for c in CATEGORY_ORDER}
    top_cat = max((c for c in CATEGORY_ORDER if cats.get(c,0)>0),
                  key=lambda c: cats[c], default="-")
    top_kws = [k["keyword"] for k in keywords[:7]]

    cat_lines = [f"{c} {cats[c]}건" for c in CATEGORY_ORDER if cats.get(c,0)>0]
    kw_str    = " · ".join(top_kws[:5]) if top_kws else "-"

    hot   = [i for i in today_items if i["importance"]["class"]=="hot"]
    star  = [i for i in today_items if i["importance"]["class"]=="star"]
    hot_items  = hot[:3]
    hot_titles = ""
    if hot_items:
        hot_titles = " 특히 " + "、".join(f"'{h['title'][:30]}'" for h in hot_items[:2]) + " 등이 주목받았습니다."

    prose = (
        f"오늘({NOW_KST.strftime('%m월 %d일')}) {len(today_items)}건의 AI 뉴스가 업데이트됐습니다. "
        f"국내 기사 {kr}건, 해외 기사 {len(today_items)-kr}건이며 "
        f"오늘의 핵심 키워드는 {kw_str}로, {top_cat} 분야에서 가장 많은 활동이 관측됐습니다."
        f"{hot_titles}"
    )

    # ★ 핵심 포인트 5개: 한국어 우선 + 중요도 정렬 + 소스 중복 제외
    NON_INSIGHT_CATS = {"논문", "비즈니스"}
    IMP_ORDER = {"hot": 0, "star": 1, "new": 2}

    def kp_priority_key(x):
        imp = IMP_ORDER.get(x["importance"]["class"], 2)
        is_ko = 0 if x.get("lang") == "ko" else 1
        return (imp, is_ko)

    kp_candidates = sorted(
        [i for i in today_items if i["category"] not in NON_INSIGHT_CATS],
        key=kp_priority_key
    )
    seen_kp_src = set()
    key_point_items = []
    for it in kp_candidates:
        if len(key_point_items) >= 5:
            break
        src = it["source"]
        if src in seen_kp_src:
            continue
        seen_kp_src.add(src)
        key_point_items.append(it)

    key_points = [make_key_point(it) for it in key_point_items[:5]]

    return {
        "date":            NOW_KST.strftime("%Y년 %m월 %d일"),
        "total":           len(today_items),
        "kr_count":        kr,
        "en_count":        len(today_items)-kr,
        "top_keywords":    top_kws,
        "top_category":    top_cat,
        "category_counts": cats,
        "hot_picks":       [{"title":i["title"],"source":i["source"],"url":i["url"]} for i in hot_items],
        "key_points":      key_points,
        "one_line":        f"오늘 {len(items)}건 | 국내 {kr} · 해외 {len(items)-kr} | 핫 키워드: {', '.join(top_kws[:3])}",
        "prose":           prose,
    }

# ─────────────────────────────────────────────────────
# 누적 집계 (주간·월간)
# ─────────────────────────────────────────────────────

# ─────────────────────────────────────────────────────
# ★ 이전 수집 URL 로딩 (중복 제거용)
# ─────────────────────────────────────────────────────
def load_seen_urls_from_history(exclude_today=True) -> set:
    """
    data/history/*.json에서 이미 수집된 URL 집합을 반환.
    오늘 파일은 제외 (exclude_today=True).
    """
    history_dir = "data/history"
    seen_urls = set()
    if not os.path.isdir(history_dir):
        return seen_urls
    for fpath in glob.glob(f"{history_dir}/*.json"):
        # 오늘 파일 제외
        if exclude_today and os.path.basename(fpath) == f"{TODAY}.json":
            continue
        try:
            with open(fpath, encoding="utf-8") as f:
                data = json.load(f)
            for item in data.get("items", []):
                url = item.get("url", "")
                if url:
                    seen_urls.add(url)
        except Exception:
            pass
    return seen_urls

def load_history_items(days: int) -> list:
    history_dir = "data/history"
    all_items, seen_ids = [], set()
    files = sorted(glob.glob(f"{history_dir}/*.json"), reverse=True)[:days]
    for fpath in files:
        try:
            with open(fpath, encoding="utf-8") as f:
                data = json.load(f)
            for item in data.get("items", []):
                uid = item.get("url") or item.get("id")
                if uid and uid not in seen_ids:
                    seen_ids.add(uid)
                    all_items.append(item)
        except Exception as e:
            print(f"  ⚠️ {fpath} 읽기 실패: {e}")
    return all_items

def build_period_json(items, period_label, days):
    """
    ★ v7: content_highlights, cat_highlights, rising_keywords 추가
    수집량 중심 → 내용 중심 데이터 제공
    """
    cat_stats, src_stats = make_stats(items)
    keywords = extract_keywords(items)
    kr = sum(1 for i in items if i.get("lang")=="ko")

    daily_counts = {}
    for it in items:
        d = it.get("collect_date","")
        if d: daily_counts[d] = daily_counts.get(d,0)+1
    daily_timeline = [{"date":k,"count":v} for k,v in sorted(daily_counts.items())]

    cat_daily = {}
    for it in items:
        d, cat = it.get("collect_date",""), it.get("category","")
        if d and cat:
            cat_daily.setdefault(d,{})
            cat_daily[d][cat] = cat_daily[d].get(cat,0)+1

    # ★ 핵심 하이라이트: hot/star 기사 상위 10개
    hot   = [i for i in items if i.get("importance",{}).get("class")=="hot"]
    star  = [i for i in items if i.get("importance",{}).get("class")=="star"]
    priority = hot + star
    seen_u, highlights = set(), []
    for it in priority:
        url = it.get("url","")
        if url and url not in seen_u:
            seen_u.add(url); highlights.append(it)
        if len(highlights) >= 10: break

    # ★ 카테고리별 대표 소식 (hot/star 우선, 논문·비즈니스 제외)
    MAIN_CATS = ["콘텐츠","영상AI","이미지·디자인AI","LLM","개발AI"]
    cat_highlights = {}
    for cat in MAIN_CATS:
        cat_items = [i for i in priority if i.get("category")==cat]
        if not cat_items:
            cat_items = [i for i in items if i.get("category")==cat]
        if cat_items:
            cat_highlights[cat] = {
                "title":  cat_items[0]["title"],
                "source": cat_items[0]["source"],
                "url":    cat_items[0].get("url",""),
                "one_line": cat_items[0].get("one_line_kr") or cat_items[0].get("one_line",""),
                "date":   cat_items[0].get("date",""),
            }

    # ★ 이번 기간 핵심 5포인트 생성
    key_points_items = highlights[:5] if highlights else items[:5]
    period_key_points = [make_key_point(it) for it in key_points_items]

    # ★ 주간/월간 요약 문장
    top_kws = [k["keyword"] for k in keywords[:5]]
    kw_str = ", ".join(top_kws) if top_kws else "-"
    top_cat = max(cat_stats.items(), key=lambda x:x[1])[0] if cat_stats else "-"
    period_name = "주간" if period_label == "weekly" else "월간"
    period_prose = (
        f"이번 {period_name} 총 {len(items)}건의 AI 자료가 수집됐습니다. "
        f"국내 {kr}건, 해외 {len(items)-kr}건이며 "
        f"{top_cat} 분야에서 가장 활발한 활동이 관측됐습니다. "
        f"주요 키워드는 {kw_str}입니다."
    )

    return {
        "period":             period_label,
        "days":               days,
        "generated_at":       NOW_KST.strftime("%Y-%m-%d %H:%M"),
        "total":              len(items),
        "kr_count":           kr,
        "en_count":           len(items)-kr,
        "category_stats":     cat_stats,
        "source_stats":       src_stats,
        "keywords":           keywords,
        "daily_timeline":     daily_timeline,
        "cat_daily":          cat_daily,
        "content_highlights": highlights,          # ★ 핵심 기사 목록
        "cat_highlights":     cat_highlights,       # ★ 카테고리별 대표
        "period_key_points":  period_key_points,    # ★ 기간 핵심 포인트
        "period_prose":       period_prose,          # ★ 기간 요약 문장
        "items":              items,
    }

# ─────────────────────────────────────────────────────
# 메인
# ─────────────────────────────────────────────────────
def main():
    print(f"\n{'='*60}")
    print(f"  AI 트렌드 뉴스 수집 v13 — {TODAY}")
    print(f"  실행 시각: {NOW_KST.strftime('%Y-%m-%d %H:%M')} KST")
    print(f"  RSS 소스: {len(RSS_FEEDS)}개 / 블로그 크롤러: {len(BLOG_CONFIGS)}개")
    print(f"{'='*60}\n")

    today_items = []

    # 1) RSS 수집 (병렬 aiohttp)
    print("── RSS 수집 (병렬) ───────────────────────────")
    rss_items = asyncio.run(fetch_all_rss_async(RSS_FEEDS))
    today_items.extend(rss_items)
    print(f"  ✅ RSS 총 {len(rss_items)}건 수집 완료")

    # 2) 블로그 크롤링
    print("\n── 공식 블로그 크롤링 ────────────────────────")
    for cfg in BLOG_CONFIGS:
        print(f"🌐 [{cfg['category']}] {cfg['name']} 크롤링 중...")
        today_items.extend(scrape_blog(cfg))

    # 3) URL 중복 제거 (동일 실행 내에서만 — history 중복 체크 제거)
    # ★ history 중복 체크를 하지 않음: 날짜 필터(RSS/블로그)로 이미 오늘 기사만 수집됨
    # history 중복 체크를 켜면 RSS 기사가 어제와 겹쳐 0건이 되는 문제가 있었음
    print("\n── 중복 제거 (동일 실행 내) ──────────────────────")
    seen, deduped = set(), []
    for it in today_items:
        url = it["url"]
        if url not in seen:
            seen.add(url)
            deduped.append(it)
    skip_dup = len(today_items) - len(deduped)
    today_items = deduped
    print(f"  ✅ 동일 URL 중복 제거: {skip_dup}건 | 최종: {len(today_items)}건")

    # 4) 카테고리 순서 정렬
    today_items.sort(
        key=lambda x: CATEGORY_ORDER.index(x["category"])
        if x["category"] in CATEGORY_ORDER else 99
    )
    for i, item in enumerate(today_items):
        item["id"] = f"{TODAY}_{i:04d}"
        if not item.get("one_line"):
            item["one_line"] = one_line_summary(item.get("summary","") or item.get("title",""))

    # 5) ★ 전체 기사 AI 요약 (영어+국문)
    print("\n── 원문 병렬 크롤링 ──────────────────────────────")
    asyncio.run(fetch_all_bodies_async(today_items))
    prefetched = sum(1 for i in today_items if i.get("_body",""))
    print(f"  ✅ 원문 크롤링: {prefetched}/{len(today_items)}건 성공")
    print("\n── AI 요약 처리 (영어 번역+요약 / 국문 요약) ──────")
    batch_translate_items(today_items)

    kr_cnt = sum(1 for i in today_items if i.get("lang")=="ko")
    print(f"\n오늘 수집: {len(today_items)}건 (국내 {kr_cnt} / 해외 {len(today_items)-kr_cnt})")

    keywords             = extract_keywords(today_items)
    cat_stats, src_stats = make_stats(today_items)
    daily_summary        = build_daily_summary(today_items, keywords)

    # 6) 저장
    os.makedirs("data/history", exist_ok=True)
    today_output = {
        "generated_at":   NOW_KST.strftime("%Y-%m-%d %H:%M"),
        "date":           TODAY,
        "total":          len(today_items),
        "items":          today_items,
        "keywords":       keywords,
        "category_stats": cat_stats,
        "source_stats":   src_stats,
        "daily_summary":  daily_summary,
    }

    with open("data/ai_news.json", "w", encoding="utf-8") as f:
        json.dump(today_output, f, ensure_ascii=False, indent=2)
    print("✅ data/ai_news.json 저장")

    hist_path = f"data/history/{TODAY}.json"
    with open(hist_path, "w", encoding="utf-8") as f:
        json.dump(today_output, f, ensure_ascii=False, indent=2)
    print(f"✅ {hist_path} 저장")

    # 7) 주간·월간 집계
    print("\n📊 주간 집계 생성 중...")
    weekly_items = load_history_items(7)
    with open("data/weekly.json", "w", encoding="utf-8") as f:
        json.dump(build_period_json(weekly_items, "weekly", 7), f, ensure_ascii=False, indent=2)
    print(f"✅ data/weekly.json 저장 ({len(weekly_items)}건)")

    print("📊 월간 집계 생성 중...")
    monthly_items = load_history_items(30)
    with open("data/monthly.json", "w", encoding="utf-8") as f:
        json.dump(build_period_json(monthly_items, "monthly", 30), f, ensure_ascii=False, indent=2)
    print(f"✅ data/monthly.json 저장 ({len(monthly_items)}건)")

    # 8) 결과 요약
    print(f"\n{'='*60}")
    print(f"✅ 완료!")
    print(f"   카테고리: {list(cat_stats.keys())}")
    print(f"   핫 키워드: {[k['keyword'] for k in keywords[:7]]}")
    print(f"   핵심 포인트 (인사이트 서술문):")
    for pt in daily_summary.get("key_points", []):
        print(f"     • {pt}")
    print(f"   카테고리별 분포:")
    for cat, cnt in cat_stats.items():
        bar = "█" * min(cnt // 2, 20)
        print(f"     {cat:12s} {cnt:4d}건  {bar}")

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
AI 트렌드 — RSS + 블로그 크롤링 수집 스크립트 v6

변경 사항:
  - RSS 없는 플랫폼(Anthropic, Runway, Stability AI, ElevenLabs 등)
    공식 블로그 직접 크롤링 추가
  - 시간 파싱 개선: 원문 timezone 정보를 최우선으로 사용
  - 핵심 포인트 5개 자동 생성 (daily_summary.key_points)
  - 카테고리 개편: 이미지AI + 디자인AI → 이미지·디자인AI

저장 구조:
  data/
  ├── ai_news.json          ← 오늘 데이터
  ├── history/YYYY-MM-DD.json
  ├── weekly.json
  └── monthly.json
"""

import json, feedparser, requests, re, os, glob
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
    "콘텐츠",        # 한국 미디어
    "영상AI",        # 영상 생성 AI
    "이미지·디자인AI", # 이미지/디자인 통합
    "LLM",           # 거대언어모델
    "개발AI",        # 개발 도구·프레임워크
    "논문",          # ArXiv / 학술 (수집은 하되 필터 탭 없음)
    "비즈니스",      # 뉴스·인사이트 (수집은 하되 필터 탭 없음)
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

    # ══════════════════════════════════════════════════
    # 🖼️  이미지·디자인AI — Midjourney · Flux · Stability
    # ══════════════════════════════════════════════════
    # Midjourney 공식 업데이트 피드
    {"name":"Midjourney Updates",
     "url":"https://updates.midjourney.com/feed",
     "category":"이미지·디자인AI","badge":"official","lang":"en","limit":6},
    # Midjourney 뉴스
    {**gnews("Midjourney AI image generation", 5),
     "name":"Midjourney News","category":"이미지·디자인AI"},
    # Flux (Black Forest Labs)
    {**gnews("Flux AI image generation Black Forest Labs", 4),
     "name":"Flux AI News","category":"이미지·디자인AI"},
    # Ideogram
    {**gnews("Ideogram AI image generator", 4),
     "name":"Ideogram News","category":"이미지·디자인AI"},
    # Adobe Firefly
    {**gnews("Adobe Firefly AI generative image", 4),
     "name":"Adobe Firefly News","category":"이미지·디자인AI"},
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
    # Mistral AI
    {**gnews("Mistral AI LLM open source", 5),
     "name":"Mistral AI News","category":"LLM"},
    # Perplexity
    {**gnews("Perplexity AI search LLM", 4),
     "name":"Perplexity News","category":"LLM"},
    # DeepSeek
    {**gnews("DeepSeek AI model open source", 5),
     "name":"DeepSeek News","category":"LLM"},
    # Meta AI / Llama
    {**gnews("Meta AI Llama model open source", 5),
     "name":"Meta AI News","category":"LLM"},
    # Google Gemini
    {**gnews("Google Gemini AI model", 5),
     "name":"Google Gemini News","category":"LLM"},
    # xAI / Grok
    {**gnews("Grok xAI Elon Musk language model", 4),
     "name":"xAI Grok News","category":"LLM"},
    # OpenAI GPT 블로그
    {"name":"OpenAI Blog",
     "url":"https://openai.com/blog/rss.xml",
     "category":"LLM","badge":"official","lang":"en","limit":5},
    # Simon Willison
    {"name":"Simon Willison",
     "url":"https://simonwillison.net/atom/entries/",
     "category":"LLM","badge":"official","lang":"en","limit":5},
    # Import AI 뉴스레터
    {"name":"Import AI",
     "url":"https://importai.substack.com/feed",
     "category":"LLM","badge":"news","lang":"en","limit":4},

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
    "anthropic","ideogram","adobe firefly",
]
KR_AI_KEYWORDS = [
    "인공지능","AI","머신러닝","딥러닝","챗봇","생성형","자연어",
    "이미지 생성","영상 생성","클로드","제미나이","챗GPT","라마",
    "LLM","에이전트","파운데이션 모델","딥시크","미드저니",
    "runway","sora","pika","플럭스",
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

def one_line_summary(text, max_len=90):
    """본문/제목에서 한 줄 요약 추출"""
    if not text:
        return ""
    # 첫 문장 or 첫 max_len 글자
    text = clean_html(text)
    for sep in ['. ', '.\n', '. \n', '。']:
        idx = text.find(sep)
        if 10 < idx < max_len:
            return text[:idx + 1].strip()
    return (text[:max_len].rstrip() + "…") if len(text) > max_len else text

def is_ai_related(title, summary, lang):
    if lang != "ko": return True
    text = (title + " " + summary).lower()
    return any(kw.lower() in text for kw in KR_AI_KEYWORDS)

def get_importance(title, summary=""):
    text = (title + " " + summary).lower()
    n = sum(1 for kw in HOT_KEYWORDS if kw in text)
    if n >= 3: return {"label":"🔥 핫",  "class":"hot"}
    if n >= 1: return {"label":"⭐ 추천","class":"star"}
    return       {"label":"🆕 신규","class":"new"}

# ─────────────────────────────────────────────────────
# ★ 핵심 수정: 시간 파싱 (원문 timezone 우선)
# ─────────────────────────────────────────────────────
def parse_date_kst(entry, lang='en'):
    """
    RSS 날짜 → KST 변환
    ① raw 문자열에 timezone 정보가 있으면 정확히 변환
    ② timezone 없으면 한국어 피드(lang=ko)는 이미 KST로 간주
    ③ 영어 피드 timezone 없으면 UTC 가정 후 KST 변환
    """
    # 1순위: raw 문자열 파싱 (timezone 정보 포함 가능성 높음)
    for attr in ('published', 'updated'):
        raw = getattr(entry, attr, None)
        if not raw:
            continue
        # RFC 2822 형식 (e.g., "Mon, 17 Mar 2026 04:01:00 +0000")
        try:
            dt = parsedate_to_datetime(raw)
            # parsedate_to_datetime은 timezone-aware datetime 반환
            return dt.astimezone(KST).strftime("%Y-%m-%d %H:%M")
        except Exception:
            pass
        # ISO 8601 형식 (e.g., "2026-03-17T04:01:00+00:00" or "2026-03-17T04:01:00Z")
        try:
            dt = datetime.fromisoformat(raw.replace('Z', '+00:00'))
            if dt.tzinfo is None:
                # timezone 없음: 언어에 따라 판단
                tz = KST if lang == 'ko' else timezone.utc
                dt = dt.replace(tzinfo=tz)
            return dt.astimezone(KST).strftime("%Y-%m-%d %H:%M")
        except Exception:
            pass

    # 2순위: feedparser parsed struct (timezone 정보 손실 가능)
    for attr in ('published_parsed', 'updated_parsed'):
        t = getattr(entry, attr, None)
        if t:
            try:
                if lang == 'ko':
                    # 한국 피드: timezone 없으면 KST로 간주
                    dt = datetime(*t[:6], tzinfo=KST)
                else:
                    # 영어 피드: UTC 가정
                    dt = datetime(*t[:6], tzinfo=timezone.utc).astimezone(KST)
                return dt.strftime("%Y-%m-%d %H:%M")
            except Exception:
                pass

    # 폴백: 현재 KST
    return NOW_KST.strftime("%Y-%m-%d %H:%M")

def get_thumbnail(entry):
    if getattr(entry, 'media_thumbnail', None):
        return entry.media_thumbnail[0].get('url', '')
    for enc in getattr(entry, 'enclosures', []):
        if 'image' in enc.get('type', ''):
            return enc.get('url', '')
    body = (getattr(entry, 'summary', '') or
            (entry.content[0].get('value', '') if getattr(entry, 'content', None) else ''))
    m = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', body)
    if m and m.group(1).startswith('http'): return m.group(1)
    return ""

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
]

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
            # 패턴 매칭
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

            # 제목 추출: h1~h5 우선 → 다이렉트 텍스트 노드 → 첫 번째 텍스트
            title_el = a.find(["h1","h2","h3","h4","h5"])
            if title_el:
                title = title_el.get_text(strip=True)
            else:
                # 다이렉트 텍스트 노드만 (중첩된 span/div 제외)
                direct_texts = [t.strip() for t in a.find_all(string=True, recursive=False) if t.strip()]
                title = direct_texts[0] if direct_texts else ''
                if not title:
                    first = a.find(string=True)
                    title = first.strip() if first else ''
            title = re.sub(r'\s+', ' ', title)[:120].strip()
            # 네비게이션 아이템 필터: 너무 짧거나 단일단어(Company, Affiliates 등) 제외
            if len(title) < 15 or (len(title.split()) == 1 and title[0].isupper()):
                continue

            # 날짜 추출: <time> 태그 또는 텍스트에서 날짜 패턴
            date_str = ""
            time_el = a.find("time")
            if time_el:
                date_str = time_el.get("datetime", "") or time_el.get_text(strip=True)
            if not date_str:
                # 텍스트에서 날짜 패턴 검색 (예: "March 11, 2026" 또는 "Mar 11, 2026")
                text_block = a.get_text(" ", strip=True)
                m = re.search(
                    r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2},? \d{4}',
                    text_block, re.IGNORECASE
                )
                if m:
                    date_str = m.group(0)

            # 날짜 파싱
            kst_date = _parse_scraped_date(date_str)

            # 요약: 링크 주변 <p> 태그 or 상위 div의 <p>
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
    # ISO 8601
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
    return NOW_KST.strftime("%Y-%m-%d %H:%M")

# ─────────────────────────────────────────────────────
# RSS 수집
# ─────────────────────────────────────────────────────
def fetch_feed(feed_info):
    items = []
    try:
        resp = requests.get(
            feed_info["url"],
            headers=SCRAPE_HEADERS,
            timeout=15,
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
                "url":          link,
                "source":       feed_info["name"],
                "category":     feed_info["category"],
                "badge":        feed_info["badge"],
                "lang":         lang,
                "date":         parse_date_kst(entry, lang),   # ★ lang 전달
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
    "Anthropic","Perplexity","Ideogram","Adobe Firefly","Together AI",
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
# ★ 핵심 포인트 5개 생성
# ─────────────────────────────────────────────────────
def make_key_point(item):
    """뉴스 아이템 → 한 줄 핵심 포인트 문장"""
    source = item.get("source", "")
    title  = item.get("title", "")
    lang   = item.get("lang", "en")
    cat    = item.get("category", "")

    # 카테고리별 동사 템플릿
    if "영상AI" in cat:
        action = "새로운 영상 AI 기능을 공개했다"
    elif "이미지" in cat or "디자인" in cat:
        action = "새로운 이미지 생성 기술을 선보였다"
    elif "LLM" in cat:
        action = "새 모델 또는 AI 서비스를 발표했다"
    elif "개발AI" in cat:
        action = "새로운 개발 도구·기술을 공개했다"
    elif "콘텐츠" in cat:
        action = "국내 AI 관련 주요 소식을 전했다"
    else:
        action = "AI 관련 새 소식을 발표했다"

    if lang == "ko":
        # 한국어: 제목 그대로 사용
        short = title[:55] + ("…" if len(title) > 55 else "")
        return f'{source}에 따르면 "{short}".'
    else:
        short = title[:60] + ("\u2026" if len(title) > 60 else "")
        return f"{source}는 '{short}'을 다루며 {action}."


def build_daily_summary(items, keywords):
    kr   = sum(1 for i in items if i.get("lang")=="ko")
    cats = {c: sum(1 for i in items if i["category"]==c) for c in CATEGORY_ORDER}
    top_cat = max((c for c in CATEGORY_ORDER if cats.get(c,0)>0),
                  key=lambda c: cats[c], default="-")
    top_kws = [k["keyword"] for k in keywords[:7]]

    cat_lines = [f"{c} {cats[c]}건" for c in CATEGORY_ORDER if cats.get(c,0)>0]
    kw_str    = " · ".join(top_kws[:5]) if top_kws else "-"

    hot  = [i for i in items if i["importance"]["class"]=="hot"]
    star = [i for i in items if i["importance"]["class"]=="star"]
    hot_items  = hot[:3]
    hot_titles = ""
    if hot_items:
        hot_titles = " 특히 " + "、".join(f"'{h['title'][:30]}'" for h in hot_items[:2]) + " 등이 주목받았습니다."

    prose = (
        f"오늘({NOW_KST.strftime('%m월 %d일')}) 총 {len(items)}건의 AI 자료가 수집됐습니다. "
        f"국내 기사 {kr}건, 해외 기사 {len(items)-kr}건이며 "
        f"분야별로는 {', '.join(cat_lines)}이 수집됐습니다. "
        f"오늘의 핵심 키워드는 {kw_str}로, {top_cat} 분야에서 가장 많은 활동이 관측됐습니다."
        f"{hot_titles}"
    )

    # ★ 핵심 포인트 5개: 중요도 높은 기사 + 다양한 소스
    priority_items = hot + star + [i for i in items if i["importance"]["class"] == "new"]
    seen_sources, key_point_items = set(), []
    for it in priority_items:
        if it["source"] not in seen_sources:
            seen_sources.add(it["source"])
            key_point_items.append(it)
        if len(key_point_items) >= 5:
            break
    # 부족하면 그냥 채우기
    for it in items:
        if len(key_point_items) >= 5:
            break
        if it not in key_point_items:
            key_point_items.append(it)

    key_points = [make_key_point(it) for it in key_point_items[:5]]

    return {
        "date":            NOW_KST.strftime("%Y년 %m월 %d일"),
        "total":           len(items),
        "kr_count":        kr,
        "en_count":        len(items)-kr,
        "top_keywords":    top_kws,
        "top_category":    top_cat,
        "category_counts": cats,
        "hot_picks":       [{"title":i["title"],"source":i["source"],"url":i["url"]} for i in hot_items],
        "key_points":      key_points,                # ★ 새 필드
        "one_line":        f"오늘 {len(items)}건 | 국내 {kr} · 해외 {len(items)-kr} | 핫 키워드: {', '.join(top_kws[:3])}",
        "prose":           prose,
    }

# ─────────────────────────────────────────────────────
# 누적 집계 (B방식)
# ─────────────────────────────────────────────────────
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
    return {
        "period":          period_label,
        "days":            days,
        "generated_at":    NOW_KST.strftime("%Y-%m-%d %H:%M"),
        "total":           len(items),
        "kr_count":        kr,
        "en_count":        len(items)-kr,
        "category_stats":  cat_stats,
        "source_stats":    src_stats,
        "keywords":        keywords,
        "daily_timeline":  daily_timeline,
        "cat_daily":       cat_daily,
        "items":           items,
    }

# ─────────────────────────────────────────────────────
# 메인
# ─────────────────────────────────────────────────────
def main():
    print(f"\n{'='*60}")
    print(f"  AI 트렌드 뉴스 수집 v6 — {TODAY}")
    print(f"  실행 시각: {NOW_KST.strftime('%Y-%m-%d %H:%M')} KST")
    print(f"  RSS 소스: {len(RSS_FEEDS)}개 / 블로그 크롤러: {len(BLOG_CONFIGS)}개")
    print(f"{'='*60}\n")

    today_items = []

    # 1) RSS 수집
    print("── RSS 수집 ──────────────────────────────────")
    for feed in RSS_FEEDS:
        print(f"📡 [{feed['category']}] {feed['name']} 수집 중...")
        today_items.extend(fetch_feed(feed))

    # 2) 블로그 크롤링
    print("\n── 공식 블로그 크롤링 ────────────────────────")
    for cfg in BLOG_CONFIGS:
        print(f"🌐 [{cfg['category']}] {cfg['name']} 크롤링 중...")
        today_items.extend(scrape_blog(cfg))

    # 3) URL 중복 제거
    seen, deduped = set(), []
    for it in today_items:
        if it["url"] not in seen:
            seen.add(it["url"])
            deduped.append(it)
    today_items = deduped

    # 4) 카테고리 순서 정렬
    today_items.sort(
        key=lambda x: CATEGORY_ORDER.index(x["category"])
        if x["category"] in CATEGORY_ORDER else 99
    )
    for i, item in enumerate(today_items):
        item["id"] = f"{TODAY}_{i:04d}"
        # one_line 없으면 생성
        if not item.get("one_line"):
            item["one_line"] = one_line_summary(item.get("summary","") or item.get("title",""))

    kr_cnt = sum(1 for i in today_items if i.get("lang")=="ko")
    print(f"\n오늘 수집: {len(today_items)}건 (국내 {kr_cnt} / 해외 {len(today_items)-kr_cnt})")

    keywords             = extract_keywords(today_items)
    cat_stats, src_stats = make_stats(today_items)
    daily_summary        = build_daily_summary(today_items, keywords)

    # 5) 저장
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

    # 6) 주간·월간 집계
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

    # 7) 결과 요약
    print(f"\n{'='*60}")
    print(f"✅ 완료!")
    print(f"   카테고리: {list(cat_stats.keys())}")
    print(f"   핫 키워드: {[k['keyword'] for k in keywords[:7]]}")
    print(f"   핵심 포인트:")
    for pt in daily_summary.get("key_points", []):
        print(f"     • {pt}")
    print(f"   카테고리별 분포:")
    for cat, cnt in cat_stats.items():
        bar = "█" * min(cnt // 2, 20)
        print(f"     {cat:12s} {cnt:4d}건  {bar}")

if __name__ == "__main__":
    main()

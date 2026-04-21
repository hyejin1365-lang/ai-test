#!/usr/bin/env python3
"""
AI 트렌드 — RSS + 블로그 크롤링 수집 스크립트 v12

변경 사항 (v12):
  1. gnews 27개 → 22개 제거, 공식 RSS/크롤러로 대체
  2. 공식 Changelog 소스 6개 추가
     (GitHub Changelog, Cursor, Gemini API, Mistral, OpenAI Dev Changelog, VS Code)
  3. Runway BLOG_CONFIGS link_pattern /news/ → /blog/ 수정
  4. OpenAI Blog URL 중복 수집 제거 (영상AI·LLM 양쪽에 있던 것 통합)
  5. get_importance(): 논문 카테고리 hot 캡 → 최대 star
  6. deep-translator 실패 시 Gemini API 번역 fallback 추가
  7. Bloomberg Tech / Wired AI 제거 (노이즈 비율 높음)
  8. requirements.txt 호환성 유지
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
    "콘텐츠",          # 한국 미디어
    "영상AI",          # 영상 생성 AI
    "이미지·디자인AI", # 이미지/디자인 통합
    "LLM",             # 거대언어모델
    "개발AI",          # 개발 도구·프레임워크·Changelog
    "AI법률",          # AI 법률·규제·정책
    "논문",            # ArXiv / 학술
    "비즈니스",        # 뉴스·인사이트
]

# ── RSS 피드 목록 ──────────────────────────────────────
RSS_FEEDS = [

    # ══════════════════════════════════════════════════
    # 🇰🇷  콘텐츠 — 한국 AI 미디어 (핵심 3개로 정리)
    # ══════════════════════════════════════════════════
    {"name": "AI타임스",
     "url":  "https://www.aitimes.com/rss/allArticle.xml",
     "category": "콘텐츠", "badge": "kr-news", "lang": "ko", "limit": 10},
    {"name": "더에이아이",
     "url":  "http://www.newstheai.com/rss/allArticle.xml",
     "category": "콘텐츠", "badge": "kr-news", "lang": "ko", "limit": 7},
    {"name": "바이라인네트워크",
     "url":  "https://byline.network/feed/",
     "category": "콘텐츠", "badge": "kr-news", "lang": "ko", "limit": 6},

    # ══════════════════════════════════════════════════
    # 🎬  영상AI — 공식 RSS 우선, gnews 최소화
    # ══════════════════════════════════════════════════
    # OpenAI 공식 (Sora 포함) — LLM 탭과 중복 방지: 여기선 limit 3
    {"name": "OpenAI News (영상)",
     "url":  "https://openai.com/news/rss.xml",
     "category": "영상AI", "badge": "official", "lang": "en", "limit": 3},
    # Replicate 공식 블로그 RSS
    {"name": "Replicate Blog",
     "url":  "https://replicate.com/blog/rss",
     "category": "영상AI", "badge": "tool", "lang": "en", "limit": 4},
    # TechCrunch AI — 영상/이미지 AI 뉴스 커버
    {"name": "TechCrunch AI",
     "url":  "https://techcrunch.com/category/artificial-intelligence/feed/",
     "category": "영상AI", "badge": "news", "lang": "en", "limit": 4},

    # ══════════════════════════════════════════════════
    # 🖼️  이미지·디자인AI — 공식 RSS + HuggingFace
    # ══════════════════════════════════════════════════
    # Midjourney 공식 업데이트 RSS
    {"name": "Midjourney Updates",
     "url":  "https://updates.midjourney.com/feed",
     "category": "이미지·디자인AI", "badge": "official", "lang": "en", "limit": 6},
    # Stability AI RSS
    {"name": "Stability AI Blog",
     "url":  "https://stability.ai/blog/rss.xml",
     "category": "이미지·디자인AI", "badge": "official", "lang": "en", "limit": 4},
    # HuggingFace 공식 블로그
    {"name": "HuggingFace Blog",
     "url":  "https://huggingface.co/blog/feed.xml",
     "category": "이미지·디자인AI", "badge": "official", "lang": "en", "limit": 5},
    # HuggingFace Daily Papers
    {"name": "HuggingFace Papers",
     "url":  "https://papers.takara.ai/api/feed",
     "category": "이미지·디자인AI", "badge": "paper", "lang": "en", "limit": 4},

    # ══════════════════════════════════════════════════
    # 🧠  LLM — 공식 블로그 RSS (gnews 전부 제거)
    # ══════════════════════════════════════════════════
    # Anthropic 공식 뉴스 RSS
    {"name": "Anthropic News",
     "url":  "https://www.anthropic.com/rss.xml",
     "category": "LLM", "badge": "official", "lang": "en", "limit": 6},
    # OpenAI Blog RSS (LLM 메인)
    {"name": "OpenAI Blog",
     "url":  "https://openai.com/blog/rss.xml",
     "category": "LLM", "badge": "official", "lang": "en", "limit": 6},
    # Meta AI 공식 블로그 RSS
    {"name": "Meta AI Blog",
     "url":  "https://ai.meta.com/blog/rss/",
     "category": "LLM", "badge": "official", "lang": "en", "limit": 5},
    # Simon Willison (AI 생태계 분석)
    {"name": "Simon Willison",
     "url":  "https://simonwillison.net/atom/entries/",
     "category": "LLM", "badge": "official", "lang": "en", "limit": 4},
    # Import AI 뉴스레터
    {"name": "Import AI",
     "url":  "https://importai.substack.com/feed",
     "category": "LLM", "badge": "news", "lang": "en", "limit": 4},

    # ══════════════════════════════════════════════════
    # 💻  개발AI — 공식 Changelog 중심으로 재편 (v12 핵심)
    # ══════════════════════════════════════════════════
    # ★ GitHub Changelog 공식 RSS
    {"name": "GitHub Changelog",
     "url":  "https://github.blog/changelog/feed/",
     "category": "개발AI", "badge": "official", "lang": "en", "limit": 8},
    # ★ VS Code Release Notes RSS
    {"name": "VS Code Release Notes",
     "url":  "https://code.visualstudio.com/feed.xml",
     "category": "개발AI", "badge": "official", "lang": "en", "limit": 4},
    # Google AI Blog
    {"name": "Google AI Blog",
     "url":  "http://googleaiblog.blogspot.com/atom.xml",
     "category": "개발AI", "badge": "official", "lang": "en", "limit": 4},
    # DeepMind
    {"name": "DeepMind",
     "url":  "https://deepmind.google/blog/rss.xml",
     "category": "개발AI", "badge": "official", "lang": "en", "limit": 4},
    # LangChain Blog
    {"name": "LangChain Blog",
     "url":  "https://blog.langchain.dev/rss/",
     "category": "개발AI", "badge": "official", "lang": "en", "limit": 4},
    # Together AI Blog
    {"name": "Together AI Blog",
     "url":  "https://www.together.ai/blog/rss.xml",
     "category": "개발AI", "badge": "official", "lang": "en", "limit": 3},
    # Weights & Biases
    {"name": "Weights & Biases",
     "url":  "https://wandb.ai/fully-connected/rss.xml",
     "category": "개발AI", "badge": "official", "lang": "en", "limit": 3},
    # Latent Space
    {"name": "Latent Space",
     "url":  "https://www.latent.space/feed",
     "category": "개발AI", "badge": "news", "lang": "en", "limit": 4},
    # MarkTechPost
    {"name": "MarkTechPost",
     "url":  "https://www.marktechpost.com/feed/",
     "category": "개발AI", "badge": "news", "lang": "en", "limit": 4},

    # ══════════════════════════════════════════════════
    # 📄  논문 — ArXiv
    # ══════════════════════════════════════════════════
    {"name": "ArXiv AI",
     "url":  "https://rss.arxiv.org/rss/cs.AI",
     "category": "논문", "badge": "paper", "lang": "en", "limit": 8},
    {"name": "ArXiv ML",
     "url":  "https://rss.arxiv.org/rss/cs.LG",
     "category": "논문", "badge": "paper", "lang": "en", "limit": 6},
    {"name": "ArXiv CV",
     "url":  "https://rss.arxiv.org/rss/cs.CV",
     "category": "논문", "badge": "paper", "lang": "en", "limit": 5},
    {"name": "ArXiv CL",
     "url":  "https://rss.arxiv.org/rss/cs.CL",
     "category": "논문", "badge": "paper", "lang": "en", "limit": 5},

    # ══════════════════════════════════════════════════
    # ⚖️  AI법률 — 법률·규제·정책
    # ══════════════════════════════════════════════════
    {"name": "AI법률 뉴스(국내)",
     "url":  "https://news.google.com/rss/search?q=AI+%EB%B2%95%EB%A5%A0+%EA%B7%9C%EC%A0%9C+%EC%A0%95%EC%B1%85&hl=ko&gl=KR&ceid=KR:ko",
     "category": "AI법률", "badge": "gnews", "lang": "ko", "limit": 6},
    {"name": "AI Regulation News",
     "url":  "https://news.google.com/rss/search?q=AI+regulation+law+policy+EU+act&hl=en-US&gl=US&ceid=US:en",
     "category": "AI법률", "badge": "gnews", "lang": "en", "limit": 5},
    {"name": "AI Copyright Law",
     "url":  "https://news.google.com/rss/search?q=artificial+intelligence+copyright+law+lawsuit&hl=en-US&gl=US&ceid=US:en",
     "category": "AI법률", "badge": "gnews", "lang": "en", "limit": 4},

    # ══════════════════════════════════════════════════
    # 📊  비즈니스 — 핵심 뉴스만 유지
    # ══════════════════════════════════════════════════
    {"name": "VentureBeat AI",
     "url":  "https://venturebeat.com/category/ai/feed/",
     "category": "비즈니스", "badge": "news", "lang": "en", "limit": 5},
    {"name": "MIT Tech Review",
     "url":  "https://www.technologyreview.com/feed/",
     "category": "비즈니스", "badge": "news", "lang": "en", "limit": 4},
    {"name": "AI Business",
     "url":  "https://aibusiness.com/rss.xml",
     "category": "비즈니스", "badge": "news", "lang": "en", "limit": 4},
    {"name": "Last Week in AI",
     "url":  "https://lastweekin.ai/feed",
     "category": "비즈니스", "badge": "news", "lang": "en", "limit": 4},
    {"name": "The Sequence",
     "url":  "https://thesequence.substack.com/feed",
     "category": "비즈니스", "badge": "news", "lang": "en", "limit": 3},
    {"name": "Ahead of AI",
     "url":  "https://magazine.sebastianraschka.com/feed",
     "category": "비즈니스", "badge": "news", "lang": "en", "limit": 3},
]

# ── 키워드 ─────────────────────────────────────────────
HOT_KEYWORDS = [
    "gpt", "llm", "agent", "에이전트", "multimodal", "멀티모달", "diffusion",
    "transformer", "claude", "gemini", "llama", "reasoning", "추론", "생성형",
    "video generation", "image generation", "rag", "fine-tuning", "파인튜닝",
    "benchmark", "open source", "오픈소스", "인공지능", "딥러닝", "chatgpt",
    "sora", "runway", "midjourney", "stable diffusion", "flux", "pika", "luma", "kling",
    "grok", "mistral", "phi", "qwen", "deepseek", "딥시크", "elevenlabs", "perplexity",
    "anthropic", "ideogram", "adobe firefly", "leonardo", "dall-e", "canva",
    "figma", "capcut", "heygen", "synthesia", "descript",
    "AI법률", "AI규제", "저작권", "규제", "정책",
    "content creator", "video editing", "영상편집", "콘텐츠 제작",
    "changelog", "release", "update", "api", "cursor", "copilot", "vscode",
]
KR_AI_KEYWORDS = [
    "인공지능", "AI", "머신러닝", "딥러닝", "챗봇", "생성형", "자연어",
    "이미지 생성", "영상 생성", "클로드", "제미나이", "챗GPT", "라마",
    "LLM", "에이전트", "파운데이션 모델", "딥시크", "미드저니",
    "runway", "sora", "pika", "플럭스", "레오나르도",
    "피그마", "캡컷", "AI규제", "AI법률", "저작권", "영상편집",
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
    if not text:
        return ""
    t = re.sub(r'<[^>]+>', '', text)
    for r, s in [
        ('&amp;', '&'), ('&lt;', '<'), ('&gt;', '>'),
        ('&nbsp;', ' '), ('&#8216;', "'"), ('&#8217;', "'"),
        ('&#8220;', '"'), ('&#8221;', '"'),
    ]:
        t = t.replace(r, s)
    t = re.sub(r'\s+', ' ', t).strip()
    return t[:280] + "…" if len(t) > 280 else t


def one_line_summary(text, max_len=120):
    if not text:
        return ""
    text = clean_html(text)
    sents = re.split(r'(?<=[.!?다요됨음])\s+', text)
    sents = [s.strip() for s in sents if len(s.strip()) > 12]
    if not sents:
        return (text[:max_len].rstrip() + "…") if len(text) > max_len else text

    SIGNAL_PATS = [
        r'\d+[%억만원달러]',
        r'(?:출시|출범|공개|발표|도입|업데이트|업그레이드|런칭|launch|release|introduce|announc)',
        r'(?:신규|새로운|처음|최초|first|new feature|now available)',
        r'(?:AI|LLM|GPT|Claude|Gemini|Sora|Runway|Midjourney|Figma|CapCut|Cursor|Copilot)',
    ]

    def score(s):
        sc = 0
        for p in SIGNAL_PATS:
            if re.search(p, s, re.IGNORECASE):
                sc += 1
        if len(s) < 20:
            sc -= 1
        if len(s) > 200:
            sc -= 1
        return sc

    best = max(sents, key=score)
    if len(best) <= max_len:
        return best
    truncated = best[:max_len].rsplit(' ', 1)[0]
    return truncated + "…"


def is_ai_related(title, summary, lang):
    if lang != "ko":
        return True
    text = (title + " " + summary).lower()
    return any(kw.lower() in text for kw in KR_AI_KEYWORDS)


LAUNCH_PATTERNS = [
    r'(?:출시|출범|런칭|공개|선보|새롭게|새로운 기능|신규 기능|업데이트)',
    r'(?:launch(?:es|ed)?|release[sd]?|introduc(?:es|ed|ing)|announc(?:es|ed|ing))',
    r'(?:now available|just released|new feature|new model|new tool)',
    r'(?:unveil[s]?|debut[s]?|roll[s]? out|ship[s]?)',
    r'(?:changelog|added|fixed|improved|updated)',  # ★ v12: Changelog 패턴 추가
]


def get_importance(title, summary="", category=""):
    # ★ v12: 논문 카테고리는 최대 star로 캡
    if category == "논문":
        text = (title + " " + summary).lower()
        n = sum(1 for kw in HOT_KEYWORDS if kw in text)
        if n >= 1:
            return {"label": "⭐ 추천", "class": "star"}
        return {"label": "🆕 신규", "class": "new"}

    text = (title + " " + summary).lower()
    n = sum(1 for kw in HOT_KEYWORDS if kw in text)

    is_launch = any(
        re.search(p, title + " " + summary, re.IGNORECASE)
        for p in LAUNCH_PATTERNS
    )
    if is_launch and n >= 1:
        return {"label": "🔥 핫", "class": "hot"}
    if n >= 3:
        return {"label": "🔥 핫", "class": "hot"}
    if n >= 1:
        return {"label": "⭐ 추천", "class": "star"}
    return {"label": "🆕 신규", "class": "new"}


# ── 참고앱 방식: 뉴스 분류(type) 자동 감지 ────────────────
# 분류: 모델출시 / API변경 / 기능추가 / 가격변경 / 도구출시 / 뉴스
TYPE_PATTERNS = {
    "모델출시": [
        r'(?:모델|model).*(?:출시|공개|릴리스|launch|release|introduc|announc)',
        r'(?:출시|공개|릴리스|launch|release|introduc).*(?:모델|model|LLM|GPT|Claude|Gemini|Llama|Mistral|Opus|Sonnet|Flash|Haiku|Grok|Phi|Qwen|DeepSeek)',
        r'(?:new|신규|새로운).*(?:model|모델)',
        r'(?:GPT|Claude|Gemini|Llama|Mistral|Opus|Sonnet|Haiku|Grok|Phi|Qwen|DeepSeek|Sora|Flux|DALL-E|Midjourney)\s*\d',
        r'(?:is now available|정식 출시|GA|Generally Available).*(?:model|모델)',
    ],
    "API변경": [
        r'API\s*(?:변경|업데이트|추가|deprecated|deprecat|endpoint|지원|support)',
        r'(?:API|SDK|endpoint)\s*v\d',
        r'(?:deprecated|deprecat|종료|sunset|migration)',
        r'(?:SDK|API)\s*(?:v\d|\d+\.\d+)',
        r'(?:새|신규|추가)\s*(?:API|엔드포인트|endpoint)',
    ],
    "가격변경": [
        r'(?:가격|요금|price|pricing|cost|비용|할인|discount|free|무료|인하|인상|플랜|plan|tier)',
        r'(?:token|토큰).*(?:price|가격|cost|비용)',
        r'(?:무료|free)\s*(?:플랜|plan|tier|버전)',
        r'(?:요금|price|pricing)\s*(?:변경|update|change|인하|인상)',
    ],
    "도구출시": [
        r'(?:도구|tool|plugin|extension|앱|app|CLI|SDK|라이브러리|library|framework|프레임워크).*(?:출시|launch|release|공개)',
        r'(?:출시|launch|release).*(?:도구|tool|plugin|extension|앱|CLI)',
        r'(?:Cursor|Copilot|VS Code|VSCode|GitHub|Codex|Claude Code|Windsurf|Replit|Bolt|Lovable).*(?:업데이트|update|release|출시|기능)',
        r'(?:Chrome|Firefox|Safari).*(?:extension|확장|plugin)',
        r'(?:MCP|Model Context Protocol)',
    ],
    "기능추가": [
        r'(?:기능|feature|추가|added|추가됨|지원|support).*(?:추가|added|지원|support|improved|개선)',
        r'(?:added|추가|지원|improved|강화|업그레이드).*(?:기능|feature|capability|지원|support)',
        r'(?:이제|now).*(?:가능|available|지원|support)',
        r'(?:새|new|신규)\s*(?:기능|feature|functionality)',
        r'(?:업데이트|update|개선|improvement|enhanced)',
    ],
}

def get_type(title: str, summary: str = "", source: str = "", category: str = "") -> str:
    """
    참고앱 방식으로 뉴스 분류 자동 감지.
    모델출시 > API변경 > 가격변경 > 도구출시 > 기능추가 > 뉴스 순으로 우선순위.
    """
    text = (title + " " + summary).lower()

    for type_name in ["모델출시", "API변경", "가격변경", "도구출시", "기능추가"]:
        for pattern in TYPE_PATTERNS[type_name]:
            if re.search(pattern, title + " " + summary, re.IGNORECASE):
                return type_name

    # 국내 뉴스 미디어는 기본 '뉴스'
    if category == "콘텐츠":
        return "뉴스"

    # 논문은 별도
    if category == "논문":
        return "논문"

    return "뉴스"


# ─────────────────────────────────────────────────────
# 시간 파싱
# ─────────────────────────────────────────────────────
def parse_date_kst(entry, lang='en'):
    for attr in ('published', 'updated'):
        raw = getattr(entry, attr, None)
        if not raw:
            continue
        try:
            dt = parsedate_to_datetime(raw)
            return dt.astimezone(KST).strftime("%Y-%m-%d %H:%M")
        except Exception:
            pass
        try:
            dt = datetime.fromisoformat(raw.replace('Z', '+00:00'))
            if dt.tzinfo is None:
                tz = KST if lang == 'ko' else timezone.utc
                dt = dt.replace(tzinfo=tz)
            return dt.astimezone(KST).strftime("%Y-%m-%d %H:%M")
        except Exception:
            pass

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
    body = (
        getattr(entry, 'summary', '') or
        (entry.content[0].get('value', '') if getattr(entry, 'content', None) else '')
    )
    m = re.search(r'<img[^>]+src=["\'](https?:[^"\']+)["\']', body)
    if m:
        return m.group(1)
    return ""


# ─────────────────────────────────────────────────────
# 번역 (deep-translator 우선 → Gemini API fallback)
# ─────────────────────────────────────────────────────
_translator = None


def get_translator():
    global _translator
    if _translator is None:
        try:
            from deep_translator import GoogleTranslator
            _translator = GoogleTranslator(source='auto', target='ko')
        except ImportError:
            _translator = False
    return _translator if _translator else None


def _gemini_translate(text: str) -> str:
    """Gemini API를 이용한 번역 fallback"""
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key or not text:
        return text
    try:
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"gemini-1.5-flash:generateContent?key={api_key}"
        )
        payload = {
            "contents": [{
                "parts": [{
                    "text": (
                        f"다음 영어 문장을 자연스러운 한국어로 번역해. "
                        f"번역문만 출력하고 다른 말은 하지 마:\n{text}"
                    )
                }]
            }],
            "generationConfig": {"maxOutputTokens": 200, "temperature": 0.1},
        }
        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        candidates = resp.json().get("candidates", [])
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            if parts:
                return parts[0].get("text", text).strip()
    except Exception:
        pass
    return text


def translate_to_ko(text, max_len=180):
    if not text:
        return ""
    translator = get_translator()
    # deep-translator 사용
    if translator:
        try:
            result = translator.translate(text[:max_len])
            if result:
                return result
        except Exception:
            pass
    # ★ v12: Gemini fallback
    return _gemini_translate(text[:max_len])


def batch_translate_items(items):
    translator = get_translator()
    gemini_key = os.environ.get("GEMINI_API_KEY", "")
    has_translation = bool(translator or gemini_key)

    if not has_translation:
        print("  ⚠️ 번역 수단 없음 (deep-translator 미설치 + GEMINI_API_KEY 없음), 생략")
        for it in items:
            it["one_line_kr"] = it.get("one_line", "")
        return

    en_items = [i for i in items if i.get("lang") == "en"]
    priority = (
        [i for i in en_items if i["importance"]["class"] == "hot"] +
        [i for i in en_items if i["importance"]["class"] == "star"] +
        [i for i in en_items if i["importance"]["class"] == "new"]
    )
    seen, ordered = set(), []
    for it in priority:
        if it["id"] not in seen:
            seen.add(it["id"])
            ordered.append(it)

    translate_targets = ordered[:80]
    translate_ids = {it["id"] for it in translate_targets}

    print(f"  🌐 번역 대상: {len(translate_targets)}건")
    ok_count = 0
    for it in items:
        if it["id"] in translate_ids:
            src_line = it.get("one_line", "") or it.get("title", "")
            it["one_line_kr"] = translate_to_ko(src_line)
            it["title_kr"] = translate_to_ko(it.get("title", "")[:120])
            ok_count += 1
        elif it.get("lang") == "en":
            it["one_line_kr"] = ""
            it["title_kr"] = ""
        else:
            it["one_line_kr"] = ""
            it["title_kr"] = ""

    print(f"  ✅ 번역 완료: {ok_count}건")


# ─────────────────────────────────────────────────────
# 블로그 크롤러 (RSS 없는 공식 플랫폼)
# ─────────────────────────────────────────────────────
BLOG_CONFIGS = [
    # ── Runway 공식 블로그 (★ v12: /news/ → /blog/ 수정) ──
    {
        "name":         "Runway Blog",
        "base_url":     "https://runwayml.com",
        "list_url":     "https://runwayml.com/blog",
        "category":     "영상AI",
        "badge":        "crawled",
        "lang":         "en",
        "limit":        5,
        "link_pattern": r"^(?:/blog/|blog/)[a-z0-9]",
        "link_base":    "https://runwayml.com",
    },
    # ── ElevenLabs 공식 블로그 ────────────────────────
    {
        "name":         "ElevenLabs Blog",
        "base_url":     "https://elevenlabs.io",
        "list_url":     "https://elevenlabs.io/blog",
        "category":     "영상AI",
        "badge":        "crawled",
        "lang":         "en",
        "limit":        5,
        "link_pattern": r"^/blog/[a-z0-9]",
        "link_base":    "https://elevenlabs.io",
    },
    # ── HeyGen 공식 블로그 ────────────────────────────
    {
        "name":         "HeyGen Blog",
        "base_url":     "https://www.heygen.com",
        "list_url":     "https://www.heygen.com/blog",
        "category":     "영상AI",
        "badge":        "crawled",
        "lang":         "en",
        "limit":        5,
        "link_pattern": r"^/blog/[a-z0-9]",
        "link_base":    "https://www.heygen.com",
    },
    # ── Pika Labs 블로그 ──────────────────────────────
    {
        "name":         "Pika Blog",
        "base_url":     "https://pika.art",
        "list_url":     "https://pika.art/blog",
        "category":     "영상AI",
        "badge":        "crawled",
        "lang":         "en",
        "limit":        5,
        "link_pattern": r"^/blog/[a-z0-9]",
        "link_base":    "https://pika.art",
    },
    # ── Anthropic 공식 뉴스 (RSS 보완용) ─────────────
    {
        "name":         "Anthropic Blog",
        "base_url":     "https://www.anthropic.com",
        "list_url":     "https://www.anthropic.com/news",
        "category":     "LLM",
        "badge":        "crawled",
        "lang":         "en",
        "limit":        5,
        "link_pattern": r"^/news/[a-z]",
        "link_base":    "https://www.anthropic.com",
    },
    # ── Stability AI 뉴스 ─────────────────────────────
    {
        "name":         "Stability AI News",
        "base_url":     "https://stability.ai",
        "list_url":     "https://stability.ai/news",
        "category":     "이미지·디자인AI",
        "badge":        "crawled",
        "lang":         "en",
        "limit":        5,
        "link_pattern": r"^/news/[a-z]",
        "link_base":    "https://stability.ai",
    },
    # ── Figma 공식 블로그 ─────────────────────────────
    {
        "name":         "Figma Blog",
        "base_url":     "https://www.figma.com",
        "list_url":     "https://www.figma.com/blog/",
        "category":     "이미지·디자인AI",
        "badge":        "crawled",
        "lang":         "en",
        "limit":        5,
        "link_pattern": r"^/blog/[a-z0-9]",
        "link_base":    "https://www.figma.com",
    },
    # ── ★ v12: Cursor Changelog (공식 RSS 없음) ───────
    {
        "name":         "Cursor Changelog",
        "base_url":     "https://www.cursor.com",
        "list_url":     "https://www.cursor.com/changelog",
        "category":     "개발AI",
        "badge":        "crawled",
        "lang":         "en",
        "limit":        6,
        "link_pattern": r"^(?:/changelog/|/changelog$)",
        "link_base":    "https://www.cursor.com",
    },
    # ── ★ v12: Mistral Changelog ─────────────────────
    {
        "name":         "Mistral Changelog",
        "base_url":     "https://docs.mistral.ai",
        "list_url":     "https://docs.mistral.ai/getting-started/changelog/",
        "category":     "개발AI",
        "badge":        "crawled",
        "lang":         "en",
        "limit":        6,
        "link_pattern": r"^(?:/getting-started/changelog|#)",
        "link_base":    "https://docs.mistral.ai",
    },
    # ── ★ v12: Google Gemini API Changelog ───────────
    {
        "name":         "Gemini API Changelog",
        "base_url":     "https://ai.google.dev",
        "list_url":     "https://ai.google.dev/gemini-api/docs/changelog",
        "category":     "개발AI",
        "badge":        "crawled",
        "lang":         "en",
        "limit":        6,
        "link_pattern": r"^(?:/gemini-api/docs/changelog|#\d{2}-\d{2}-\d{4})",
        "link_base":    "https://ai.google.dev",
    },
    # ── ★ v12: OpenAI Developer Changelog ────────────
    {
        "name":         "OpenAI Dev Changelog",
        "base_url":     "https://platform.openai.com",
        "list_url":     "https://platform.openai.com/docs/changelog",
        "category":     "개발AI",
        "badge":        "crawled",
        "lang":         "en",
        "limit":        6,
        "link_pattern": r"^(?:/docs/changelog|#\d{4}-\d{2}-\d{2})",
        "link_base":    "https://platform.openai.com",
    },
]


def _find_time_in_container(element, depth=5):
    t = element.find("time")
    if t:
        return t
    node = element.parent
    for _ in range(depth):
        if not node:
            break
        t = node.find("time")
        if t:
            return t
        node = node.parent
    return None


def scrape_blog(cfg):
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
            if href.startswith("/"):
                full_url = cfg["link_base"].rstrip("/") + href
            elif href.startswith("http"):
                full_url = href
            else:
                full_url = cfg["link_base"].rstrip("/") + "/" + href.lstrip("/")

            if full_url in seen_hrefs:
                continue
            seen_hrefs.add(full_url)

            title_el = a.find(["h1", "h2", "h3", "h4", "h5"])
            if title_el:
                title = title_el.get_text(strip=True)
            else:
                direct_texts = [
                    t.strip() for t in a.find_all(string=True, recursive=False)
                    if t.strip()
                ]
                title = direct_texts[0] if direct_texts else ''
                if not title:
                    first = a.find(string=True)
                    title = first.strip() if first else ''
            title = re.sub(r'\s+', ' ', title)[:120].strip()
            if len(title) < 15 or (len(title.split()) == 1 and title[0].isupper()):
                continue

            date_str = ""
            time_el = _find_time_in_container(a, depth=6)
            if time_el:
                date_str = time_el.get("datetime", "") or time_el.get_text(strip=True)
            if not date_str:
                text_block = a.get_text(" ", strip=True)
                m = re.search(
                    r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)'
                    r'[a-z]* \d{1,2},? \d{4}',
                    text_block, re.IGNORECASE
                )
                if m:
                    date_str = m.group(0)

            kst_date = _parse_scraped_date(date_str)

            summary = ""
            parent = a.parent
            if parent:
                p_el = parent.find("p")
                if p_el:
                    summary = clean_html(p_el.get_text(strip=True))

            items.append({
                "id":           f"{abs(hash(title + full_url)) % 999999:06d}",
                "title":        title,
                "summary":      summary,
                "one_line":     one_line_summary(summary or title),
                "one_line_kr":  "",
                "url":          full_url,
                "source":       cfg["name"],
                "category":     cfg["category"],
                "badge":        cfg["badge"],
                "lang":         cfg["lang"],
                "date":         kst_date,
                "collect_date": TODAY,
                "thumbnail":    "",
                "type":         get_type(title, summary, cfg["name"], cfg["category"]),
                "importance":   get_importance(title, summary, cfg["category"]),
            })
            count += 1

        print(f"  ✅ {cfg['name']} (크롤링): {count}건")
    except Exception as e:
        print(f"  ❌ {cfg['name']} (크롤링): {e}")
    return items


def _parse_scraped_date(raw: str) -> str:
    if not raw:
        return NOW_KST.strftime("%Y-%m-%d %H:%M")
    try:
        dt = datetime.fromisoformat(raw.replace('Z', '+00:00'))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(KST).strftime("%Y-%m-%d %H:%M")
    except Exception:
        pass
    MONTHS = {
        "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
        "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
    }
    m = re.search(
        r'(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)'
        r'[a-z]* (\d{1,2}),? (\d{4})',
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
        cat   = feed_info.get("category", "")
        for entry in feed.entries:
            if count >= feed_info["limit"]:
                break
            title = clean_html(entry.get("title", "제목 없음"))
            link  = entry.get("link", "#")
            raw_summary = (
                entry.get("summary", "") or
                (entry.content[0].get("value", "") if getattr(entry, "content", None) else "")
            )
            summary = clean_html(raw_summary)
            if not is_ai_related(title, summary, lang):
                continue
            items.append({
                "id":           f"{abs(hash(title + link)) % 999999:06d}",
                "title":        title,
                "summary":      summary,
                "one_line":     one_line_summary(summary or title),
                "one_line_kr":  "",
                "url":          link,
                "source":       feed_info["name"],
                "category":     cat,
                "badge":        feed_info["badge"],
                "lang":         lang,
                "date":         parse_date_kst(entry, lang),
                "collect_date": TODAY,
                "thumbnail":    get_thumbnail(entry),
                "type":         get_type(title, summary, feed_info["name"], cat),
                "importance":   get_importance(title, summary, cat),
            })
            count += 1
        status = f"{count}건" if count > 0 else "0건 (AI 관련 없거나 빈 피드)"
        print(f"  ✅ {feed_info['name']}: {status}")
    except Exception as e:
        print(f"  ❌ {feed_info['name']}: {e}")
    return items


# ─────────────────────────────────────────────────────
# 집계
# ─────────────────────────────────────────────────────
EXTRACT_KEYWORDS = [
    "LLM", "Agent", "에이전트", "RAG", "GPT", "Claude", "클로드", "Gemini", "제미나이",
    "Llama", "라마", "Diffusion", "Multimodal", "멀티모달", "Fine-tuning", "파인튜닝",
    "Transformer", "Reasoning", "추론", "Vision", "Benchmark", "Open Source", "오픈소스",
    "Video AI", "Image Generation", "이미지 생성", "생성형 AI", "DeepSeek", "딥시크",
    "Sora", "Runway", "Midjourney", "Stable Diffusion", "Flux", "Pika", "Luma", "Kling",
    "인공지능", "ChatGPT", "Grok", "Mistral", "Phi", "Qwen", "ElevenLabs",
    "Anthropic", "Perplexity", "Ideogram", "Adobe Firefly", "Leonardo", "DALL-E", "Canva AI",
    "Together AI", "ComfyUI", "Cursor", "Copilot", "GitHub", "VS Code",
]


def extract_keywords(items):
    freq = {}
    for item in items:
        text = (item["title"] + " " + item["summary"]).lower()
        for kw in EXTRACT_KEYWORDS:
            if kw.lower() in text:
                freq[kw] = freq.get(kw, 0) + 1
    return [
        {"keyword": k, "count": v}
        for k, v in sorted(freq.items(), key=lambda x: -x[1])[:20]
    ]


def make_stats(items):
    cat, src = {}, {}
    for it in items:
        cat[it["category"]] = cat.get(it["category"], 0) + 1
        src[it["source"]]   = src.get(it["source"], 0) + 1
    ordered_cat = {k: cat[k] for k in CATEGORY_ORDER if k in cat}
    sorted_src  = [
        {"source": k, "count": v}
        for k, v in sorted(src.items(), key=lambda x: -x[1])
    ]
    return ordered_cat, sorted_src


# ─────────────────────────────────────────────────────
# 핵심 포인트 생성
# ─────────────────────────────────────────────────────
_SOURCE_TAG_RE = re.compile(r'^\[[^\]]{1,40}\]\s*')


def _strip_source_tag(text: str) -> str:
    return _SOURCE_TAG_RE.sub('', text).strip()


def _extract_first_sentence(text: str, max_len: int = 130) -> str:
    text = _strip_source_tag(text)
    if not text:
        return ""

    stmt_endings = [
        '발표했다.', '공개했다.', '밝혔다.', '출시했다.', '나섰다.',
        '됩니다.', '했습니다.', '됐다.', '체결했다.', '선보였다.',
        '이다.', '었다.', '였다.',
    ]
    for ending in stmt_endings:
        idx = text.find(ending)
        if 12 < idx <= max_len:
            return text[:idx + len(ending)].strip()

    m = re.search(r'.{12,}?[.。]\s', text)
    if m and m.end() <= max_len + 5:
        candidate = text[:m.end()].strip()
        if len(candidate) < 22:
            m2 = re.search(r'.{20,}?[.。]\s', text[m.end():])
            if m2 and (m.end() + m2.end()) <= max_len + 20:
                return text[:m.end() + m2.end()].strip()
        return candidate

    idx = text.find('.')
    if 15 < idx <= max_len:
        return text[:idx + 1].strip()

    if len(text) > max_len:
        for sep in ['다.', '습니다.', '이다.', '했다.']:
            ridx = text[:max_len].rfind(sep)
            if ridx > 15:
                return text[:ridx + len(sep)].strip()
        return text[:max_len].rstrip() + '.'

    return text.rstrip()


def _finalize(text: str) -> str:
    if not text:
        return ""
    text = _strip_source_tag(text.strip())

    if text.endswith('…') or text.endswith('...'):
        for sep in ['다.', '했다.', '됩니다.', '습니다.', '이다.', '었다.', '였다.']:
            idx = text.rfind(sep)
            if idx > 15:
                return text[:idx + len(sep)].strip()
        text = re.sub(r'[…\.]+$', '', text).strip() + '.'

    if text and text[-1] not in ('.', '!', '?', '다', '요', '됨', '음'):
        text = text + '.'

    return text


def make_key_point(item) -> str:
    title   = item.get("title", "").strip()
    summary = item.get("summary", "").strip()
    lang    = item.get("lang", "en")

    if lang == "ko":
        if summary and len(summary) > 20:
            clean_sum = _strip_source_tag(summary)
            sent = _extract_first_sentence(clean_sum, max_len=130)
            if sent and len(sent) > 15:
                return _finalize(_strip_source_tag(sent))
        title_clean = _strip_source_tag(title)
        return _finalize(title_clean)
    else:
        kr = _strip_source_tag(item.get("one_line_kr", "").strip())
        if kr and len(kr) > 10:
            kr = re.sub(r'하는 방법\.$', '하는 방법을 공개했다.', kr)
            kr = re.sub(r'을 사용할 수 있습니다\.$', '을 API로 제공한다.', kr)
            kr = re.sub(r'할 수 있습니다\.$', '한다.', kr)
            return _finalize(kr)

        if summary and len(summary) > 20:
            clean_sum = re.sub(
                r'^arXiv:\S+\s+Announce Type:[^\n]*\n?', '', summary
            )
            clean_sum = re.sub(r'^Abstract:\s*', '', clean_sum).strip()
            snippet = clean_sum[:150].split(". ")[0].strip()
            if snippet and len(snippet) > 20:
                translated = translate_to_ko(snippet[:130])
                if translated and len(translated) > 10 and translated != snippet:
                    return _finalize(translated)

        title_kr = translate_to_ko(title[:90])
        return _finalize(title_kr) if title_kr and title_kr != title else _finalize(title)


def build_daily_summary(items, keywords):
    today_items = [i for i in items if (i.get("date") or "").startswith(TODAY)]
    if len(today_items) < 3:
        today_items = [i for i in items if (i.get("collect_date") or "") == TODAY]
    if len(today_items) == 0:
        today_items = items

    kr   = sum(1 for i in today_items if i.get("lang") == "ko")
    cats = {c: sum(1 for i in today_items if i["category"] == c) for c in CATEGORY_ORDER}
    top_cat = max(
        (c for c in CATEGORY_ORDER if cats.get(c, 0) > 0),
        key=lambda c: cats[c], default="-"
    )
    top_kws = [k["keyword"] for k in keywords[:7]]
    kw_str  = " · ".join(top_kws[:5]) if top_kws else "-"

    hot      = [i for i in today_items if i["importance"]["class"] == "hot"]
    hot_items = hot[:3]
    hot_titles = ""
    if hot_items:
        hot_titles = (
            " 특히 " +
            "、".join(f"'{h['title'][:30]}'" for h in hot_items[:2]) +
            " 등이 주목받았습니다."
        )

    prose = (
        f"오늘({NOW_KST.strftime('%m월 %d일')}) {len(today_items)}건의 AI 뉴스가 업데이트됐습니다. "
        f"국내 기사 {kr}건, 해외 기사 {len(today_items) - kr}건이며 "
        f"오늘의 핵심 키워드는 {kw_str}로, {top_cat} 분야에서 가장 많은 활동이 관측됐습니다."
        f"{hot_titles}"
    )

    NON_INSIGHT_CATS = {"논문", "비즈니스"}
    IMP_ORDER = {"hot": 0, "star": 1, "new": 2}

    def kp_priority_key(x):
        imp   = IMP_ORDER.get(x["importance"]["class"], 2)
        is_ko = 0 if x.get("lang") == "ko" else 1
        return (imp, is_ko)

    kp_candidates = sorted(
        [i for i in today_items if i["category"] not in NON_INSIGHT_CATS],
        key=kp_priority_key
    )
    seen_kp_src, key_point_items = set(), []
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
        "en_count":        len(today_items) - kr,
        "top_keywords":    top_kws,
        "top_category":    top_cat,
        "category_counts": cats,
        "hot_picks":       [
            {"title": i["title"], "source": i["source"], "url": i["url"]}
            for i in hot_items
        ],
        "key_points":      key_points,
        "one_line":        (
            f"오늘 {len(items)}건 | 국내 {kr} · 해외 {len(items) - kr} | "
            f"핫 키워드: {', '.join(top_kws[:3])}"
        ),
        "prose":           prose,
    }


# ─────────────────────────────────────────────────────
# 누적 집계 (주간·월간)
# ─────────────────────────────────────────────────────
def load_seen_urls_from_history(exclude_today=True) -> set:
    history_dir = "data/history"
    seen_urls = set()
    if not os.path.isdir(history_dir):
        return seen_urls
    for fpath in glob.glob(f"{history_dir}/*.json"):
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
    cat_stats, src_stats = make_stats(items)
    keywords = extract_keywords(items)
    kr = sum(1 for i in items if i.get("lang") == "ko")

    daily_counts = {}
    for it in items:
        d = it.get("collect_date", "")
        if d:
            daily_counts[d] = daily_counts.get(d, 0) + 1
    daily_timeline = [
        {"date": k, "count": v} for k, v in sorted(daily_counts.items())
    ]

    cat_daily = {}
    for it in items:
        d, cat = it.get("collect_date", ""), it.get("category", "")
        if d and cat:
            cat_daily.setdefault(d, {})
            cat_daily[d][cat] = cat_daily[d].get(cat, 0) + 1

    hot  = [i for i in items if i.get("importance", {}).get("class") == "hot"]
    star = [i for i in items if i.get("importance", {}).get("class") == "star"]
    priority = hot + star
    seen_u, highlights = set(), []
    for it in priority:
        url = it.get("url", "")
        if url and url not in seen_u:
            seen_u.add(url)
            highlights.append(it)
        if len(highlights) >= 10:
            break

    MAIN_CATS = ["콘텐츠", "영상AI", "이미지·디자인AI", "LLM", "개발AI"]
    cat_highlights = {}
    for cat in MAIN_CATS:
        cat_items = [i for i in priority if i.get("category") == cat]
        if not cat_items:
            cat_items = [i for i in items if i.get("category") == cat]
        if cat_items:
            cat_highlights[cat] = {
                "title":    cat_items[0]["title"],
                "source":   cat_items[0]["source"],
                "url":      cat_items[0].get("url", ""),
                "one_line": (
                    cat_items[0].get("one_line_kr") or
                    cat_items[0].get("one_line", "")
                ),
                "date":     cat_items[0].get("date", ""),
            }

    key_points_items  = highlights[:5] if highlights else items[:5]
    period_key_points = [make_key_point(it) for it in key_points_items]

    top_kws = [k["keyword"] for k in keywords[:5]]
    kw_str  = ", ".join(top_kws) if top_kws else "-"
    top_cat = max(cat_stats.items(), key=lambda x: x[1])[0] if cat_stats else "-"
    period_name = "주간" if period_label == "weekly" else "월간"
    period_prose = (
        f"이번 {period_name} 총 {len(items)}건의 AI 자료가 수집됐습니다. "
        f"국내 {kr}건, 해외 {len(items) - kr}건이며 "
        f"{top_cat} 분야에서 가장 활발한 활동이 관측됐습니다. "
        f"주요 키워드는 {kw_str}입니다."
    )

    return {
        "period":             period_label,
        "days":               days,
        "generated_at":       NOW_KST.strftime("%Y-%m-%d %H:%M"),
        "total":              len(items),
        "kr_count":           kr,
        "en_count":           len(items) - kr,
        "category_stats":     cat_stats,
        "source_stats":       src_stats,
        "keywords":           keywords,
        "daily_timeline":     daily_timeline,
        "cat_daily":          cat_daily,
        "content_highlights": highlights,
        "cat_highlights":     cat_highlights,
        "period_key_points":  period_key_points,
        "period_prose":       period_prose,
        "items":              items,
    }


# ─────────────────────────────────────────────────────
# 메인
# ─────────────────────────────────────────────────────
def main():
    print(f"\n{'=' * 60}")
    print(f"  AI 트렌드 뉴스 수집 v12 — {TODAY}")
    print(f"  실행 시각: {NOW_KST.strftime('%Y-%m-%d %H:%M')} KST")
    print(f"  RSS 소스: {len(RSS_FEEDS)}개 / 블로그 크롤러: {len(BLOG_CONFIGS)}개")
    print(f"{'=' * 60}\n")

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
    print("\n── 중복 제거 ─────────────────────────────────")
    prev_urls = load_seen_urls_from_history(exclude_today=True)
    print(f"  이전 수집 URL: {len(prev_urls)}건")
    seen, deduped = set(), []
    skip_old = 0
    for it in today_items:
        url = it["url"]
        if url in seen:
            continue
        seen.add(url)
        if url in prev_urls:
            skip_old += 1
            continue
        deduped.append(it)
    today_items = deduped
    print(f"  ✅ 이전 중복 제거: {skip_old}건 | 최종 신규: {len(today_items)}건")

    # 4) 카테고리 순서 정렬
    today_items.sort(
        key=lambda x: (
            CATEGORY_ORDER.index(x["category"])
            if x["category"] in CATEGORY_ORDER else 99
        )
    )
    for i, item in enumerate(today_items):
        item["id"] = f"{TODAY}_{i:04d}"
        if not item.get("one_line"):
            item["one_line"] = one_line_summary(
                item.get("summary", "") or item.get("title", "")
            )

    # 5) 해외 기사 번역
    print("\n── 해외 기사 번역 ────────────────────────────")
    batch_translate_items(today_items)
    for it in today_items:
        if it.get("lang") == "ko":
            it["one_line_kr"] = it.get("one_line", "")
            it["title_kr"]    = it.get("title", "")

    kr_cnt = sum(1 for i in today_items if i.get("lang") == "ko")
    print(f"\n오늘 수집: {len(today_items)}건 (국내 {kr_cnt} / 해외 {len(today_items) - kr_cnt})")

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
        json.dump(
            build_period_json(weekly_items, "weekly", 7),
            f, ensure_ascii=False, indent=2
        )
    print(f"✅ data/weekly.json 저장 ({len(weekly_items)}건)")

    print("📊 월간 집계 생성 중...")
    monthly_items = load_history_items(30)
    with open("data/monthly.json", "w", encoding="utf-8") as f:
        json.dump(
            build_period_json(monthly_items, "monthly", 30),
            f, ensure_ascii=False, indent=2
        )
    print(f"✅ data/monthly.json 저장 ({len(monthly_items)}건)")

    # 8) 결과 요약
    print(f"\n{'=' * 60}")
    print(f"✅ 완료! (v12)")
    print(f"   RSS 소스: {len(RSS_FEEDS)}개 | 크롤러: {len(BLOG_CONFIGS)}개")
    print(f"   카테고리: {list(cat_stats.keys())}")
    print(f"   핫 키워드: {[k['keyword'] for k in keywords[:7]]}")
    print(f"   핵심 포인트:")
    for pt in daily_summary.get("key_points", []):
        print(f"     • {pt}")
    print(f"   카테고리별 분포:")
    for cat, cnt in cat_stats.items():
        bar = "█" * min(cnt // 2, 20)
        print(f"     {cat:14s} {cnt:4d}건  {bar}")


if __name__ == "__main__":
    main()

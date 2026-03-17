#!/usr/bin/env python3
"""
AI 트렌드 — RSS 자동 수집 스크립트 (B방식: 날짜별 누적 저장)

저장 구조:
  data/
  ├── ai_news.json            ← 오늘 데이터 (대시보드 기본 로딩)
  ├── history/
  │   ├── YYYY-MM-DD.json     ← 날짜별 보관
  │   └── ...
  ├── weekly.json             ← 최근 7일 집계
  └── monthly.json            ← 최근 30일 집계

[시간 처리 원칙]
  - 모든 RSS 날짜를 UTC → KST(+9)로 통일 변환
  - 날짜 정보가 없는 경우 수집 시각(KST)으로 대체
  - 카드에는 원문 발행 시각(KST 변환) 표시
"""

import json, feedparser, requests, re, os, glob
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime

KST     = timezone(timedelta(hours=9))
NOW_KST = datetime.now(KST)
TODAY   = NOW_KST.strftime("%Y-%m-%d")

# ── 카테고리 순서 ──────────────────────────────────────────
CATEGORY_ORDER = ["콘텐츠", "영상AI", "이미지AI", "LLM", "디자인AI", "논문", "개발AI", "비즈니스"]

# ── RSS 피드 목록 ──────────────────────────────────────────
RSS_FEEDS = [
    # ─── 🇰🇷 콘텐츠 (한국 미디어) ─────────────────────────
    {"name":"AI타임스",        "url":"https://www.aitimes.com/rss/allArticle.xml",          "category":"콘텐츠",  "badge":"kr-news","lang":"ko","limit":10},
    {"name":"바이라인네트워크",  "url":"https://byline.network/feed/",                        "category":"콘텐츠",  "badge":"kr-news","lang":"ko","limit":7},
    {"name":"디지털투데이",      "url":"https://www.digitaltoday.co.kr/rss/allArticle.xml",  "category":"콘텐츠",  "badge":"kr-news","lang":"ko","limit":7},
    {"name":"전자신문",          "url":"http://rss.etnews.com/Section901.xml",               "category":"콘텐츠",  "badge":"kr-news","lang":"ko","limit":7},
    {"name":"더에이아이",        "url":"http://www.newstheai.com/rss/allArticle.xml",        "category":"콘텐츠",  "badge":"kr-news","lang":"ko","limit":6},

    # ─── 🎬 영상AI ──────────────────────────────────────────
    {"name":"Replicate Blog",   "url":"https://replicate.com/blog/rss",                    "category":"영상AI",  "badge":"tool",   "lang":"en","limit":5},
    {"name":"NVIDIA Dev Blog",  "url":"https://developer.nvidia.com/blog/feed",            "category":"영상AI",  "badge":"tool",   "lang":"en","limit":5},
    {"name":"TechCrunch AI",    "url":"https://techcrunch.com/category/artificial-intelligence/feed/","category":"영상AI","badge":"news","lang":"en","limit":6},

    # ─── 🖼️ 이미지AI ─────────────────────────────────────────
    {"name":"HuggingFace Blog", "url":"https://huggingface.co/blog/feed.xml",              "category":"이미지AI","badge":"official","lang":"en","limit":6},
    {"name":"Wired AI",         "url":"https://www.wired.com/feed/rss",                    "category":"이미지AI","badge":"news",   "lang":"en","limit":5},
    {"name":"AI News",          "url":"https://www.artificialintelligence-news.com/feed/", "category":"이미지AI","badge":"news",   "lang":"en","limit":5},

    # ─── 🧠 LLM ────────────────────────────────────────────
    {"name":"OpenAI",           "url":"https://openai.com/news/rss.xml",                   "category":"LLM",     "badge":"official","lang":"en","limit":6},
    {"name":"OpenAI Blog",      "url":"https://openai.com/blog/rss.xml",                   "category":"LLM",     "badge":"official","lang":"en","limit":4},
    {"name":"Simon Willison",   "url":"https://simonwillison.net/atom/entries/",            "category":"LLM",     "badge":"official","lang":"en","limit":5},
    {"name":"Import AI",        "url":"https://importai.substack.com/feed",                "category":"LLM",     "badge":"news",   "lang":"en","limit":5},
    {"name":"Sebastian Raschka","url":"https://magazine.sebastianraschka.com/feed",        "category":"LLM",     "badge":"news",   "lang":"en","limit":4},
    {"name":"Ben Evans",        "url":"https://www.ben-evans.com/benedictevans/rss.xml",   "category":"LLM",     "badge":"news",   "lang":"en","limit":4},

    # ─── 🎨 디자인AI ─────────────────────────────────────────
    {"name":"Bloomberg Tech",   "url":"https://feeds.bloomberg.com/technology/news.rss",   "category":"디자인AI","badge":"news",   "lang":"en","limit":5},
    {"name":"Toward AI",        "url":"https://towardsai.net/feed",                        "category":"디자인AI","badge":"news",   "lang":"en","limit":4},

    # ─── 📄 논문 ────────────────────────────────────────────
    {"name":"ArXiv AI",         "url":"https://rss.arxiv.org/rss/cs.AI",                  "category":"논문",    "badge":"paper",  "lang":"en","limit":8},
    {"name":"ArXiv ML",         "url":"https://rss.arxiv.org/rss/cs.LG",                  "category":"논문",    "badge":"paper",  "lang":"en","limit":6},
    {"name":"ArXiv CV",         "url":"https://rss.arxiv.org/rss/cs.CV",                  "category":"논문",    "badge":"paper",  "lang":"en","limit":5},
    {"name":"ArXiv CL",         "url":"https://rss.arxiv.org/rss/cs.CL",                  "category":"논문",    "badge":"paper",  "lang":"en","limit":5},

    # ─── 💻 개발AI ──────────────────────────────────────────
    {"name":"Google AI Blog",   "url":"http://googleaiblog.blogspot.com/atom.xml",         "category":"개발AI",  "badge":"official","lang":"en","limit":4},
    {"name":"DeepMind",         "url":"https://deepmind.google/blog/rss.xml",              "category":"개발AI",  "badge":"official","lang":"en","limit":4},
    {"name":"LangChain Blog",   "url":"https://blog.langchain.dev/rss/",                   "category":"개발AI",  "badge":"official","lang":"en","limit":4},
    {"name":"MarkTechPost",     "url":"https://www.marktechpost.com/feed/",                "category":"개발AI",  "badge":"news",   "lang":"en","limit":5},

    # ─── 📊 비즈니스 ─────────────────────────────────────────
    {"name":"VentureBeat AI",   "url":"https://venturebeat.com/category/ai/feed/",         "category":"비즈니스","badge":"news",   "lang":"en","limit":5},
    {"name":"MIT Tech Review",  "url":"https://www.technologyreview.com/feed/",            "category":"비즈니스","badge":"news",   "lang":"en","limit":4},
    {"name":"AI Business",      "url":"https://aibusiness.com/rss.xml",                    "category":"비즈니스","badge":"news",   "lang":"en","limit":4},
]

HOT_KEYWORDS = [
    "gpt","llm","agent","에이전트","멀티모달","multimodal","diffusion",
    "transformer","claude","gemini","llama","reasoning","추론","생성형",
    "video generation","image generation","rag","fine-tuning","파인튜닝",
    "benchmark","open source","오픈소스","인공지능","딥러닝","chatgpt","sora",
    "midjourney","stable diffusion","flux","runway","pika","luma",
    "grok","mistral","phi","qwen","deepseek","딥시크",
]
KR_AI_KEYWORDS = [
    "인공지능","AI","머신러닝","딥러닝","챗봇","생성형","자연어",
    "이미지 생성","영상 생성","클로드","제미나이","챗GPT","라마",
    "LLM","에이전트","파운데이션 모델","딥시크","sora","runway","미드저니",
]

# ─────────────────────────────────────────────────────────
# 유틸 함수
# ─────────────────────────────────────────────────────────
def clean_html(text):
    if not text: return ""
    t = re.sub(r'<[^>]+>', '', text)
    for r, s in [('&amp;','&'),('&lt;','<'),('&gt;','>'),('&nbsp;',' '),('&#8216;',"'"),('&#8217;',"'")]:
        t = t.replace(r, s)
    t = re.sub(r'\s+', ' ', t).strip()
    return t[:280] + "…" if len(t) > 280 else t

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

def parse_date_kst(entry):
    """
    RSS의 발행 시각을 KST로 변환해서 반환.
    - published_parsed / updated_parsed (time.struct_time → UTC 가정)
    - published / updated 문자열 직접 파싱
    - 모두 없으면 수집 시각(NOW_KST)
    """
    # 1) feedparser가 파싱한 struct_time (UTC)
    for attr in ('published_parsed', 'updated_parsed'):
        t = getattr(entry, attr, None)
        if t:
            try:
                dt = datetime(*t[:6], tzinfo=timezone.utc)
                return dt.astimezone(KST).strftime("%Y-%m-%d %H:%M")
            except Exception:
                pass

    # 2) 문자열 날짜 직접 파싱 (RFC2822 / ISO8601)
    for attr in ('published', 'updated'):
        raw = getattr(entry, attr, None)
        if raw:
            try:
                dt = parsedate_to_datetime(raw)          # RFC2822
                return dt.astimezone(KST).strftime("%Y-%m-%d %H:%M")
            except Exception:
                pass
            try:
                dt = datetime.fromisoformat(raw.replace('Z', '+00:00'))
                return dt.astimezone(KST).strftime("%Y-%m-%d %H:%M")
            except Exception:
                pass

    # 3) 폴백: 수집 시각
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

# ─────────────────────────────────────────────────────────
# 수집
# ─────────────────────────────────────────────────────────
def fetch_feed(feed_info):
    items = []
    try:
        resp = requests.get(
            feed_info["url"],
            headers={"User-Agent": "Mozilla/5.0 (compatible; AI-Trend/3.0)"},
            timeout=15,
        )
        resp.raise_for_status()
        feed  = feedparser.parse(resp.text)
        count = 0
        for entry in feed.entries:
            if count >= feed_info["limit"]: break
            title   = clean_html(entry.get("title", "제목 없음"))
            link    = entry.get("link", "#")
            summary = clean_html(
                entry.get("summary", "") or
                (entry.content[0].get("value", "") if getattr(entry, "content", None) else ""))
            lang = feed_info.get("lang", "en")
            if not is_ai_related(title, summary, lang): continue
            items.append({
                "id":           f"{abs(hash(title+link))%999999:06d}",
                "title":        title,
                "summary":      summary,
                "url":          link,
                "source":       feed_info["name"],
                "category":     feed_info["category"],
                "badge":        feed_info["badge"],
                "lang":         lang,
                "date":         parse_date_kst(entry),   # ★ KST 통일
                "collect_date": TODAY,
                "thumbnail":    get_thumbnail(entry),
                "importance":   get_importance(title, summary),
            })
            count += 1
        print(f"  ✅ {feed_info['name']}: {count}건")
    except Exception as e:
        print(f"  ❌ {feed_info['name']}: {e}")
    return items

# ─────────────────────────────────────────────────────────
# 집계 함수
# ─────────────────────────────────────────────────────────
EXTRACT_KEYWORDS = [
    "LLM","Agent","에이전트","RAG","GPT","Claude","클로드","Gemini","제미나이",
    "Llama","라마","Diffusion","Multimodal","멀티모달","Fine-tuning","파인튜닝",
    "Transformer","Reasoning","추론","Vision","Benchmark","Open Source","오픈소스",
    "Video AI","Image Generation","이미지 생성","생성형 AI","DeepSeek","딥시크",
    "Sora","Runway","Midjourney","Stable Diffusion","Flux","Pika","Luma",
    "인공지능","ChatGPT","Grok","Mistral","Phi","Qwen",
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

def build_daily_summary(items, keywords):
    kr   = sum(1 for i in items if i.get("lang")=="ko")
    cats = {c: sum(1 for i in items if i["category"]==c) for c in CATEGORY_ORDER}
    top_cat = max((c for c in CATEGORY_ORDER if cats.get(c,0)>0),
                  key=lambda c: cats[c], default="-")
    top_kws = [k["keyword"] for k in keywords[:7]]
    hot     = [i for i in items if i["importance"]["class"]=="hot"][:3]

    # ── 줄글 요약 생성 ─────────────────────────────────────
    cat_lines = []
    for c in CATEGORY_ORDER:
        n = cats.get(c, 0)
        if n > 0:
            cat_lines.append(f"{c} {n}건")
    cat_summary = ", ".join(cat_lines)

    kw_str = " · ".join(top_kws[:5]) if top_kws else "-"

    # 핫 픽 제목 나열
    hot_titles = ""
    if hot:
        hot_titles = " 특히 " + "、".join(f"'{h['title'][:30]}'" for h in hot[:2]) + " 등이 주목받았습니다."

    prose = (
        f"오늘({NOW_KST.strftime('%m월 %d일')}) 총 {len(items)}건의 AI 자료가 수집됐습니다. "
        f"국내 기사 {kr}건, 해외 기사 {len(items)-kr}건이며 "
        f"분야별로는 {cat_summary}이 수집됐습니다. "
        f"오늘의 핵심 키워드는 {kw_str}로, {top_cat} 분야에서 가장 많은 활동이 관측됐습니다."
        f"{hot_titles}"
    )

    return {
        "date":         NOW_KST.strftime("%Y년 %m월 %d일"),
        "total":        len(items),
        "kr_count":     kr,
        "en_count":     len(items)-kr,
        "top_keywords": top_kws,
        "top_category": top_cat,
        "category_counts": cats,
        "hot_picks":    [{"title":i["title"],"source":i["source"],"url":i["url"]} for i in hot],
        "one_line":     (f"오늘 {len(items)}건 수집 | 국내 {kr}건 · 해외 {len(items)-kr}건 | "
                         f"핫 키워드: {', '.join(top_kws[:3])}"),
        "prose":        prose,   # ★ 줄글 요약
    }

# ─────────────────────────────────────────────────────────
# 누적 집계
# ─────────────────────────────────────────────────────────
def load_history_items(days: int) -> list:
    history_dir = "data/history"
    all_items   = []
    seen_ids    = set()
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

def build_period_json(items, period_label: str, days: int) -> dict:
    cat_stats, src_stats = make_stats(items)
    keywords = extract_keywords(items)
    kr = sum(1 for i in items if i.get("lang")=="ko")

    daily_counts = {}
    for it in items:
        d = it.get("collect_date","")
        if d:
            daily_counts[d] = daily_counts.get(d,0)+1
    daily_timeline = [{"date":k,"count":v} for k,v in sorted(daily_counts.items())]

    cat_daily = {}
    for it in items:
        d   = it.get("collect_date","")
        cat = it.get("category","")
        if d and cat:
            cat_daily.setdefault(d, {})
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

# ─────────────────────────────────────────────────────────
# 메인
# ─────────────────────────────────────────────────────────
def main():
    print(f"\n{'='*55}")
    print(f"  AI 트렌드 뉴스 수집 — {TODAY}")
    print(f"  실행 시각: {NOW_KST.strftime('%Y-%m-%d %H:%M')} KST")
    print(f"{'='*55}\n")

    today_items = []
    for feed in RSS_FEEDS:
        print(f"📡 [{feed['category']}] {feed['name']} 수집 중...")
        today_items.extend(fetch_feed(feed))

    # 중복 URL 제거
    seen = set()
    deduped = []
    for it in today_items:
        if it["url"] not in seen:
            seen.add(it["url"])
            deduped.append(it)
    today_items = deduped

    # 카테고리 순서 정렬
    today_items.sort(
        key=lambda x: CATEGORY_ORDER.index(x["category"])
        if x["category"] in CATEGORY_ORDER else 99
    )
    for i, item in enumerate(today_items):
        item["id"] = f"{TODAY}_{i:04d}"

    kr_cnt = sum(1 for i in today_items if i.get("lang")=="ko")
    print(f"\n오늘 수집: {len(today_items)}건 (국내 {kr_cnt} / 해외 {len(today_items)-kr_cnt})")

    keywords      = extract_keywords(today_items)
    cat_stats, src_stats = make_stats(today_items)
    daily_summary = build_daily_summary(today_items, keywords)

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

    print("\n📊 주간 집계 생성 중...")
    weekly_items  = load_history_items(7)
    weekly_output = build_period_json(weekly_items, "weekly", 7)
    with open("data/weekly.json", "w", encoding="utf-8") as f:
        json.dump(weekly_output, f, ensure_ascii=False, indent=2)
    print(f"✅ data/weekly.json 저장 ({len(weekly_items)}건)")

    print("📊 월간 집계 생성 중...")
    monthly_items  = load_history_items(30)
    monthly_output = build_period_json(monthly_items, "monthly", 30)
    with open("data/monthly.json", "w", encoding="utf-8") as f:
        json.dump(monthly_output, f, ensure_ascii=False, indent=2)
    print(f"✅ data/monthly.json 저장 ({len(monthly_items)}건)")

    history_files = sorted(glob.glob("data/history/*.json"))
    print(f"\n📁 누적 보관: {len(history_files)}일치")
    print(f"\n✅ 완료! 카테고리: {list(cat_stats.keys())}")
    print(f"   핫 키워드: {[k['keyword'] for k in keywords[:5]]}")

if __name__ == "__main__":
    main()

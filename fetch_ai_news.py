#!/usr/bin/env python3
"""
AI 트렌드 - RSS 자동 수집 스크립트 (B방식: 날짜별 누적 저장)

저장 구조:
  data/
  ├── ai_news.json            ← 오늘 데이터 (대시보드 기본 로딩)
  ├── history/
  │   ├── 2026-03-17.json     ← 날짜별 보관
  │   ├── 2026-03-16.json
  │   └── ...
  ├── weekly.json             ← 최근 7일 집계 (매일 자동 생성)
  └── monthly.json            ← 최근 30일 집계 (매일 자동 생성)
"""

import json, feedparser, requests, re, os, glob
from datetime import datetime, timezone, timedelta

KST     = timezone(timedelta(hours=9))
NOW_KST = datetime.now(KST)
TODAY   = NOW_KST.strftime("%Y-%m-%d")

# ── RSS 피드 목록 ─────────────────────────────────────────────
CATEGORY_ORDER = ["콘텐츠", "영상AI", "디자인AI", "논문", "개발AI", "비즈니스"]

RSS_FEEDS = [
    # 🇰🇷 콘텐츠 (한국)
    {"name":"AI타임스",       "url":"https://www.aitimes.com/rss/allArticle.xml",           "category":"콘텐츠",  "badge":"kr-news","lang":"ko","limit":10},
    {"name":"바이라인네트워크","url":"https://byline.network/feed/",                          "category":"콘텐츠",  "badge":"kr-news","lang":"ko","limit":7},
    {"name":"디지털투데이",    "url":"https://www.digitaltoday.co.kr/rss/allArticle.xml",    "category":"콘텐츠",  "badge":"kr-news","lang":"ko","limit":7},
    {"name":"전자신문",        "url":"http://rss.etnews.com/Section901.xml",                 "category":"콘텐츠",  "badge":"kr-news","lang":"ko","limit":7},
    {"name":"더에이아이",      "url":"http://www.newstheai.com/rss/allArticle.xml",          "category":"콘텐츠",  "badge":"kr-news","lang":"ko","limit":6},
    # 🎬 영상AI
    {"name":"Replicate Blog",  "url":"https://replicate.com/blog/rss",                       "category":"영상AI",  "badge":"tool",   "lang":"en","limit":4},
    {"name":"NVIDIA Dev Blog", "url":"https://developer.nvidia.com/blog/feed",               "category":"영상AI",  "badge":"tool",   "lang":"en","limit":4},
    # 🎨 디자인AI
    {"name":"HuggingFace Blog","url":"https://huggingface.co/blog/feed.xml",                 "category":"디자인AI","badge":"official","lang":"en","limit":5},
    # 📄 논문
    {"name":"ArXiv AI",        "url":"https://rss.arxiv.org/rss/cs.AI",                     "category":"논문",    "badge":"paper",  "lang":"en","limit":7},
    {"name":"ArXiv ML",        "url":"https://rss.arxiv.org/rss/cs.LG",                     "category":"논문",    "badge":"paper",  "lang":"en","limit":5},
    {"name":"ArXiv CV",        "url":"https://rss.arxiv.org/rss/cs.CV",                     "category":"논문",    "badge":"paper",  "lang":"en","limit":4},
    {"name":"ArXiv CL",        "url":"https://rss.arxiv.org/rss/cs.CL",                     "category":"논문",    "badge":"paper",  "lang":"en","limit":4},
    # 💻 개발AI
    {"name":"OpenAI",          "url":"https://openai.com/news/rss.xml",                      "category":"개발AI",  "badge":"official","lang":"en","limit":5},
    {"name":"Google AI Blog",  "url":"http://googleaiblog.blogspot.com/atom.xml",            "category":"개발AI",  "badge":"official","lang":"en","limit":4},
    {"name":"DeepMind",        "url":"https://deepmind.google/blog/rss.xml",                 "category":"개발AI",  "badge":"official","lang":"en","limit":4},
    {"name":"LangChain Blog",  "url":"https://blog.langchain.dev/rss/",                      "category":"개발AI",  "badge":"official","lang":"en","limit":4},
    {"name":"MarkTechPost",    "url":"https://www.marktechpost.com/feed/",                   "category":"개발AI",  "badge":"news",   "lang":"en","limit":5},
    # 📊 비즈니스
    {"name":"VentureBeat AI",  "url":"https://venturebeat.com/category/ai/feed/",            "category":"비즈니스","badge":"news",   "lang":"en","limit":5},
    {"name":"MIT Tech Review", "url":"https://www.technologyreview.com/feed/",               "category":"비즈니스","badge":"news",   "lang":"en","limit":4},
    {"name":"AI Business",     "url":"https://aibusiness.com/rss.xml",                       "category":"비즈니스","badge":"news",   "lang":"en","limit":4},
]

HOT_KEYWORDS = [
    "gpt","llm","agent","에이전트","멀티모달","multimodal","diffusion",
    "transformer","claude","gemini","llama","reasoning","추론","생성형",
    "video generation","image generation","rag","fine-tuning","파인튜닝",
    "benchmark","open source","오픈소스","인공지능","딥러닝","chatgpt","sora"
]
KR_AI_KEYWORDS = [
    "인공지능","AI","머신러닝","딥러닝","챗봇","생성형","자연어",
    "이미지 생성","영상 생성","클로드","제미나이","챗GPT","라마",
    "LLM","에이전트","파운데이션 모델","딥시크"
]

# ─────────────────────────────────────────────────────────────
# 유틸 함수
# ─────────────────────────────────────────────────────────────
def clean_html(text):
    if not text: return ""
    t = re.sub(r'<[^>]+>', '', text)
    for r, s in [('&amp;','&'),('&lt;','<'),('&gt;','>'),('&nbsp;',' ')]:
        t = t.replace(r, s)
    t = re.sub(r'\s+', ' ', t).strip()
    return t[:300] + "..." if len(t) > 300 else t

def is_ai_related(title, summary, lang):
    if lang != "ko": return True
    text = (title + " " + summary).lower()
    return any(kw.lower() in text for kw in KR_AI_KEYWORDS)

def get_importance(title, summary=""):
    text = (title + " " + summary).lower()
    n = sum(1 for kw in HOT_KEYWORDS if kw in text)
    if n >= 3: return {"label":"🔥 핫","class":"hot"}
    if n >= 1: return {"label":"⭐ 추천","class":"star"}
    return {"label":"🆕 신규","class":"new"}

def parse_date(entry):
    for attr in ('published_parsed','updated_parsed'):
        t = getattr(entry, attr, None)
        if t:
            try:
                dt = datetime(*t[:6], tzinfo=timezone.utc)
                return dt.astimezone(KST).strftime("%Y-%m-%d %H:%M")
            except: pass
    return NOW_KST.strftime("%Y-%m-%d %H:%M")

def get_thumbnail(entry):
    if getattr(entry,'media_thumbnail',None):
        return entry.media_thumbnail[0].get('url','')
    for enc in getattr(entry,'enclosures',[]):
        if 'image' in enc.get('type',''):
            return enc.get('url','')
    body = (getattr(entry,'summary','') or
            (entry.content[0].get('value','') if getattr(entry,'content',None) else ''))
    m = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', body)
    if m and m.group(1).startswith('http'): return m.group(1)
    return ""

# ─────────────────────────────────────────────────────────────
# 수집
# ─────────────────────────────────────────────────────────────
def fetch_feed(feed_info):
    items = []
    try:
        resp = requests.get(feed_info["url"],
                            headers={"User-Agent":"Mozilla/5.0 (compatible; AI-Trend/2.0)"},
                            timeout=15)
        resp.raise_for_status()
        feed  = feedparser.parse(resp.text)
        count = 0
        for entry in feed.entries:
            if count >= feed_info["limit"]: break
            title   = clean_html(entry.get("title","제목 없음"))
            link    = entry.get("link","#")
            summary = clean_html(
                entry.get("summary","") or
                (entry.content[0].get("value","") if getattr(entry,"content",None) else ""))
            lang = feed_info.get("lang","en")
            if not is_ai_related(title, summary, lang): continue
            items.append({
                "id":        f"{abs(hash(title+link))%999999:06d}",
                "title":     title,
                "summary":   summary,
                "url":       link,
                "source":    feed_info["name"],
                "category":  feed_info["category"],
                "badge":     feed_info["badge"],
                "lang":      lang,
                "date":      parse_date(entry),
                "collect_date": TODAY,          # ★ 수집 날짜 기록
                "thumbnail": get_thumbnail(entry),
                "importance":get_importance(title, summary),
            })
            count += 1
        print(f"  ✅ {feed_info['name']}: {count}건")
    except Exception as e:
        print(f"  ❌ {feed_info['name']}: {e}")
    return items

# ─────────────────────────────────────────────────────────────
# 집계 함수
# ─────────────────────────────────────────────────────────────
def extract_keywords(items):
    target = [
        "LLM","Agent","에이전트","RAG","GPT","Claude","클로드","Gemini","제미나이",
        "Llama","라마","Diffusion","Multimodal","멀티모달","Fine-tuning","파인튜닝",
        "Transformer","Reasoning","추론","Vision","Benchmark","Open Source","오픈소스",
        "Video AI","Image Generation","이미지 생성","생성형 AI","DeepSeek","딥시크",
        "Sora","Runway","인공지능","ChatGPT"
    ]
    freq = {}
    for item in items:
        text = (item["title"] + " " + item["summary"]).lower()
        for kw in target:
            if kw.lower() in text:
                freq[kw] = freq.get(kw,0) + 1
    return [{"keyword":k,"count":v}
            for k,v in sorted(freq.items(), key=lambda x:-x[1])[:20]]

def make_stats(items):
    cat, src = {}, {}
    for it in items:
        cat[it["category"]] = cat.get(it["category"],0)+1
        src[it["source"]]   = src.get(it["source"],0)+1
    # 카테고리 순서 유지
    ordered_cat = {k:cat[k] for k in CATEGORY_ORDER if k in cat}
    sorted_src  = [{"source":k,"count":v}
                   for k,v in sorted(src.items(),key=lambda x:-x[1])]
    return ordered_cat, sorted_src

def build_daily_summary(items, keywords):
    kr = sum(1 for i in items if i.get("lang")=="ko")
    top_cat = max((c for c in CATEGORY_ORDER if c in {i["category"] for i in items}),
                  key=lambda c: sum(1 for i in items if i["category"]==c), default="-")
    top_kws = [k["keyword"] for k in keywords[:5]]
    hot     = [i for i in items if i["importance"]["class"]=="hot"][:3]
    return {
        "date":         NOW_KST.strftime("%Y년 %m월 %d일"),
        "total":        len(items),
        "kr_count":     kr,
        "en_count":     len(items)-kr,
        "top_keywords": top_kws,
        "top_category": top_cat,
        "hot_picks":    [{"title":i["title"],"source":i["source"],"url":i["url"]} for i in hot],
        "one_line":     (f"오늘은 총 {len(items)}건의 AI 자료가 수집됐습니다. "
                         f"국내 기사 {kr}건, 해외 기사 {len(items)-kr}건이며, "
                         f"'{top_kws[0] if top_kws else '-'}' 키워드가 가장 주목받고 있습니다."),
    }

# ─────────────────────────────────────────────────────────────
# ★ 누적 집계: history/ 폴더에서 N일치 읽어 합산
# ─────────────────────────────────────────────────────────────
def load_history_items(days: int) -> list:
    """history/ 폴더에서 최근 days일치 아이템 모두 읽기"""
    history_dir = "data/history"
    all_items   = []
    seen_ids    = set()

    # 날짜 내림차순으로 최대 days개 파일
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
    """주간/월간 집계 JSON 생성"""
    cat_stats, src_stats = make_stats(items)
    keywords = extract_keywords(items)
    kr = sum(1 for i in items if i.get("lang")=="ko")

    # 날짜별 수집 건수 (타임라인용)
    daily_counts = {}
    for it in items:
        d = it.get("collect_date","")
        if d:
            daily_counts[d] = daily_counts.get(d,0)+1
    daily_timeline = [{"date":k,"count":v}
                      for k,v in sorted(daily_counts.items())]

    # 카테고리별 트렌드 (날짜 × 카테고리)
    cat_daily = {}
    for it in items:
        d   = it.get("collect_date","")
        cat = it.get("category","")
        if d and cat:
            cat_daily.setdefault(d, {})
            cat_daily[d][cat] = cat_daily[d].get(cat,0)+1

    return {
        "period":         period_label,
        "days":           days,
        "generated_at":   NOW_KST.strftime("%Y-%m-%d %H:%M"),
        "total":          len(items),
        "kr_count":       kr,
        "en_count":       len(items)-kr,
        "category_stats": cat_stats,
        "source_stats":   src_stats,
        "keywords":       keywords,
        "daily_timeline": daily_timeline,
        "cat_daily":      cat_daily,
        "items":          items,          # 전체 아이템 (주간/월간 카드용)
    }

# ─────────────────────────────────────────────────────────────
# 메인
# ─────────────────────────────────────────────────────────────
def main():
    print(f"\n{'='*55}")
    print(f"  AI 트렌드 뉴스 수집 — {TODAY}")
    print(f"  실행 시각: {NOW_KST.strftime('%Y-%m-%d %H:%M')} KST")
    print(f"{'='*55}\n")

    # 1) 오늘 기사 수집
    today_items = []
    for feed in RSS_FEEDS:
        print(f"📡 [{feed['category']}] {feed['name']} 수집 중...")
        today_items.extend(fetch_feed(feed))

    # 카테고리 순서 정렬
    today_items.sort(key=lambda x: CATEGORY_ORDER.index(x["category"])
                                   if x["category"] in CATEGORY_ORDER else 99)
    for i, item in enumerate(today_items):
        item["id"] = f"{TODAY}_{i:04d}"

    kr_cnt = sum(1 for i in today_items if i.get("lang")=="ko")
    print(f"\n오늘 수집: {len(today_items)}건 (국내 {kr_cnt} / 해외 {len(today_items)-kr_cnt})")

    keywords   = extract_keywords(today_items)
    cat_stats, src_stats = make_stats(today_items)
    daily_summary = build_daily_summary(today_items, keywords)

    # 2) 오늘 데이터 저장
    os.makedirs("data/history", exist_ok=True)

    today_output = {
        "generated_at":  NOW_KST.strftime("%Y-%m-%d %H:%M"),
        "date":          TODAY,
        "total":         len(today_items),
        "items":         today_items,
        "keywords":      keywords,
        "category_stats":cat_stats,
        "source_stats":  src_stats,
        "daily_summary": daily_summary,
    }

    # data/ai_news.json  ← 오늘 데이터 (대시보드 기본)
    with open("data/ai_news.json", "w", encoding="utf-8") as f:
        json.dump(today_output, f, ensure_ascii=False, indent=2)
    print(f"✅ data/ai_news.json 저장")

    # data/history/YYYY-MM-DD.json  ← 날짜별 보관
    hist_path = f"data/history/{TODAY}.json"
    with open(hist_path, "w", encoding="utf-8") as f:
        json.dump(today_output, f, ensure_ascii=False, indent=2)
    print(f"✅ {hist_path} 저장")

    # 3) 주간 집계 (최근 7일)
    print("\n📊 주간 집계 생성 중...")
    weekly_items  = load_history_items(7)
    weekly_output = build_period_json(weekly_items, "weekly", 7)
    with open("data/weekly.json", "w", encoding="utf-8") as f:
        json.dump(weekly_output, f, ensure_ascii=False, indent=2)
    print(f"✅ data/weekly.json 저장 ({len(weekly_items)}건)")

    # 4) 월간 집계 (최근 30일)
    print("📊 월간 집계 생성 중...")
    monthly_items  = load_history_items(30)
    monthly_output = build_period_json(monthly_items, "monthly", 30)
    with open("data/monthly.json", "w", encoding="utf-8") as f:
        json.dump(monthly_output, f, ensure_ascii=False, indent=2)
    print(f"✅ data/monthly.json 저장 ({len(monthly_items)}건)")

    # 5) 보관 현황 출력
    history_files = sorted(glob.glob("data/history/*.json"))
    print(f"\n📁 누적 보관: {len(history_files)}일치")
    for fp in history_files[-5:]:
        print(f"   {os.path.basename(fp)}")
    if len(history_files) > 5:
        print(f"   ... 외 {len(history_files)-5}일치")

    print(f"\n✅ 완료! 카테고리: {list(cat_stats.keys())}")
    print(f"   핫 키워드: {[k['keyword'] for k in keywords[:5]]}")

if __name__ == "__main__":
    main()

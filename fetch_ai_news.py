#!/usr/bin/env python3
"""
AI PULSE - 실제 RSS/API 기반 AI 뉴스 자동 수집 스크립트
GitHub Actions에서 매일 오전 7시(KST) 자동 실행
"""

import json
import feedparser
import requests
import re
import os
from datetime import datetime, timezone, timedelta
from urllib.parse import quote

# ─── 한국 시간대 ───────────────────────────────────────────────
KST = timezone(timedelta(hours=9))
NOW_KST = datetime.now(KST)

# ─── 수집할 RSS 피드 목록 ───────────────────────────────────────
RSS_FEEDS = [
    # ── 논문 (ArXiv) ──
    {
        "name": "ArXiv AI",
        "url": "https://rss.arxiv.org/rss/cs.AI",
        "category": "논문",
        "badge": "paper",
        "icon": "🟣",
        "limit": 8,
    },
    {
        "name": "ArXiv ML",
        "url": "https://rss.arxiv.org/rss/cs.LG",
        "category": "논문",
        "badge": "paper",
        "icon": "🟣",
        "limit": 6,
    },
    {
        "name": "ArXiv CV",
        "url": "https://rss.arxiv.org/rss/cs.CV",
        "category": "논문",
        "badge": "paper",
        "icon": "🟣",
        "limit": 5,
    },
    {
        "name": "ArXiv CL",
        "url": "https://rss.arxiv.org/rss/cs.CL",
        "category": "논문",
        "badge": "paper",
        "icon": "🟣",
        "limit": 5,
    },
    # ── 공식 블로그 ──
    {
        "name": "OpenAI",
        "url": "https://openai.com/news/rss.xml",
        "category": "개발AI",
        "badge": "official",
        "icon": "🔵",
        "limit": 5,
    },
    {
        "name": "HuggingFace Blog",
        "url": "https://huggingface.co/blog/feed.xml",
        "category": "개발AI",
        "badge": "official",
        "icon": "🔵",
        "limit": 5,
    },
    {
        "name": "Google AI Blog",
        "url": "http://googleaiblog.blogspot.com/atom.xml",
        "category": "개발AI",
        "badge": "official",
        "icon": "🔵",
        "limit": 4,
    },
    {
        "name": "DeepMind",
        "url": "https://deepmind.google/blog/rss.xml",
        "category": "개발AI",
        "badge": "official",
        "icon": "🔵",
        "limit": 4,
    },
    {
        "name": "LangChain Blog",
        "url": "https://blog.langchain.dev/rss/",
        "category": "개발AI",
        "badge": "official",
        "icon": "🔵",
        "limit": 4,
    },
    # ── 뉴스 ──
    {
        "name": "VentureBeat AI",
        "url": "https://venturebeat.com/category/ai/feed/",
        "category": "비즈니스",
        "badge": "news",
        "icon": "🟢",
        "limit": 6,
    },
    {
        "name": "MIT Tech Review",
        "url": "https://www.technologyreview.com/feed/",
        "category": "비즈니스",
        "badge": "news",
        "icon": "🟢",
        "limit": 4,
    },
    {
        "name": "MarkTechPost",
        "url": "https://www.marktechpost.com/feed/",
        "category": "개발AI",
        "badge": "news",
        "icon": "🟢",
        "limit": 5,
    },
    {
        "name": "KDnuggets",
        "url": "https://www.kdnuggets.com/feed",
        "category": "개발AI",
        "badge": "news",
        "icon": "🟢",
        "limit": 4,
    },
    {
        "name": "AI Business",
        "url": "https://aibusiness.com/rss.xml",
        "category": "비즈니스",
        "badge": "news",
        "icon": "🟢",
        "limit": 4,
    },
    # ── AI 도구/영상/디자인 ──
    {
        "name": "Replicate Blog",
        "url": "https://replicate.com/blog/rss",
        "category": "영상AI",
        "badge": "tool",
        "icon": "🔴",
        "limit": 3,
    },
    {
        "name": "Stability AI Blog",
        "url": "https://stability.ai/blog/rss.xml",
        "category": "영상AI",
        "badge": "tool",
        "icon": "🔴",
        "limit": 3,
    },
    {
        "name": "NVIDIA Dev Blog",
        "url": "https://developer.nvidia.com/blog/feed",
        "category": "개발AI",
        "badge": "tool",
        "icon": "🟡",
        "limit": 4,
    },
]

# ─── 카테고리 → 중요도 키워드 맵 ────────────────────────────────
HOT_KEYWORDS = [
    "gpt", "llm", "agent", "multimodal", "diffusion", "transformer",
    "claude", "gemini", "llama", "mistral", "phi", "reasoning",
    "video generation", "image generation", "rag", "fine-tuning",
    "benchmark", "open source", "rlhf", "sft", "moe", "vision"
]

def clean_html(text):
    """HTML 태그 제거"""
    if not text:
        return ""
    clean = re.sub(r'<[^>]+>', '', text)
    clean = re.sub(r'\s+', ' ', clean).strip()
    return clean[:280] + "..." if len(clean) > 280 else clean

def get_importance(title, summary=""):
    """중요도 태그 결정"""
    text = (title + " " + summary).lower()
    hot_count = sum(1 for kw in HOT_KEYWORDS if kw in text)
    if hot_count >= 3:
        return {"label": "🔥 핫", "class": "hot"}
    elif hot_count >= 1:
        return {"label": "⭐ 추천", "class": "star"}
    else:
        return {"label": "🆕 신규", "class": "new"}

def parse_date(entry):
    """날짜 파싱 (여러 형식 처리)"""
    try:
        if hasattr(entry, 'published_parsed') and entry.published_parsed:
            dt = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
            return dt.astimezone(KST).strftime("%Y-%m-%d %H:%M")
        if hasattr(entry, 'updated_parsed') and entry.updated_parsed:
            dt = datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc)
            return dt.astimezone(KST).strftime("%Y-%m-%d %H:%M")
    except Exception:
        pass
    return NOW_KST.strftime("%Y-%m-%d %H:%M")

def get_thumbnail(entry, source_name):
    """썸네일 URL 추출 (없으면 소스별 기본 이미지)"""
    # media:thumbnail
    if hasattr(entry, 'media_thumbnail') and entry.media_thumbnail:
        return entry.media_thumbnail[0].get('url', '')
    # enclosure
    if hasattr(entry, 'enclosures') and entry.enclosures:
        for enc in entry.enclosures:
            if 'image' in enc.get('type', ''):
                return enc.get('url', '')
    # 본문에서 img 태그 추출
    content = ""
    if hasattr(entry, 'summary'):
        content = entry.summary
    elif hasattr(entry, 'content') and entry.content:
        content = entry.content[0].get('value', '')
    match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', content)
    if match:
        return match.group(1)
    return ""

def fetch_feed(feed_info):
    """단일 RSS 피드 수집"""
    items = []
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; AI-PULSE/1.0; +https://github.com/ai-pulse)"
        }
        resp = requests.get(feed_info["url"], headers=headers, timeout=15)
        resp.raise_for_status()
        feed = feedparser.parse(resp.text)
        
        count = 0
        for entry in feed.entries:
            if count >= feed_info["limit"]:
                break

            title = clean_html(entry.get("title", "제목 없음"))
            link  = entry.get("link", "#")
            summary = clean_html(
                entry.get("summary", "") or
                (entry.get("content", [{}])[0].get("value", "") if entry.get("content") else "")
            )
            pub_date = parse_date(entry)
            thumbnail = get_thumbnail(entry, feed_info["name"])
            importance = get_importance(title, summary)

            items.append({
                "id": f"{feed_info['badge']}_{count}_{abs(hash(title)) % 99999:05d}",
                "title": title,
                "summary": summary,
                "url": link,
                "source": feed_info["name"],
                "category": feed_info["category"],
                "badge": feed_info["badge"],
                "icon": feed_info["icon"],
                "date": pub_date,
                "thumbnail": thumbnail,
                "importance": importance,
            })
            count += 1

        print(f"  ✅ {feed_info['name']}: {count}건 수집")
    except Exception as e:
        print(f"  ❌ {feed_info['name']} 실패: {e}")
    return items

def extract_keywords(items):
    """전체 기사에서 키워드 빈도 추출"""
    freq = {}
    target_kws = [
        "LLM", "Agent", "RAG", "GPT", "Claude", "Gemini", "Llama",
        "Diffusion", "Multimodal", "Fine-tuning", "Transformer",
        "Reasoning", "Vision", "Benchmark", "Open Source",
        "Video AI", "Image Generation", "RLHF", "MoE", "Mistral",
        "Phi", "Qwen", "DeepSeek", "Sora", "Runway", "Stable Diffusion"
    ]
    for item in items:
        text = (item["title"] + " " + item["summary"]).lower()
        for kw in target_kws:
            if kw.lower() in text:
                freq[kw] = freq.get(kw, 0) + 1
    sorted_kw = sorted(freq.items(), key=lambda x: -x[1])
    return [{"keyword": k, "count": v} for k, v in sorted_kw[:20]]

def category_stats(items):
    """카테고리별 통계"""
    stats = {}
    for item in items:
        cat = item["category"]
        stats[cat] = stats.get(cat, 0) + 1
    return stats

def source_stats(items):
    """소스별 통계"""
    stats = {}
    for item in items:
        src = item["source"]
        stats[src] = stats.get(src, 0) + 1
    return [{"source": k, "count": v} for k, v in sorted(stats.items(), key=lambda x: -x[1])]

def main():
    print(f"\n{'='*50}")
    print(f" AI PULSE 뉴스 수집 시작")
    print(f" 실행 시각: {NOW_KST.strftime('%Y-%m-%d %H:%M')} KST")
    print(f"{'='*50}\n")

    all_items = []
    for feed in RSS_FEEDS:
        print(f"📡 [{feed['category']}] {feed['name']} 수집 중...")
        items = fetch_feed(feed)
        all_items.extend(items)

    # ID 재부여 (중복 방지)
    for i, item in enumerate(all_items):
        item["id"] = f"item_{i:04d}"

    print(f"\n총 {len(all_items)}건 수집 완료\n")

    # 키워드 / 통계
    keywords  = extract_keywords(all_items)
    cat_stats = category_stats(all_items)
    src_stats = source_stats(all_items)

    # 최종 data.json 생성
    output = {
        "generated_at": NOW_KST.strftime("%Y-%m-%d %H:%M"),
        "generated_at_iso": NOW_KST.isoformat(),
        "total": len(all_items),
        "items": all_items,
        "keywords": keywords,
        "category_stats": cat_stats,
        "source_stats": src_stats,
    }

    os.makedirs("data", exist_ok=True)
    with open("data/ai_news.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print("✅ data/ai_news.json 저장 완료")
    print(f"   - 총 기사: {len(all_items)}건")
    print(f"   - 키워드: {len(keywords)}개")
    print(f"   - 카테고리: {list(cat_stats.keys())}")

if __name__ == "__main__":
    main()

'use strict';

/* ═══════════════════════════════════════════════════════════
   AI 트렌드 대시보드 — app.js v7
   ─ 일간: data/ai_news.json
   ─ 주간: data/weekly.json
   ─ 월간: data/monthly.json

   v7 변경:
   - 핵심 포인트: 헤드라인 카피 → 원문 인사이트 서술문
   - 해외 기사 썸네일: one_line_kr (번역된 한 줄 요약) 표시
   - 주간/월간 리포트: 수집량 중심 → 내용/키워드/트렌드 중심
   - 이미지·디자인AI 소스 추가 반영
═══════════════════════════════════════════════════════════ */

let TODAY_DATA   = null;
let WEEKLY_DATA  = null;
let MONTHLY_DATA = null;

let ALL_ITEMS    = [];
let KEYWORDS     = [];
let CAT_STATS    = {};
let SOURCE_STATS = [];
let DAILY_SUMMARY = null;

let currentCat    = '전체';
let currentLang   = 'all';
let currentSearch = '';

let catChartInst, weeklyKeyTrendInst, monthlyCatTrendInst;

// ★ 카테고리
const CAT_ORDER  = ['콘텐츠','영상AI','이미지·디자인AI','LLM','개발AI','논문','비즈니스'];
const CAT_FILTER = ['콘텐츠','영상AI','이미지·디자인AI','LLM','개발AI'];

const CAT_COLORS = {
  '콘텐츠':'#e53e3e',
  '영상AI':'#f97316',
  '이미지·디자인AI':'#ec4899',
  'LLM':'#8b5cf6',
  '개발AI':'#2563eb',
  '논문':'#7c3aed',
  '비즈니스':'#16a34a',
};
const BADGE_CLASS = {
  paper:'badge-paper', official:'badge-official', crawled:'badge-official',
  news:'badge-news',   tool:'badge-tool', 'kr-news':'badge-kr-news',
  gnews:'badge-gnews',
};
const BADGE_LABEL = {
  paper:'논문', official:'공식블로그', crawled:'공식블로그',
  news:'뉴스', tool:'도구', 'kr-news':'국내', gnews:'뉴스집계',
};
const CAT_EMOJI = {
  '콘텐츠':'📰','영상AI':'🎬','이미지·디자인AI':'🖼️',
  'LLM':'🧠','개발AI':'💻','논문':'📄','비즈니스':'📊',
};

// ═══ 1. 데이터 로딩 ═══════════════════════════════════════
async function loadData() {
  showSkeleton(true);
  hideError();
  try {
    const ts = `?_=${Date.now()}`;
    const [todayRes, weeklyRes, monthlyRes] = await Promise.allSettled([
      fetch(`data/ai_news.json${ts}`).then(r => r.ok ? r.json() : null),
      fetch(`data/weekly.json${ts}`).then(r  => r.ok ? r.json() : null),
      fetch(`data/monthly.json${ts}`).then(r => r.ok ? r.json() : null),
    ]);

    TODAY_DATA   = todayRes.value   || null;
    WEEKLY_DATA  = weeklyRes.value  || null;
    MONTHLY_DATA = monthlyRes.value || null;

    if (!TODAY_DATA) throw new Error('ai_news.json을 불러오지 못했습니다.');

    ALL_ITEMS     = TODAY_DATA.items    || [];
    KEYWORDS      = TODAY_DATA.keywords || [];
    CAT_STATS     = TODAY_DATA.category_stats || {};
    SOURCE_STATS  = TODAY_DATA.source_stats   || [];
    DAILY_SUMMARY = TODAY_DATA.daily_summary  || null;

    document.getElementById('updateTime').textContent =
      `마지막 업데이트: ${TODAY_DATA.generated_at || '-'} KST`;

    renderAll();
  } catch (err) {
    showSkeleton(false);
    showError(
      `데이터 로딩 실패: ${err.message}\n\n` +
      `GitHub Actions 첫 실행 후 data/ai_news.json이 생성됩니다.\n` +
      `Actions 탭 → Run workflow → 완료 후 새로고침`
    );
  }
}

// ═══ 2. 전체 렌더링 ══════════════════════════════════════
function renderAll() {
  showSkeleton(false);
  renderDailySummary();
  renderNewsList();
  renderSidebar();
  renderWeekly();
  renderMonthly();
}

// ═══ 3. 뉴스 리스트 ══════════════════════════════════════
function getFilteredItems(items = ALL_ITEMS) {
  if (currentCat !== '전체')
    items = items.filter(it => it.category === currentCat);
  if (currentLang !== 'all')
    items = items.filter(it => (it.lang || 'en') === currentLang);
  if (currentSearch) {
    const q = currentSearch.toLowerCase();
    items = items.filter(it =>
      (it.title||'').toLowerCase().includes(q) ||
      (it.summary||'').toLowerCase().includes(q) ||
      (it.source||'').toLowerCase().includes(q)
    );
  }
  return items;
}

function renderNewsList() {
  const listEl = document.getElementById('newsList');
  listEl.innerHTML = '';
  const items = getFilteredItems();

  document.getElementById('resultCount').textContent =
    items.length > 0 ? `${items.length}건` : '';

  if (!items.length) {
    listEl.innerHTML = `
      <div class="empty-state">
        <i class="fa-solid fa-search"></i>
        <p>검색 결과가 없습니다.</p>
      </div>`;
    return;
  }
  items.forEach(item => listEl.appendChild(buildListItem(item)));
}

function buildListItem(item) {
  const a = document.createElement('a');
  a.className = 'news-list-item';
  a.href      = item.url || '#';
  a.target    = '_blank';
  a.rel       = 'noopener noreferrer';

  const bCls   = BADGE_CLASS[item.badge] || 'badge-news';
  const bLbl   = BADGE_LABEL[item.badge] || item.badge;
  const impCls = item.importance?.class === 'hot'  ? 'imp-hot'
               : item.importance?.class === 'star' ? 'imp-star' : 'imp-new';
  const impLbl = item.importance?.label || '🆕';
  const emoji  = CAT_EMOJI[item.category] || '📰';
  const isKr   = item.lang === 'ko';

  // ★ 한 줄 요약: 한국어 기사는 one_line / 해외 기사는 one_line_kr(번역) 우선
  let displayLine = '';
  if (isKr) {
    displayLine = item.one_line || firstSentence(item.summary) || '';
  } else {
    displayLine = item.one_line_kr || item.one_line || firstSentence(item.summary) || '';
  }

  const thumbHTML = item.thumbnail
    ? `<img class="list-thumb" src="${esc(item.thumbnail)}" alt="" loading="lazy"
           onerror="this.style.display='none';this.nextElementSibling.style.display='flex'">`
    : '';
  const phStyle = item.thumbnail ? 'style="display:none"' : '';

  a.innerHTML = `
    <div class="list-thumb-wrap">
      ${thumbHTML}
      <div class="list-thumb-placeholder" ${phStyle}>${emoji}</div>
    </div>
    <div class="list-body">
      <div class="list-meta">
        <span class="badge ${bCls}">${bLbl}</span>
        <span class="imp-tag ${impCls}">${impLbl}</span>
        ${isKr ? '<span class="lang-ko">🇰🇷</span>' : ''}
        <span class="list-source">${esc(item.source)}</span>
        <span class="list-cat">${emoji} ${esc(item.category)}</span>
      </div>
      <div class="list-title">${esc(item.title)}</div>
      <div class="list-oneline">${esc(displayLine)}</div>
    </div>
    <div class="list-right">
      <span class="list-date">${formatDateShort(item.date)}</span>
      <span class="list-arrow">→</span>
    </div>`;
  return a;
}

function firstSentence(text) {
  if (!text) return '';
  const idx = text.search(/[.。!?]/);
  if (idx > 10 && idx < 100) return text.slice(0, idx + 1);
  return text.slice(0, 90) + (text.length > 90 ? '…' : '');
}

function formatDateShort(dateStr) {
  if (!dateStr) return '';
  const m = dateStr.match(/\d{4}-(\d{2}-\d{2} \d{2}:\d{2})/);
  return m ? m[1] : dateStr;
}

// ═══ 4. 사이드바 ══════════════════════════════════════════
function renderSidebar() {
  const ul = document.getElementById('sourceList');
  ul.innerHTML = '';
  SOURCE_STATS.slice(0, 10).forEach(s => {
    const li = document.createElement('li');
    li.className = 'source-item';
    li.innerHTML = `<span class="source-name">${esc(s.source)}</span>
                    <span class="source-count">${s.count}</span>`;
    ul.appendChild(li);
  });

  const wrap = document.getElementById('keywordsWrap');
  wrap.innerHTML = '';
  const top = KEYWORDS.slice(0, 10);
  const max = top[0]?.count || 1;
  top.forEach(kw => {
    const pct = Math.round((kw.count / max) * 100);
    const row = document.createElement('div');
    row.className = 'kw-row';
    row.innerHTML = `
      <span class="kw-label">${esc(kw.keyword)}</span>
      <div class="kw-bar-wrap"><div class="kw-bar" style="width:${pct}%"></div></div>
      <span class="kw-count">${kw.count}</span>`;
    wrap.appendChild(row);
  });

  renderCatChart();
}

function renderCatChart() {
  const ctx = document.getElementById('catChart');
  if (!ctx) return;
  if (catChartInst) catChartInst.destroy();

  const labels = CAT_ORDER.filter(c => CAT_STATS[c]);
  const values = labels.map(c => CAT_STATS[c] || 0);
  const colors = labels.map(c => CAT_COLORS[c] || '#888');

  catChartInst = new Chart(ctx, {
    type: 'doughnut',
    data: { labels, datasets: [{ data: values, backgroundColor: colors, borderWidth: 0 }] },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: {
        legend: { position:'bottom', labels:{ color: getColor('--text2'), font:{ size:10 }, padding:6 } }
      }
    }
  });
}

// ═══ 5. 오늘의 요약 ══════════════════════════════════════
function renderDailySummary() {
  const section = document.getElementById('dailySummarySection');
  if (!section) return;
  section.style.display = 'block';

  const d = DAILY_SUMMARY;
  document.getElementById('summaryDate').textContent = d?.date || NOW_KST_STR();

  const krCount = ALL_ITEMS.filter(i => i.lang === 'ko').length;
  document.getElementById('summaryStats').innerHTML = `
    <span class="stat-badge">총 <strong>${ALL_ITEMS.length}건</strong></span>
    <span class="stat-badge">🇰🇷 국내 <strong>${krCount}건</strong></span>
    <span class="stat-badge">🌐 해외 <strong>${ALL_ITEMS.length - krCount}건</strong></span>
    <span class="stat-badge">소스 <strong>${SOURCE_STATS.length}개</strong></span>`;

  const proseEl = document.getElementById('summaryProse');
  if (proseEl) {
    proseEl.textContent = d?.prose || d?.one_line ||
      `오늘 총 ${ALL_ITEMS.length}건의 AI 자료가 수집됐습니다.`;
  }

  // 핵심 키워드
  const kwEl = document.getElementById('summaryKeywords');
  kwEl.innerHTML = '';
  (d?.top_keywords?.length ? d.top_keywords : KEYWORDS.slice(0,7).map(k=>k.keyword))
    .forEach(kw => {
      const chip = document.createElement('span');
      chip.className = 'kw-chip kw-size-3';
      chip.textContent = kw;
      kwEl.appendChild(chip);
    });

  // ★ 핵심 포인트 5개 (인사이트 서술문)
  const pointsEl = document.getElementById('summaryKeyPoints');
  if (pointsEl) {
    pointsEl.innerHTML = '';
    const pts = d?.key_points || [];
    if (pts.length) {
      pts.forEach((pt, i) => {
        const li = document.createElement('li');
        li.className = 'key-point-item';
        li.innerHTML = `<span class="kp-num">${i+1}</span><span class="kp-text">${esc(pt)}</span>`;
        pointsEl.appendChild(li);
      });
    } else {
      const fallback = ALL_ITEMS.filter(i => i.importance?.class !== 'new').slice(0, 5);
      fallback.forEach((it, i) => {
        const li = document.createElement('li');
        li.className = 'key-point-item';
        li.innerHTML = `<span class="kp-num">${i+1}</span>
          <span class="kp-text">${esc((it.one_line_kr || it.one_line || it.title).slice(0,80))}</span>`;
        pointsEl.appendChild(li);
      });
    }
  }

  // 추천 픽
  const picksEl = document.getElementById('summaryPicks');
  picksEl.innerHTML = '';
  const hotPicks = d?.hot_picks?.length
    ? d.hot_picks
    : ALL_ITEMS.filter(i => i.importance?.class === 'hot').slice(0,3)
        .map(i => ({ title:i.title, source:i.source, url:i.url }));
  const picks = hotPicks.length ? hotPicks : ALL_ITEMS.slice(0,3).map(i=>({title:i.title,source:i.source,url:i.url}));
  picks.forEach((p, idx) => picksEl.appendChild(buildPickItem(idx+1, p.title, p.source, p.url)));
}

function buildPickItem(num, title, source, url) {
  const a = document.createElement('a');
  a.className = 'pick-item';
  a.href      = url || '#';
  a.target    = '_blank';
  a.rel       = 'noopener noreferrer';
  a.innerHTML = `
    <div class="pick-num">${num}</div>
    <div class="pick-info">
      <div class="pick-title">${esc(title)}</div>
      <div class="pick-source">${esc(source)}</div>
    </div>`;
  return a;
}

// ═══ 6. 주간 리포트 (내용 중심 v7) ══════════════════════
function renderWeekly() {
  const W = WEEKLY_DATA;

  // 날짜 범위
  const rangeEl = document.getElementById('weekRange');
  if (W?.daily_timeline?.length) {
    const dates = W.daily_timeline.map(d => d.date);
    rangeEl.textContent = `${dates[0]} ~ ${dates[dates.length-1]}`;
  } else {
    const now = new Date();
    const mon = new Date(now); mon.setDate(now.getDate() - now.getDay() + 1);
    const sun = new Date(mon); sun.setDate(mon.getDate() + 6);
    rangeEl.textContent = `${fmtDate(mon)} ~ ${fmtDate(sun)}`;
  }

  const wItems = W?.items || ALL_ITEMS;
  const wKw    = W?.keywords || KEYWORDS;

  // 누적 정보
  document.getElementById('wAccumInfo').innerHTML =
    `<span class="acc-badge">📅 ${W?.daily_timeline?.length || 1}일치 데이터</span>` +
    `<span class="acc-badge">📰 총 ${W?.total || wItems.length}건 수집</span>` +
    `<span class="acc-badge">🔥 핫이슈 ${(W?.content_highlights||[]).filter(i=>i.importance?.class==='hot').length}건</span>`;

  // ★ 이번 주 핵심 뉴스 (content_highlights)
  renderWeeklyHighlights(W?.content_highlights || wItems.filter(i=>i.importance?.class!=='new').slice(0,8));

  // ★ 카테고리별 대표 소식
  renderCatHighlights('weeklyCatHighlights', W?.cat_highlights || {});

  // ★ 이번 주 핵심 포인트
  renderPeriodKeyPoints('weeklyKeyPoints', W?.period_key_points || []);

  // ★ 이번 주 핵심 요약 문장
  const proseEl = document.getElementById('weeklyProse');
  if (proseEl) proseEl.textContent = W?.period_prose || '';

  // 키워드 히트맵
  renderKeywordHeatmap('weeklyKeywords', wKw.slice(0, 16));

  // ★ 키워드 트렌드 차트 (상위 5개 키워드 선 그래프)
  renderKeywordTrendChart('weeklyKeyTrendChart', W);

  // 리포트 다운로드
  document.getElementById('dlBtn').onclick = () => downloadReport(W || TODAY_DATA);
}

function renderWeeklyHighlights(items) {
  const el = document.getElementById('weeklyHighlights');
  if (!el) return;
  el.innerHTML = '';
  if (!items || !items.length) {
    el.innerHTML = '<p class="no-data-msg">데이터 누적 중입니다.</p>';
    return;
  }
  items.slice(0, 8).forEach(item => {
    const div = document.createElement('div');
    div.className = 'highlight-item';
    const impCls = item.importance?.class === 'hot' ? 'imp-hot'
                 : item.importance?.class === 'star' ? 'imp-star' : 'imp-new';
    const impLbl = item.importance?.label || '🆕';
    const emoji  = CAT_EMOJI[item.category] || '📰';
    const isKr   = item.lang === 'ko';
    const summary = isKr
      ? (item.one_line || '')
      : (item.one_line_kr || item.one_line || '');

    div.innerHTML = `
      <a href="${esc(item.url||'#')}" target="_blank" rel="noopener" class="highlight-link">
        <div class="hl-meta">
          <span class="imp-tag ${impCls}">${impLbl}</span>
          <span class="hl-cat">${emoji} ${esc(item.category)}</span>
          <span class="hl-source">${esc(item.source)}</span>
          <span class="hl-date">${formatDateShort(item.date)}</span>
        </div>
        <div class="hl-title">${esc(item.title)}</div>
        ${summary ? `<div class="hl-summary">${esc(summary)}</div>` : ''}
      </a>`;
    el.appendChild(div);
  });
}

function renderCatHighlights(elId, catHighlights) {
  const el = document.getElementById(elId);
  if (!el) return;
  el.innerHTML = '';
  const MAIN_CATS = ['콘텐츠','영상AI','이미지·디자인AI','LLM','개발AI'];
  MAIN_CATS.forEach(cat => {
    const h = catHighlights[cat];
    if (!h) return;
    const emoji = CAT_EMOJI[cat] || '📰';
    const div = document.createElement('div');
    div.className = 'cat-highlight-card';
    div.style.borderLeftColor = CAT_COLORS[cat] || '#888';
    div.innerHTML = `
      <div class="ch-header">
        <span class="ch-cat-label">${emoji} ${esc(cat)}</span>
      </div>
      <a href="${esc(h.url||'#')}" target="_blank" rel="noopener" class="ch-link">
        <div class="ch-title">${esc(h.title)}</div>
        ${h.one_line ? `<div class="ch-oneline">${esc(h.one_line)}</div>` : ''}
        <div class="ch-meta">${esc(h.source)} · ${formatDateShort(h.date)}</div>
      </a>`;
    el.appendChild(div);
  });
  if (!el.children.length) {
    el.innerHTML = '<p class="no-data-msg">데이터 누적 중입니다.</p>';
  }
}

function renderPeriodKeyPoints(elId, points) {
  const el = document.getElementById(elId);
  if (!el) return;
  el.innerHTML = '';
  if (!points || !points.length) return;
  points.forEach((pt, i) => {
    const li = document.createElement('li');
    li.className = 'key-point-item';
    li.innerHTML = `<span class="kp-num">${i+1}</span><span class="kp-text">${esc(pt)}</span>`;
    el.appendChild(li);
  });
}

function renderKeywordTrendChart(elId, periodData) {
  const ctx = document.getElementById(elId);
  if (!ctx) return;
  if (weeklyKeyTrendInst) weeklyKeyTrendInst.destroy();

  const timeline = periodData?.daily_timeline || [];
  const catDaily = periodData?.cat_daily || {};
  if (!timeline.length) {
    ctx.parentElement.innerHTML = '<p class="no-data-msg">📅 데이터 누적 중 (2일차부터 표시)</p>';
    return;
  }

  const dates     = timeline.map(d => d.date.slice(5));
  const datesFull = timeline.map(d => d.date);
  const datasets  = CAT_FILTER
    .filter(cat => datesFull.some(d => catDaily[d]?.[cat]))
    .map(cat => ({
      label: cat,
      data: datesFull.map(d => catDaily[d]?.[cat] || 0),
      borderColor: CAT_COLORS[cat],
      backgroundColor: (CAT_COLORS[cat] || '#888') + '22',
      borderWidth: 2.5,
      tension: 0.35,
      fill: false,
      pointRadius: 4,
    }));

  weeklyKeyTrendInst = new Chart(ctx, {
    type: 'line',
    data: { labels: dates, datasets },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: {
        legend: { position:'bottom', labels:{ color:getColor('--text2'), font:{size:10} } }
      },
      scales: {
        x: { ticks:{ color:getColor('--text2') }, grid:{ color:'rgba(128,128,128,0.1)' } },
        y: { ticks:{ color:getColor('--text2') }, grid:{ color:'rgba(128,128,128,0.1)' }, beginAtZero:true }
      }
    }
  });
}

// ═══ 7. 월간 인사이트 (내용 중심 v7) ════════════════════
function renderMonthly() {
  const M = MONTHLY_DATA;

  const rangeEl = document.getElementById('monthRange');
  if (M?.daily_timeline?.length) {
    const dates = M.daily_timeline.map(d => d.date);
    rangeEl.textContent = `${dates[0]} ~ ${dates[dates.length-1]} (${dates.length}일)`;
  } else {
    const now = new Date();
    rangeEl.textContent = `${now.getFullYear()}년 ${now.getMonth()+1}월 기준`;
  }

  const mItems = M?.items || ALL_ITEMS;
  const mKw    = M?.keywords || KEYWORDS;

  // 누적 정보
  const krCount = M?.kr_count ?? mItems.filter(i => i.lang === 'ko').length;
  document.getElementById('mAccumInfo').innerHTML =
    `<span class="acc-badge">📅 ${M?.daily_timeline?.length || 1}일치</span>` +
    `<span class="acc-badge">📰 ${M?.total || mItems.length}건 수집</span>` +
    `<span class="acc-badge">🇰🇷 국내 ${krCount}건</span>` +
    (M ? `` : `<span class="acc-badge warn">⚠️ 누적 데이터 없음</span>`);

  // ★ 월간 핵심 요약
  const proseEl = document.getElementById('monthlySummary');
  if (proseEl) {
    proseEl.innerHTML = M?.period_prose
      ? `<p>${M.period_prose}</p>`
      : `<p>총 <strong>${M?.total || mItems.length}건</strong>의 AI 자료가 수집됐습니다.</p>`;
  }

  // ★ 이달의 핵심 뉴스
  renderWeeklyHighlights_monthly(M?.content_highlights || mItems.filter(i=>i.importance?.class!=='new').slice(0,10));

  // ★ 카테고리별 대표 소식
  renderCatHighlights('monthlyCatHighlights', M?.cat_highlights || {});

  // ★ 월간 핵심 포인트
  renderPeriodKeyPoints('monthlyKeyPoints', M?.period_key_points || []);

  // 키워드 히트맵
  renderKeywordHeatmap('monthlyKeywords', mKw.slice(0, 20));

  // ★ 월간 카테고리 트렌드 (선 그래프)
  renderMonthlyCatTrend(M?.cat_daily || {}, M?.daily_timeline || []);
}

function renderWeeklyHighlights_monthly(items) {
  const el = document.getElementById('monthlyHighlights');
  if (!el) return;
  el.innerHTML = '';
  if (!items || !items.length) {
    el.innerHTML = '<p class="no-data-msg">데이터 누적 중입니다.</p>';
    return;
  }
  items.slice(0, 10).forEach(item => {
    const div = document.createElement('div');
    div.className = 'highlight-item';
    const impCls = item.importance?.class === 'hot' ? 'imp-hot'
                 : item.importance?.class === 'star' ? 'imp-star' : 'imp-new';
    const impLbl = item.importance?.label || '🆕';
    const emoji  = CAT_EMOJI[item.category] || '📰';
    const isKr   = item.lang === 'ko';
    const summary = isKr
      ? (item.one_line || '')
      : (item.one_line_kr || item.one_line || '');

    div.innerHTML = `
      <a href="${esc(item.url||'#')}" target="_blank" rel="noopener" class="highlight-link">
        <div class="hl-meta">
          <span class="imp-tag ${impCls}">${impLbl}</span>
          <span class="hl-cat">${emoji} ${esc(item.category)}</span>
          <span class="hl-source">${esc(item.source)}</span>
          <span class="hl-date">${formatDateShort(item.date)}</span>
        </div>
        <div class="hl-title">${esc(item.title)}</div>
        ${summary ? `<div class="hl-summary">${esc(summary)}</div>` : ''}
      </a>`;
    el.appendChild(div);
  });
}

function renderMonthlyCatTrend(catDaily, timeline) {
  const ctx = document.getElementById('monthlyLineChart');
  if (!ctx) return;
  if (monthlyCatTrendInst) monthlyCatTrendInst.destroy();

  if (!timeline.length) {
    ctx.parentElement.innerHTML = '<p class="no-data-msg">📅 데이터 누적 중 (2일차부터 표시)</p>';
    return;
  }

  const dates     = timeline.map(d => d.date.slice(5));
  const datesFull = timeline.map(d => d.date);
  const datasets  = CAT_FILTER
    .filter(cat => datesFull.some(d => catDaily[d]?.[cat]))
    .map(cat => ({
      label: cat,
      data: datesFull.map(d => catDaily[d]?.[cat] || 0),
      borderColor: CAT_COLORS[cat],
      backgroundColor: (CAT_COLORS[cat] || '#888') + '22',
      borderWidth: 2,
      tension: 0.3,
      fill: false,
      pointRadius: 3,
    }));

  monthlyCatTrendInst = new Chart(ctx, {
    type: 'line',
    data: { labels: dates, datasets },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: {
        legend: { position:'bottom', labels:{ color:getColor('--text2'), font:{size:11} } }
      },
      scales: {
        x: { ticks:{ color:getColor('--text2'), maxRotation:45 }, grid:{ color:'rgba(128,128,128,0.08)' } },
        y: { ticks:{ color:getColor('--text2') }, grid:{ color:'rgba(128,128,128,0.08)' }, beginAtZero:true }
      }
    }
  });
}

// ═══ 8. 공용 위젯 ═════════════════════════════════════════
function renderKeywordHeatmap(elId, keywords) {
  const wrap = document.getElementById(elId);
  if (!wrap) return;
  wrap.innerHTML = '';
  const max = keywords[0]?.count || 1;
  keywords.forEach(kw => {
    const r    = kw.count / max;
    const size = r > 0.8 ? 5 : r > 0.6 ? 4 : r > 0.4 ? 3 : r > 0.2 ? 2 : 1;
    const chip = document.createElement('span');
    chip.className   = `kw-chip kw-size-${size}`;
    chip.textContent = `${kw.keyword} ${kw.count}`;
    wrap.appendChild(chip);
  });
}

// ═══ 9. 리포트 다운로드 ══════════════════════════════════
function downloadReport(data) {
  const now     = new Date();
  const items   = data?.items    || ALL_ITEMS;
  const kws     = data?.keywords || KEYWORDS;
  const catSt   = data?.category_stats || CAT_STATS;
  const srcSt   = data?.source_stats   || SOURCE_STATS;
  const krCount = data?.kr_count ?? items.filter(i=>i.lang==='ko').length;
  const period  = data?.period === 'weekly' ? '주간' : data?.period === 'monthly' ? '월간' : '일간';

  const highlights = data?.content_highlights || items.filter(i=>i.importance?.class!=='new').slice(0,10);

  const lines = [
    `AI 트렌드 — ${period} 리포트`,
    `생성: ${now.toLocaleString('ko-KR')}`,
    `총 수집: ${items.length}건 (국내 ${krCount}건 / 해외 ${items.length-krCount}건)`,
    `${'='.repeat(56)}`,
    '',
    '■ 핵심 요약',
    data?.period_prose || data?.daily_summary?.prose || '-',
    '',
    '■ 이번 기간 핵심 뉴스 TOP 10',
    ...highlights.slice(0,10).map((it,i) => {
      const s = it.lang==='ko' ? (it.one_line||'') : (it.one_line_kr||it.one_line||'');
      return `  ${i+1}. [${it.category}] ${it.title}\n     ${s}\n     ${it.url}`;
    }),
    '',
    '■ 핵심 키워드 TOP 10',
    ...kws.slice(0,10).map((k,i)=>`  ${i+1}. ${k.keyword} (${k.count}회)`),
    '',
    '■ 카테고리별 분포',
    ...CAT_ORDER.filter(c=>catSt[c]).map(c=>`  ${c}: ${catSt[c]}건`),
    '',
    '■ 소스 현황 TOP 10',
    ...srcSt.slice(0,10).map(s=>`  ${s.source}: ${s.count}건`),
    '',
    `${'='.repeat(56)}`,
    'AI 트렌드 대시보드',
  ];
  const blob = new Blob([lines.join('\n')], { type:'text/plain;charset=utf-8' });
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement('a');
  a.href = url;
  a.download = `ai_trend_${period}_${fmtDateFile(now)}.txt`;
  a.click();
  URL.revokeObjectURL(url);
}

// ═══ 10. 이벤트 바인딩 ════════════════════════════════════
function bindEvents() {
  // 탭 전환
  document.querySelectorAll('.nav-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.tab-section').forEach(s => s.classList.remove('active'));
      btn.classList.add('active');
      document.getElementById(`tab-${btn.dataset.tab}`).classList.add('active');
      setTimeout(() => {
        [catChartInst, weeklyKeyTrendInst, monthlyCatTrendInst]
          .forEach(c => c?.resize());
      }, 50);
    });
  });

  buildFilterButtons();

  document.querySelectorAll('.lang-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.lang-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      currentLang = btn.dataset.lang;
      renderNewsList();
    });
  });

  document.getElementById('searchInput').addEventListener('input', e => {
    currentSearch = e.target.value.trim();
    renderNewsList();
  });

  const saved = localStorage.getItem('ai-trend-theme') || 'light';
  applyTheme(saved);
  document.getElementById('themeBtn').addEventListener('click', () => {
    const next = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
    applyTheme(next);
    localStorage.setItem('ai-trend-theme', next);
  });
}

function buildFilterButtons() {
  const container = document.getElementById('filterCats');
  if (!container) return;
  container.innerHTML = '';

  const cats = ['전체', ...CAT_FILTER];
  cats.forEach(cat => {
    const btn = document.createElement('button');
    btn.className = `filter-btn${cat === '전체' ? ' active' : ''}`;
    btn.dataset.cat = cat;
    const emoji = CAT_EMOJI[cat] || '';
    btn.textContent = cat === '전체' ? '전체' : `${emoji} ${cat}`;
    btn.addEventListener('click', () => {
      document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      currentCat = cat;
      renderNewsList();
    });
    container.appendChild(btn);
  });
}

function applyTheme(theme) {
  document.documentElement.dataset.theme = theme;
  const icon = document.querySelector('#themeBtn i');
  if (icon) icon.className = theme === 'dark' ? 'fa-solid fa-sun' : 'fa-solid fa-moon';
  setTimeout(() => {
    [catChartInst, weeklyKeyTrendInst, monthlyCatTrendInst]
      .forEach(c => c?.update());
  }, 80);
}

// ═══ 11. 유틸 ════════════════════════════════════════════
function esc(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g,'&amp;').replace(/</g,'&lt;')
    .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
function fmtDate(d) { return `${d.getMonth()+1}/${d.getDate()}`; }
function fmtDateFile(d) {
  return `${d.getFullYear()}${String(d.getMonth()+1).padStart(2,'0')}${String(d.getDate()).padStart(2,'0')}`;
}
function NOW_KST_STR() {
  return new Date().toLocaleDateString('ko-KR', { year:'numeric', month:'long', day:'numeric' });
}
function getColor(varName) {
  return getComputedStyle(document.documentElement).getPropertyValue(varName).trim() || '#888';
}
function showSkeleton(show) {
  const el = document.getElementById('loadingSkeleton');
  if (el) el.style.display = show ? 'block' : 'none';
}
function showError(msg) {
  const box = document.getElementById('errorBox');
  const p   = document.getElementById('errorMsg');
  if (box && p) { p.textContent = msg; box.style.display = 'block'; }
}
function hideError() {
  const box = document.getElementById('errorBox');
  if (box) box.style.display = 'none';
}

// ═══ 초기화 ═══════════════════════════════════════════════
document.addEventListener('DOMContentLoaded', () => {
  bindEvents();
  loadData();
});

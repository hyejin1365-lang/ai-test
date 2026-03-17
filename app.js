'use strict';
/* ═══════════════════════════════════════════════════════════
   AI 트렌드 대시보드  app.js  v9
   - 오늘 날짜 기사만 피드에 표시 (이전 날짜 기사 숨김)
   - 핵심 인사이트: 구체적·실용적 서술문
   - 주간/월간: 내용 중심 (highlights, cat_highlights, keywords)
═══════════════════════════════════════════════════════════ */

/* ── 전역 상태 ────────────────────────────────────────── */
let TODAY_DATA   = null;
let WEEKLY_DATA  = null;
let MONTHLY_DATA = null;

let ALL_ITEMS    = [];   // 오늘 날짜 기사만
let KEYWORDS     = [];
let CAT_STATS    = {};
let SOURCE_STATS = [];
let DAILY_SUM    = null;
let DATA_DATE    = '';   // ai_news.json 기준 날짜 (YYYY-MM-DD)

let curCat    = '전체';
let curLang   = 'all';
let curSearch = '';

let chartCat, chartWeekly, chartMonthly;

/* ── 상수 ─────────────────────────────────────────────── */
const CAT_ORDER  = ['콘텐츠','영상AI','이미지·디자인AI','LLM','개발AI','논문','비즈니스'];
const CAT_FILTER = ['콘텐츠','영상AI','이미지·디자인AI','LLM','개발AI'];

const CAT_COLOR = {
  '콘텐츠':'#e53e3e', '영상AI':'#f97316',
  '이미지·디자인AI':'#ec4899', 'LLM':'#8b5cf6',
  '개발AI':'#2563eb', '논문':'#7c3aed', '비즈니스':'#16a34a',
};
const CAT_EMOJI = {
  '콘텐츠':'📰','영상AI':'🎬','이미지·디자인AI':'🖼️',
  'LLM':'🧠','개발AI':'💻','논문':'📄','비즈니스':'📊',
};

/* badge → CSS class + label */
const BADGE = {
  'kr-news': { cls:'badge-kr',   lbl:'국내'     },
  official:  { cls:'badge-off',  lbl:'공식'     },
  crawled:   { cls:'badge-off',  lbl:'공식블로그'},
  news:      { cls:'badge-news', lbl:'뉴스'     },
  gnews:     { cls:'badge-gn',   lbl:'뉴스집계' },
  paper:     { cls:'badge-paper',lbl:'논문'     },
  tool:      { cls:'badge-tool', lbl:'도구'     },
};

/* ════════════════════════════════════════════════════════
   1. 데이터 로딩
════════════════════════════════════════════════════════ */
async function loadData() {
  showSkeleton(true);
  hideError();
  try {
    const ts = `?_=${Date.now()}`;
    const [r1, r2, r3] = await Promise.allSettled([
      fetch(`data/ai_news.json${ts}`).then(r => r.ok ? r.json() : null),
      fetch(`data/weekly.json${ts}` ).then(r => r.ok ? r.json() : null),
      fetch(`data/monthly.json${ts}`).then(r => r.ok ? r.json() : null),
    ]);

    TODAY_DATA   = r1.value || null;
    WEEKLY_DATA  = r2.value || null;
    MONTHLY_DATA = r3.value || null;

    if (!TODAY_DATA) throw new Error('data/ai_news.json을 불러오지 못했습니다.\nGitHub Actions 실행 후 새로고침 하세요.');

    DATA_DATE = TODAY_DATA.date || '';

    /* ★ 오늘 날짜 기사만 피드에 표시 */
    const allFetched = TODAY_DATA.items || [];
    ALL_ITEMS = allFetched.filter(it => {
      const d = (it.date || '').slice(0, 10);
      return d === DATA_DATE;
    });

    /* 오늘 기사가 너무 적으면(<5) collect_date 기준으로 fallback */
    if (ALL_ITEMS.length < 5) {
      ALL_ITEMS = allFetched.filter(it => (it.collect_date || '') === DATA_DATE);
    }
    /* 그래도 없으면 전체 표시 */
    if (ALL_ITEMS.length === 0) {
      ALL_ITEMS = allFetched;
    }

    KEYWORDS     = TODAY_DATA.keywords      || [];
    CAT_STATS    = TODAY_DATA.category_stats || {};
    SOURCE_STATS = TODAY_DATA.source_stats   || [];
    DAILY_SUM    = TODAY_DATA.daily_summary  || null;

    document.getElementById('updateTime').textContent =
      `마지막 업데이트: ${TODAY_DATA.generated_at || '-'} KST`;

    renderAll();
  } catch (err) {
    showSkeleton(false);
    showError(`데이터 로딩 실패: ${err.message}`);
  }
}

/* ════════════════════════════════════════════════════════
   2. 전체 렌더링
════════════════════════════════════════════════════════ */
function renderAll() {
  showSkeleton(false);
  renderSummaryCard();
  renderNewsList();
  renderSidebar();
  renderWeekly();
  renderMonthly();
}

/* ════════════════════════════════════════════════════════
   3. 요약 카드 (오늘 탭 상단)
════════════════════════════════════════════════════════ */
function renderSummaryCard() {
  const el = document.getElementById('summaryCard');
  if (!el) return;
  el.style.display = 'block';

  const d = DAILY_SUM;
  document.getElementById('summaryDate').textContent = d?.date || DATA_DATE;

  /* 통계 배지 */
  const kr = ALL_ITEMS.filter(i => i.lang === 'ko').length;
  document.getElementById('summaryStats').innerHTML =
    `<span class="sc-stat">총 <strong>${ALL_ITEMS.length}건</strong></span>` +
    `<span class="sc-stat">🇰🇷 <strong>${kr}건</strong></span>` +
    `<span class="sc-stat">🌐 <strong>${ALL_ITEMS.length - kr}건</strong></span>`;

  /* 핵심 키워드 */
  const kwEl = document.getElementById('summaryKeywords');
  kwEl.innerHTML = '';
  const kws = d?.top_keywords?.length ? d.top_keywords
    : KEYWORDS.slice(0, 7).map(k => k.keyword);
  kws.forEach(kw => {
    const s = document.createElement('span');
    s.className = 'kw-chip sz3';
    s.textContent = kw;
    kwEl.appendChild(s);
  });

  /* ★ 핵심 인사이트 5개 */
  const insEl = document.getElementById('summaryInsights');
  if (insEl) {
    insEl.innerHTML = '';
    const pts = d?.key_points || [];
    const list = pts.length ? pts : ALL_ITEMS.filter(i => i.importance?.class !== 'new').slice(0, 5)
      .map(i => cleanInsightText(i.one_line_kr || i.one_line || i.title));
    list.slice(0, 5).forEach((pt, i) => insEl.appendChild(buildInsightItem(i + 1, pt)));
  }

  /* 추천 픽 */
  const picksEl = document.getElementById('summaryPicks');
  picksEl.innerHTML = '';
  const hotPicks = d?.hot_picks?.length
    ? d.hot_picks
    : ALL_ITEMS.filter(i => i.importance?.class === 'hot').slice(0, 3)
        .map(i => ({ title: i.title, source: i.source, url: i.url }));
  const picks = hotPicks.length ? hotPicks : ALL_ITEMS.slice(0, 3)
    .map(i => ({ title: i.title, source: i.source, url: i.url }));
  picks.forEach((p, i) => picksEl.appendChild(buildPickItem(i + 1, p)));
}

function buildInsightItem(num, text) {
  const li = document.createElement('li');
  li.className = 'insight-item';
  li.innerHTML = `<span class="insight-num">${num}</span><span class="insight-text">${esc(cleanInsightText(text))}</span>`;
  return li;
}

function buildPickItem(num, p) {
  const a = document.createElement('a');
  a.className = 'pick-item';
  a.href = p.url || '#';
  a.target = '_blank';
  a.rel = 'noopener noreferrer';
  a.innerHTML = `
    <span class="pick-num">${num}</span>
    <span class="pick-title">${esc(p.title)}</span>
    <span class="pick-source">${esc(p.source)}</span>`;
  return a;
}

/* ════════════════════════════════════════════════════════
   4. 뉴스 리스트
════════════════════════════════════════════════════════ */
function getFiltered() {
  let items = [...ALL_ITEMS];
  if (curCat  !== '전체') items = items.filter(it => it.category === curCat);
  if (curLang !== 'all')  items = items.filter(it => (it.lang || 'en') === curLang);
  if (curSearch) {
    const q = curSearch.toLowerCase();
    items = items.filter(it =>
      (it.title  || '').toLowerCase().includes(q) ||
      (it.source || '').toLowerCase().includes(q)
    );
  }
  return items;
}

function renderNewsList() {
  const listEl = document.getElementById('newsList');
  listEl.innerHTML = '';
  const items = getFiltered();

  const rcEl = document.getElementById('resultCount');
  rcEl.textContent = items.length > 0 ? `${items.length}건` : '';

  if (!items.length) {
    listEl.innerHTML = `
      <div class="empty-state">
        <i class="fa-solid fa-search"></i>
        <p>해당 조건의 기사가 없습니다.</p>
      </div>`;
    return;
  }
  items.forEach(it => listEl.appendChild(buildNewsItem(it)));
}

function buildNewsItem(item) {
  const a = document.createElement('a');
  a.className = 'news-item';
  a.href   = item.url || '#';
  a.target = '_blank';
  a.rel    = 'noopener noreferrer';

  const b = BADGE[item.badge] || BADGE.news;
  const impCls = item.importance?.class === 'hot'  ? 'imp-hot'
               : item.importance?.class === 'star' ? 'imp-star' : 'imp-new';
  const impLbl = item.importance?.label || '🆕';
  const emoji  = CAT_EMOJI[item.category] || '📰';
  const isKr   = item.lang === 'ko';

  /* 한 줄 요약: 한국어→one_line, 해외→one_line_kr(번역) 우선 */
  const oneLine = isKr
    ? (item.one_line || '')
    : (item.one_line_kr || item.one_line || '');

  /* 썸네일 */
  const thumbHTML = item.thumbnail
    ? `<img src="${esc(item.thumbnail)}" alt="" loading="lazy"
          onerror="this.parentElement.textContent='${emoji}'">`
    : '';

  /* 날짜: MM-DD HH:mm 형식 */
  const dateShort = fmtDateShort(item.date);

  a.innerHTML = `
    <div class="ni-thumb">${thumbHTML || emoji}</div>
    <div class="ni-body">
      <div class="ni-meta">
        <span class="ni-badge ${b.cls}">${b.lbl}</span>
        <span class="ni-imp ${impCls}">${impLbl}</span>
        ${isKr ? '<span class="ni-flag">🇰🇷</span>' : ''}
        <span class="ni-src">${esc(item.source)}</span>
        <span class="ni-cat">${emoji} ${esc(item.category)}</span>
      </div>
      <div class="ni-title">${esc(item.title)}</div>
      ${oneLine ? `<div class="ni-line">${esc(oneLine)}</div>` : ''}
    </div>
    <div class="ni-right">
      <span class="ni-date">${dateShort}</span>
      <span class="ni-arrow">›</span>
    </div>`;
  return a;
}

/* ════════════════════════════════════════════════════════
   5. 사이드바
════════════════════════════════════════════════════════ */
function renderSidebar() {
  /* 소스 현황 */
  const srcEl = document.getElementById('sourceList');
  srcEl.innerHTML = '';
  SOURCE_STATS.slice(0, 10).forEach(s => {
    const li = document.createElement('li');
    li.className = 'src-item';
    li.innerHTML = `<span class="src-name">${esc(s.source)}</span><span class="src-count">${s.count}</span>`;
    srcEl.appendChild(li);
  });

  /* 키워드 바 */
  const kwEl = document.getElementById('keywordsWrap');
  kwEl.innerHTML = '';
  const top = KEYWORDS.slice(0, 10);
  const max = top[0]?.count || 1;
  top.forEach(kw => {
    const pct = Math.round((kw.count / max) * 100);
    const row = document.createElement('div');
    row.className = 'kw-bar-row';
    row.innerHTML = `
      <span class="kw-bar-label">${esc(kw.keyword)}</span>
      <div class="kw-bar-track"><div class="kw-bar-fill" style="width:${pct}%"></div></div>
      <span class="kw-bar-count">${kw.count}</span>`;
    kwEl.appendChild(row);
  });

  renderCatChart();
}

function renderCatChart() {
  const ctx = document.getElementById('catChart');
  if (!ctx) return;
  if (chartCat) chartCat.destroy();

  const labels = CAT_ORDER.filter(c => CAT_STATS[c]);
  const values = labels.map(c => CAT_STATS[c] || 0);
  const colors = labels.map(c => CAT_COLOR[c] || '#888');

  chartCat = new Chart(ctx, {
    type: 'doughnut',
    data: { labels, datasets: [{ data: values, backgroundColor: colors, borderWidth: 0 }] },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: {
        legend: { position: 'bottom', labels: { color: cssVar('--text2'), font: { size: 10 }, padding: 6 } }
      }
    }
  });
}

/* ════════════════════════════════════════════════════════
   6. 주간 리포트
════════════════════════════════════════════════════════ */
function renderWeekly() {
  const W = WEEKLY_DATA;

  /* 날짜 범위 */
  const rngEl = document.getElementById('weekRange');
  if (W?.daily_timeline?.length) {
    const ds = W.daily_timeline.map(d => d.date);
    rngEl.textContent = `${ds[0]} ~ ${ds[ds.length - 1]}`;
  } else {
    rngEl.textContent = '데이터 누적 중';
  }

  /* 누적 배지 */
  document.getElementById('wAccumInfo').innerHTML =
    `<span class="acc-badge">📅 ${W?.daily_timeline?.length || 1}일치</span>` +
    `<span class="acc-badge">📰 총 ${W?.total || ALL_ITEMS.length}건</span>` +
    `<span class="acc-badge">🔥 핫이슈 ${(W?.content_highlights || []).filter(i => i.importance?.class === 'hot').length}건</span>` +
    (!W ? '<span class="acc-badge warn">⚠️ 누적 데이터 없음</span>' : '');

  /* 인사이트 포인트 */
  renderInsightList('weeklyInsights', W?.period_key_points || []);

  /* 주목 뉴스 */
  renderHlList('weeklyHighlights',
    W?.content_highlights || ALL_ITEMS.filter(i => i.importance?.class !== 'new').slice(0, 8));

  /* 카테고리별 대표 */
  renderCatCards('weeklyCatCards', W?.cat_highlights || {});

  /* 트렌드 차트 */
  renderTrendChart('weeklyTrendChart', W, 'weekly');

  /* 키워드 */
  renderKwChips('weeklyKeywords', (W?.keywords || KEYWORDS).slice(0, 16));

  /* 다운로드 */
  document.getElementById('dlBtn').onclick = () => downloadReport(W || TODAY_DATA, '주간');
}

/* ════════════════════════════════════════════════════════
   7. 월간 인사이트
════════════════════════════════════════════════════════ */
function renderMonthly() {
  const M = MONTHLY_DATA;

  const rngEl = document.getElementById('monthRange');
  if (M?.daily_timeline?.length) {
    const ds = M.daily_timeline.map(d => d.date);
    rngEl.textContent = `${ds[0]} ~ ${ds[ds.length - 1]} (${ds.length}일)`;
  } else {
    const now = new Date();
    rngEl.textContent = `${now.getFullYear()}년 ${now.getMonth() + 1}월`;
  }

  const kr = M?.kr_count ?? (M?.items || ALL_ITEMS).filter(i => i.lang === 'ko').length;
  document.getElementById('mAccumInfo').innerHTML =
    `<span class="acc-badge">📅 ${M?.daily_timeline?.length || 1}일치</span>` +
    `<span class="acc-badge">📰 ${M?.total || ALL_ITEMS.length}건 수집</span>` +
    `<span class="acc-badge">🇰🇷 국내 ${kr}건</span>` +
    (!M ? '<span class="acc-badge warn">⚠️ 누적 데이터 없음</span>' : '');

  /* 월간 요약 */
  const prEl = document.getElementById('monthlySummary');
  if (prEl) {
    prEl.innerHTML = M?.period_prose
      ? `<p>${esc(M.period_prose)}</p>`
      : `<p>총 <strong>${M?.total || ALL_ITEMS.length}건</strong>의 AI 자료가 수집됐습니다.</p>`;
  }

  renderInsightList('monthlyInsights', M?.period_key_points || []);
  renderHlList('monthlyHighlights',
    M?.content_highlights || ALL_ITEMS.filter(i => i.importance?.class !== 'new').slice(0, 10));
  renderCatCards('monthlyCatCards', M?.cat_highlights || {});
  renderTrendChart('monthlyTrendChart', M, 'monthly');
  renderKwChips('monthlyKeywords', (M?.keywords || KEYWORDS).slice(0, 20));
}

/* ════════════════════════════════════════════════════════
   8. 공용 렌더 함수
════════════════════════════════════════════════════════ */
function renderInsightList(elId, points) {
  const el = document.getElementById(elId);
  if (!el) return;
  el.innerHTML = '';
  if (!points?.length) {
    el.innerHTML = '<li class="no-data">데이터 누적 중입니다.</li>';
    return;
  }
  points.forEach((pt, i) => el.appendChild(buildInsightItem(i + 1, pt)));
}

function renderHlList(elId, items) {
  const el = document.getElementById(elId);
  if (!el) return;
  el.innerHTML = '';
  if (!items?.length) { el.innerHTML = '<div class="no-data">데이터 누적 중입니다.</div>'; return; }
  items.slice(0, 10).forEach(item => {
    const a = document.createElement('a');
    a.className = 'hl-item';
    a.href   = item.url || '#';
    a.target = '_blank';
    a.rel    = 'noopener noreferrer';

    const impCls = item.importance?.class === 'hot'  ? 'imp-hot'
                 : item.importance?.class === 'star' ? 'imp-star' : 'imp-new';
    const impLbl = item.importance?.label || '🆕';
    const emoji  = CAT_EMOJI[item.category] || '📰';
    const isKr   = item.lang === 'ko';
    const oneLine = isKr ? (item.one_line || '') : (item.one_line_kr || item.one_line || '');

    a.innerHTML = `
      <div class="hl-meta">
        <span class="ni-imp ${impCls}">${impLbl}</span>
        <span class="hl-cat">${emoji} ${esc(item.category)}</span>
        <span class="hl-src">${esc(item.source)}</span>
        <span class="hl-date">${fmtDateShort(item.date)}</span>
      </div>
      <div class="hl-title">${esc(item.title)}</div>
      ${oneLine ? `<div class="hl-oneline">${esc(oneLine)}</div>` : ''}`;
    el.appendChild(a);
  });
}

function renderCatCards(elId, catHighlights) {
  const el = document.getElementById(elId);
  if (!el) return;
  el.innerHTML = '';
  const MAIN = ['콘텐츠','영상AI','이미지·디자인AI','LLM','개발AI'];
  MAIN.forEach(cat => {
    const h = catHighlights[cat];
    if (!h) return;
    const emoji = CAT_EMOJI[cat] || '📰';
    const div = document.createElement('div');
    div.className = 'cat-card';
    div.style.borderLeftColor = CAT_COLOR[cat] || '#888';
    div.innerHTML = `
      <div class="cat-card-header">${emoji} ${esc(cat)}</div>
      <a href="${esc(h.url || '#')}" target="_blank" rel="noopener">
        <div class="cat-card-title">${esc(h.title)}</div>
        ${h.one_line ? `<div class="cat-card-line">${esc(h.one_line)}</div>` : ''}
        <div class="cat-card-meta">${esc(h.source)} · ${fmtDateShort(h.date)}</div>
      </a>`;
    el.appendChild(div);
  });
  if (!el.children.length) el.innerHTML = '<div class="no-data">데이터 누적 중입니다.</div>';
}

function renderKwChips(elId, keywords) {
  const el = document.getElementById(elId);
  if (!el) return;
  el.innerHTML = '';
  const max = keywords[0]?.count || 1;
  keywords.forEach(kw => {
    const r = kw.count / max;
    const sz = r > .8 ? 5 : r > .6 ? 4 : r > .4 ? 3 : r > .2 ? 2 : 1;
    const chip = document.createElement('span');
    chip.className   = `kw-chip sz${sz}`;
    chip.textContent = `${kw.keyword} ${kw.count}`;
    el.appendChild(chip);
  });
}

function renderTrendChart(elId, periodData, type) {
  const ctx = document.getElementById(elId);
  if (!ctx) return;
  if (type === 'weekly'  && chartWeekly)  { chartWeekly.destroy();  chartWeekly  = null; }
  if (type === 'monthly' && chartMonthly) { chartMonthly.destroy(); chartMonthly = null; }

  const tl = periodData?.daily_timeline || [];
  const cd = periodData?.cat_daily      || {};
  if (!tl.length) {
    ctx.parentElement.innerHTML = '<div class="no-data">📅 데이터 누적 중 (2일차부터 표시)</div>';
    return;
  }

  const labels = tl.map(d => d.date.slice(5));
  const dates  = tl.map(d => d.date);
  const datasets = CAT_FILTER
    .filter(cat => dates.some(d => cd[d]?.[cat]))
    .map(cat => ({
      label: cat,
      data: dates.map(d => cd[d]?.[cat] || 0),
      borderColor: CAT_COLOR[cat],
      backgroundColor: (CAT_COLOR[cat] || '#888') + '22',
      borderWidth: 2.5, tension: 0.35, fill: false, pointRadius: 4,
    }));

  const inst = new Chart(ctx, {
    type: 'line',
    data: { labels, datasets },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { position:'bottom', labels:{ color:cssVar('--text2'), font:{size:10} } } },
      scales: {
        x: { ticks:{ color:cssVar('--text2') }, grid:{ color:'rgba(128,128,128,0.1)' } },
        y: { ticks:{ color:cssVar('--text2') }, grid:{ color:'rgba(128,128,128,0.1)' }, beginAtZero:true }
      }
    }
  });
  if (type === 'weekly')  chartWeekly  = inst;
  if (type === 'monthly') chartMonthly = inst;
}

/* ════════════════════════════════════════════════════════
   9. 리포트 다운로드
════════════════════════════════════════════════════════ */
function downloadReport(data, label) {
  const items = data?.items || ALL_ITEMS;
  const kws   = data?.keywords || KEYWORDS;
  const hl    = data?.content_highlights || items.filter(i => i.importance?.class !== 'new').slice(0, 10);
  const kr    = data?.kr_count ?? items.filter(i => i.lang === 'ko').length;

  const lines = [
    `AI 트렌드 — ${label} 리포트`,
    `생성: ${new Date().toLocaleString('ko-KR')}`,
    `총 수집: ${items.length}건 (국내 ${kr}건 / 해외 ${items.length - kr}건)`,
    '='.repeat(54), '',
    '■ 핵심 요약',
    data?.period_prose || '-', '',
    `■ ${label} 핵심 뉴스 TOP 10`,
    ...hl.slice(0, 10).map((it, i) => {
      const s = it.lang === 'ko' ? (it.one_line || '') : (it.one_line_kr || it.one_line || '');
      return `  ${i + 1}. [${it.category}] ${it.title}\n     ${s}\n     ${it.url}`;
    }), '',
    '■ 핵심 키워드 TOP 10',
    ...kws.slice(0, 10).map((k, i) => `  ${i + 1}. ${k.keyword} (${k.count}회)`),
    '', '='.repeat(54), 'AI 트렌드 대시보드',
  ];

  const blob = new Blob([lines.join('\n')], { type: 'text/plain;charset=utf-8' });
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement('a');
  const now  = new Date();
  a.href     = url;
  a.download = `ai_trend_${label}_${now.getFullYear()}${p2(now.getMonth()+1)}${p2(now.getDate())}.txt`;
  a.click();
  URL.revokeObjectURL(url);
}

/* ════════════════════════════════════════════════════════
   10. 이벤트 바인딩
════════════════════════════════════════════════════════ */
function bindEvents() {
  /* 탭 전환 */
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.tab-page').forEach(p => p.classList.remove('active'));
      btn.classList.add('active');
      document.getElementById(`tab-${btn.dataset.tab}`)?.classList.add('active');
      setTimeout(() => [chartCat, chartWeekly, chartMonthly].forEach(c => c?.resize()), 60);
    });
  });

  /* 카테고리 필터 */
  buildFilterBtns();

  /* 언어 필터 */
  document.querySelectorAll('.lang-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.lang-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      curLang = btn.dataset.lang;
      renderNewsList();
    });
  });

  /* 검색 */
  document.getElementById('searchInput')?.addEventListener('input', e => {
    curSearch = e.target.value.trim();
    renderNewsList();
  });

  /* 테마 */
  const saved = localStorage.getItem('ai-trend-theme') || 'light';
  applyTheme(saved);
  document.getElementById('themeBtn')?.addEventListener('click', () => {
    const next = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
    applyTheme(next);
    localStorage.setItem('ai-trend-theme', next);
  });
}

function buildFilterBtns() {
  const el = document.getElementById('filterCats');
  if (!el) return;
  el.innerHTML = '';
  ['전체', ...CAT_FILTER].forEach(cat => {
    const btn = document.createElement('button');
    btn.className = `filter-btn${cat === '전체' ? ' active' : ''}`;
    btn.dataset.cat = cat;
    btn.textContent = cat === '전체' ? '전체' : `${CAT_EMOJI[cat] || ''} ${cat}`;
    btn.addEventListener('click', () => {
      document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      curCat = cat;
      renderNewsList();
    });
    el.appendChild(btn);
  });
}

function applyTheme(theme) {
  document.documentElement.dataset.theme = theme;
  const icon = document.querySelector('#themeBtn i');
  if (icon) icon.className = theme === 'dark' ? 'fa-solid fa-sun' : 'fa-solid fa-moon';
  setTimeout(() => [chartCat, chartWeekly, chartMonthly].forEach(c => c?.update()), 80);
}

/* ════════════════════════════════════════════════════════
   11. 유틸
════════════════════════════════════════════════════════ */
function esc(str) {
  return String(str || '')
    .replace(/&/g,'&amp;').replace(/</g,'&lt;')
    .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function fmtDateShort(dateStr) {
  if (!dateStr) return '';
  const m = dateStr.match(/\d{4}-(\d{2}-\d{2})(?: (\d{2}:\d{2}))?/);
  if (!m) return dateStr;
  return m[2] ? `${m[1]} ${m[2]}` : m[1];
}

/** 인사이트 텍스트 정제: 출처 태그 제거, 말줄임 처리 */
function cleanInsightText(text) {
  if (!text) return '';
  // [디지털투데이 XX기자] 형태 제거
  text = text.replace(/^\[[^\]]{1,30}\]\s*/g, '');
  // 말줄임표로 끝나는 경우 → 마지막 완결 문장 찾기
  if (text.endsWith('…') || text.endsWith('...')) {
    for (const sep of ['다.', '했다.', '됩니다.', '했습니다.', '이다.']) {
      const idx = text.lastIndexOf(sep);
      if (idx > 10) return text.slice(0, idx + sep.length);
    }
    text = text.replace(/[…\.]+$/, '') + '.';
  }
  return text.trim();
}

function cssVar(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || '#888';
}
function p2(n) { return String(n).padStart(2, '0'); }

function showSkeleton(show) {
  const el = document.getElementById('loadingSkeleton');
  if (el) el.style.display = show ? 'flex' : 'none';
}
function showError(msg) {
  const box = document.getElementById('errorBox');
  const pre = document.getElementById('errorMsg');
  if (box && pre) { pre.textContent = msg; box.style.display = 'flex'; }
}
function hideError() {
  const box = document.getElementById('errorBox');
  if (box) box.style.display = 'none';
}

/* ════════════════════════════════════════════════════════
   초기화
════════════════════════════════════════════════════════ */
document.addEventListener('DOMContentLoaded', () => {
  bindEvents();
  loadData();
});

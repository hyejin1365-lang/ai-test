'use strict';

/* ═══════════════════════════════════════════════════════════
   AI 트렌드 대시보드 — app.js (B방식: 날짜별 누적 데이터)
   ─ 일간: data/ai_news.json
   ─ 주간: data/weekly.json  (최근 7일 집계)
   ─ 월간: data/monthly.json (최근 30일 집계)
═══════════════════════════════════════════════════════════ */

// ── 전역 상태 ─────────────────────────────────────────────
let TODAY_DATA   = null;   // ai_news.json
let WEEKLY_DATA  = null;   // weekly.json
let MONTHLY_DATA = null;   // monthly.json

let ALL_ITEMS    = [];
let KEYWORDS     = [];
let CAT_STATS    = {};
let SOURCE_STATS = [];
let DAILY_SUMMARY = null;

let currentCat    = '전체';
let currentLang   = 'all';
let currentSearch = '';

let catChartInst, weeklyTimelineInst, weeklyCatInst,
    monthlyLineInst, monthlyBarInst;

const CAT_ORDER = ['콘텐츠','영상AI','디자인AI','논문','개발AI','비즈니스'];
const CAT_COLORS = {
  '콘텐츠':'#e53e3e','영상AI':'#f97316','디자인AI':'#a855f7',
  '논문':'#7c3aed','개발AI':'#2563eb','비즈니스':'#16a34a'
};
const BADGE_CLASS = {
  paper:'badge-paper', official:'badge-official',
  news:'badge-news',   tool:'badge-tool', 'kr-news':'badge-kr-news',
};
const BADGE_LABEL = {
  paper:'논문', official:'공식블로그', news:'뉴스', tool:'도구', 'kr-news':'국내',
};
const CAT_EMOJI = {
  '콘텐츠':'📰','영상AI':'🎬','디자인AI':'🎨',
  '논문':'📄','개발AI':'💻','비즈니스':'📊',
};

// ═══ 1. 데이터 로딩 ═══════════════════════════════════════
async function loadData() {
  showSkeleton(true);
  hideError();
  try {
    const ts = `?_=${Date.now()}`;

    // 병렬 로딩 (weekly/monthly 없어도 graceful degradation)
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
      `마지막 업데이트: ${TODAY_DATA.generated_at || '-'}`;

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
  renderCards();
  renderSidebar();
  renderDailySummary();
  renderWeekly();
  renderMonthly();
}

// ═══ 3. 뉴스 카드 ════════════════════════════════════════
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

function renderCards() {
  const grid  = document.getElementById('cardsGrid');
  grid.innerHTML = '';
  const items = getFilteredItems();

  document.getElementById('resultCount').textContent =
    items.length > 0 ? `${items.length}건` : '';

  if (!items.length) {
    grid.innerHTML = `
      <div class="error-box" style="grid-column:1/-1">
        <i class="fa-solid fa-search"></i>
        <p>검색 결과가 없습니다.</p>
      </div>`;
    return;
  }
  items.forEach(item => grid.appendChild(buildCard(item)));
}

function buildCard(item) {
  const a = document.createElement('a');
  a.className = 'news-card';
  a.href      = item.url || '#';
  a.target    = '_blank';
  a.rel       = 'noopener noreferrer';

  const bCls   = BADGE_CLASS[item.badge] || 'badge-news';
  const bLbl   = BADGE_LABEL[item.badge] || item.badge;
  const impCls = item.importance?.class === 'hot'  ? 'imp-hot'
               : item.importance?.class === 'star' ? 'imp-star' : 'imp-new';
  const impLbl = item.importance?.label || '🆕 신규';
  const emoji  = CAT_EMOJI[item.category] || '📰';
  const isKr   = item.lang === 'ko';

  const thumbHTML = item.thumbnail
    ? `<img class="card-thumb" src="${esc(item.thumbnail)}" alt="" loading="lazy"
           onerror="this.style.display='none';this.nextElementSibling.style.display='flex'">`
    : '';
  const phStyle = item.thumbnail ? 'style="display:none"' : '';

  a.innerHTML = `
    ${thumbHTML}
    <div class="card-thumb-placeholder" ${phStyle}>${emoji}</div>
    <div class="card-meta">
      <span class="badge ${bCls}">${bLbl}</span>
      <span class="importance-tag ${impCls}">${impLbl}</span>
      ${isKr ? '<span class="lang-tag-ko">🇰🇷 국내</span>' : ''}
      <span class="card-source">${esc(item.source)}</span>
    </div>
    <div class="card-title">${esc(item.title)}</div>
    <div class="card-summary">${esc(item.summary)}</div>
    <div class="card-footer">
      <span class="card-date">${item.date || ''}</span>
      <span class="card-link">읽기 →</span>
    </div>`;
  return a;
}

// ═══ 4. 사이드바 ══════════════════════════════════════════
function renderSidebar() {
  // 소스 TOP 10
  const ul = document.getElementById('sourceList');
  ul.innerHTML = '';
  SOURCE_STATS.slice(0, 10).forEach(s => {
    const li = document.createElement('li');
    li.className = 'source-item';
    li.innerHTML = `<span class="source-name">${esc(s.source)}</span>
                    <span class="source-count">${s.count}</span>`;
    ul.appendChild(li);
  });

  // 키워드 바
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
        legend: { position:'bottom', labels:{ color: getColor('--text2'), font:{ size:10 }, padding:8 } }
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

  document.getElementById('summaryOneLine').innerHTML =
    d?.one_line
      ? esc(d.one_line)
      : `오늘 총 <strong>${ALL_ITEMS.length}건</strong>의 AI 자료가 수집됐습니다.`;

  const krCount = ALL_ITEMS.filter(i => i.lang === 'ko').length;
  document.getElementById('summaryStats').innerHTML = `
    <div class="stat-badge">총 <strong>${ALL_ITEMS.length}건</strong></div>
    <div class="stat-badge">🇰🇷 국내 <strong>${krCount}건</strong></div>
    <div class="stat-badge">🌐 해외 <strong>${ALL_ITEMS.length - krCount}건</strong></div>
    <div class="stat-badge">소스 <strong>${SOURCE_STATS.length}개</strong></div>`;

  const kwEl = document.getElementById('summaryKeywords');
  kwEl.innerHTML = '';
  (d?.top_keywords?.length ? d.top_keywords : KEYWORDS.slice(0,7).map(k=>k.keyword))
    .forEach(kw => {
      const chip = document.createElement('span');
      chip.className = 'sum-kw';
      chip.textContent = kw;
      kwEl.appendChild(chip);
    });

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

// ═══ 6. 주간 리포트 ══════════════════════════════════════
function renderWeekly() {
  const W = WEEKLY_DATA;

  // 헤더 날짜 범위
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

  // 통계 숫자
  const wItems = W?.items || ALL_ITEMS;
  const wKw    = W?.keywords || KEYWORDS;
  const wSrc   = W?.source_stats || SOURCE_STATS;
  const wCat   = W?.category_stats || CAT_STATS;
  const krItems = wItems.filter(i => i.lang === 'ko');
  const papers  = wItems.filter(i => i.badge === 'paper');
  const tools   = wItems.filter(i => i.badge === 'tool' || i.badge === 'official');

  document.getElementById('wTotalItems').textContent = W?.total || wItems.length;
  document.getElementById('wKrItems').textContent    = W?.kr_count ?? krItems.length;
  document.getElementById('wPapers').textContent     = papers.length;
  document.getElementById('wTools').textContent      = tools.length;

  // 누적 현황 뱃지
  const wDays = W?.days || 1;
  const wDayCount = W?.daily_timeline?.length || 1;
  document.getElementById('wAccumInfo').innerHTML =
    `<span class="acc-badge">📅 누적 ${wDayCount}일치 데이터</span>` +
    `<span class="acc-badge">📰 총 ${W?.total || wItems.length}건</span>` +
    (W ? `` : `<span class="acc-badge warn">⚠️ 누적 데이터 없음 (오늘 데이터만 표시)</span>`);

  // 차트 1: 일별 수집량 타임라인
  renderWeeklyTimeline(W?.daily_timeline || []);

  // 차트 2: 카테고리별 분포 (주간)
  renderWeeklyCatChart(wCat);

  // 키워드 히트맵
  renderKeywordHeatmap('weeklyKeywords', wKw.slice(0, 14));

  // TOP 리스트
  renderTopList('topPapers',  papers.slice(0, 5));
  renderTopList('topKrNews',  krItems.slice(0, 5));

  document.getElementById('dlBtn').onclick = () => downloadReport(W || TODAY_DATA);
}

function renderWeeklyTimeline(timeline) {
  const ctx = document.getElementById('weeklyTimelineChart');
  if (!ctx) return;
  if (weeklyTimelineInst) weeklyTimelineInst.destroy();

  if (!timeline.length) {
    ctx.parentElement.innerHTML = '<p class="no-data-msg">📅 데이터 누적 중 (2일차부터 타임라인 표시)</p>';
    return;
  }

  weeklyTimelineInst = new Chart(ctx, {
    type: 'line',
    data: {
      labels: timeline.map(d => d.date.slice(5)),  // MM-DD
      datasets: [{
        label: '일별 수집 건수',
        data: timeline.map(d => d.count),
        borderColor: '#5b5ef4',
        backgroundColor: 'rgba(91,94,244,0.12)',
        borderWidth: 2.5,
        pointBackgroundColor: '#5b5ef4',
        pointRadius: 5,
        tension: 0.35,
        fill: true,
      }]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks:{ color: getColor('--text2') }, grid:{ color:'rgba(128,128,128,0.1)' } },
        y: { ticks:{ color: getColor('--text2') }, grid:{ color:'rgba(128,128,128,0.1)' }, beginAtZero:true }
      }
    }
  });
}

function renderWeeklyCatChart(catStats) {
  const ctx = document.getElementById('weeklyBarChart');
  if (!ctx) return;
  if (weeklyCatInst) weeklyCatInst.destroy();

  const labels = CAT_ORDER.filter(c => catStats[c]);
  const values = labels.map(c => catStats[c] || 0);
  const colors = labels.map(c => CAT_COLORS[c] || '#888');

  weeklyCatInst = new Chart(ctx, {
    type: 'bar',
    data: {
      labels,
      datasets: [{ label:'기사 수', data:values, backgroundColor:colors, borderRadius:5, borderSkipped:false }]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend:{ display:false } },
      scales: {
        x: { ticks:{ color:getColor('--text2') }, grid:{ color:'rgba(128,128,128,0.1)' } },
        y: { ticks:{ color:getColor('--text2') }, grid:{ color:'rgba(128,128,128,0.1)' }, beginAtZero:true }
      }
    }
  });
}

// ═══ 7. 월간 인사이트 ════════════════════════════════════
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
  const mSrc   = M?.source_stats || SOURCE_STATS;
  const mCat   = M?.category_stats || CAT_STATS;
  const krCount = M?.kr_count ?? mItems.filter(i => i.lang === 'ko').length;
  const sortedCats = Object.entries(mCat).sort((a, b) => b[1]-a[1]);
  const topCat     = sortedCats[0]?.[0] || '-';
  const topKws     = mKw.slice(0, 5).map(k => k.keyword).join(', ');

  document.getElementById('monthlySummary').innerHTML =
    `총 <strong>${M?.total || mItems.length}건</strong>의 AI 자료가 수집됐습니다 ` +
    `(국내 <strong>${krCount}건</strong> / 해외 <strong>${(M?.en_count ?? (mItems.length - krCount))}건</strong>).<br>` +
    `가장 활발한 분야: <strong>${topCat}</strong> &nbsp;|&nbsp; ` +
    `핵심 키워드: <strong>${topKws}</strong><br>` +
    `총 <strong>${mSrc.length}개</strong> 소스에서 수집된 누적 데이터` +
    (M ? ` (${M.days}일치)` : ' (오늘 데이터만)') + `.`;

  // 누적 현황
  document.getElementById('mAccumInfo').innerHTML =
    `<span class="acc-badge">📅 누적 ${M?.daily_timeline?.length || 1}일치</span>` +
    `<span class="acc-badge">📰 총 ${M?.total || mItems.length}건</span>` +
    (M ? `` : `<span class="acc-badge warn">⚠️ 누적 데이터 없음 (오늘 데이터만 표시)</span>`);

  // 차트 1: 날짜별 누적 트렌드 (카테고리별 스택)
  renderMonthlyCatTrend(M?.cat_daily || {}, M?.daily_timeline || []);

  // 차트 2: 소스별 총 수집량
  renderMonthlySourceChart(mSrc);

  renderKeywordHeatmap('monthlyKeywords', mKw);
  renderTopList('monthlyTopItems', mItems.slice(0, 10));
}

function renderMonthlyCatTrend(catDaily, timeline) {
  const ctx = document.getElementById('monthlyLineChart');
  if (!ctx) return;
  if (monthlyLineInst) monthlyLineInst.destroy();

  if (!timeline.length) {
    ctx.parentElement.innerHTML = '<p class="no-data-msg">📅 데이터 누적 중 (2일차부터 차트 표시)</p>';
    return;
  }

  const dates = timeline.map(d => d.date.slice(5));
  const datesFull = timeline.map(d => d.date);

  const datasets = CAT_ORDER
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

  monthlyLineInst = new Chart(ctx, {
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

function renderMonthlySourceChart(srcStats) {
  const ctx = document.getElementById('monthlyBarChart');
  if (!ctx) return;
  if (monthlyBarInst) monthlyBarInst.destroy();

  const top12  = srcStats.slice(0, 12);
  const labels = top12.map(s => s.source);
  const values = top12.map(s => s.count);

  monthlyBarInst = new Chart(ctx, {
    type: 'bar',
    data: {
      labels,
      datasets: [{
        label: '수집 건수', data: values,
        backgroundColor: 'rgba(91,94,244,0.55)',
        borderColor: 'rgba(91,94,244,0.85)',
        borderWidth:1, borderRadius:5, borderSkipped:false,
      }]
    },
    options: {
      indexAxis: 'y',
      responsive: true, maintainAspectRatio: false,
      plugins: { legend:{ display:false } },
      scales: {
        x: { ticks:{ color:getColor('--text2') }, grid:{ color:'rgba(128,128,128,0.1)' }, beginAtZero:true },
        y: { ticks:{ color:getColor('--text2'), font:{size:11} }, grid:{ display:false } }
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

function renderTopList(elId, items) {
  const el = document.getElementById(elId);
  if (!el) return;
  el.innerHTML = '';
  items.forEach((item, idx) => {
    const div = document.createElement('div');
    div.className = 'top-item';
    div.innerHTML = `
      <div class="top-rank">#${idx+1}</div>
      <div>
        <div class="top-title">${esc(item.title)}</div>
        <div class="top-sub">${esc(item.source)} · ${item.date || ''}</div>
        <a class="top-link" href="${esc(item.url||'#')}" target="_blank" rel="noopener">원문 보기 →</a>
      </div>`;
    el.appendChild(div);
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

  const lines = [
    `AI 트렌드 — ${period} 리포트`,
    `생성: ${now.toLocaleString('ko-KR')}`,
    `총 수집: ${items.length}건 (국내 ${krCount}건 / 해외 ${items.length-krCount}건)`,
    `${'='.repeat(56)}`,
    '',
    '■ 카테고리별 분포',
    ...CAT_ORDER.filter(c=>catSt[c]).map(c=>`  ${c}: ${catSt[c]}건`),
    '',
    '■ 핵심 키워드 TOP 10',
    ...kws.slice(0,10).map((k,i)=>`  ${i+1}. ${k.keyword} (${k.count}회)`),
    '',
    '■ 소스 현황 TOP 10',
    ...srcSt.slice(0,10).map(s=>`  ${s.source}: ${s.count}건`),
    '',
    '■ 주목할 논문 TOP 5',
    ...items.filter(i=>i.badge==='paper').slice(0,5)
       .map((it,i)=>`  ${i+1}. ${it.title}\n     ${it.url}`),
    '',
    '■ 국내 추천 기사 TOP 5',
    ...items.filter(i=>i.lang==='ko').slice(0,5)
       .map((it,i)=>`  ${i+1}. ${it.title}\n     ${it.url}`),
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
        [catChartInst, weeklyTimelineInst, weeklyCatInst, monthlyLineInst, monthlyBarInst]
          .forEach(c => c?.resize());
      }, 50);
    });
  });

  // 카테고리 필터
  document.querySelectorAll('.filter-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      currentCat = btn.dataset.cat;
      renderCards();
    });
  });

  // 국내/해외 토글
  document.querySelectorAll('.lang-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.lang-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      currentLang = btn.dataset.lang;
      renderCards();
    });
  });

  // 검색
  document.getElementById('searchInput').addEventListener('input', e => {
    currentSearch = e.target.value.trim();
    renderCards();
  });

  // 테마 (기본: 라이트)
  const saved = localStorage.getItem('ai-trend-theme') || 'light';
  applyTheme(saved);
  document.getElementById('themeBtn').addEventListener('click', () => {
    const next = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
    applyTheme(next);
    localStorage.setItem('ai-trend-theme', next);
  });
}

function applyTheme(theme) {
  document.documentElement.dataset.theme = theme;
  const icon = document.querySelector('#themeBtn i');
  if (icon) icon.className = theme === 'dark' ? 'fa-solid fa-sun' : 'fa-solid fa-moon';
  setTimeout(() => {
    [catChartInst, weeklyTimelineInst, weeklyCatInst, monthlyLineInst, monthlyBarInst]
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
  if (el) el.style.display = show ? 'contents' : 'none';
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

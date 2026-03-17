/* ═══════════════════════════════════════════════════
   AI PULSE — app.js
   실제 data/ai_news.json 로딩 & 렌더링
═══════════════════════════════════════════════════ */

'use strict';

// ── 전역 상태 ──────────────────────────────────────────
let ALL_ITEMS   = [];
let KEYWORDS    = [];
let CAT_STATS   = {};
let SOURCE_STATS = [];
let currentCat  = '전체';
let currentSearch = '';
let catChartInst, weeklyBarInst, monthlyBarInst;

// ── 카테고리 아이콘 맵 ────────────────────────────────
const CAT_ICON = {
  '논문':   { icon: 'fa-scroll',       color: '#c084fc' },
  '개발AI': { icon: 'fa-code',          color: '#60a5fa' },
  '영상AI': { icon: 'fa-film',          color: '#f87171' },
  '디자인AI':{ icon: 'fa-palette',      color: '#fb923c' },
  '비즈니스':{ icon: 'fa-briefcase',    color: '#4ade80' },
};

// ── 배지 유형 맵 ─────────────────────────────────────
const BADGE_CLASS = {
  paper:    'badge-paper',
  official: 'badge-official',
  news:     'badge-news',
  tool:     'badge-tool',
};
const BADGE_LABEL = {
  paper:    '논문',
  official: '공식블로그',
  news:     '뉴스',
  tool:     '도구',
};

// ── 썸네일 Placeholder (카테고리별 이모지) ───────────
const CAT_EMOJI = {
  '논문':    '📄',
  '개발AI':  '💻',
  '영상AI':  '🎬',
  '디자인AI':'🎨',
  '비즈니스':'📊',
};

// ═══════════════════════════════════════════════════
// 1. 데이터 로딩
// ═══════════════════════════════════════════════════
async function loadData() {
  showSkeleton(true);
  hideError();

  try {
    // 캐시 방지용 타임스탬프
    const ts  = Date.now();
    const res = await fetch(`data/ai_news.json?_=${ts}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    ALL_ITEMS    = data.items    || [];
    KEYWORDS     = data.keywords || [];
    CAT_STATS    = data.category_stats || {};
    SOURCE_STATS = data.source_stats   || [];

    // 생성 시각 표시
    document.getElementById('updateTime').textContent =
      `마지막 업데이트: ${data.generated_at || '-'}`;

    renderAll();
  } catch (err) {
    console.error('[AI PULSE] 데이터 로딩 실패:', err);
    showSkeleton(false);
    showError(`데이터 로딩 실패: ${err.message}\n\nGitHub Actions가 아직 실행되지 않았거나 data/ai_news.json 파일이 없습니다.`);
  }
}

// ═══════════════════════════════════════════════════
// 2. 전체 렌더링
// ═══════════════════════════════════════════════════
function renderAll() {
  showSkeleton(false);
  renderCards();
  renderSidebar();
  renderWeekly();
  renderMonthly();
}

// ═══════════════════════════════════════════════════
// 3. 카드 렌더링 (Daily Feed)
// ═══════════════════════════════════════════════════
function renderCards() {
  const grid = document.getElementById('cardsGrid');
  grid.innerHTML = '';

  let items = ALL_ITEMS;

  // 카테고리 필터
  if (currentCat !== '전체') {
    items = items.filter(it => it.category === currentCat);
  }

  // 검색 필터
  if (currentSearch) {
    const q = currentSearch.toLowerCase();
    items = items.filter(it =>
      (it.title   || '').toLowerCase().includes(q) ||
      (it.summary || '').toLowerCase().includes(q) ||
      (it.source  || '').toLowerCase().includes(q)
    );
  }

  // 결과 수 표시
  document.getElementById('resultCount').textContent =
    items.length > 0 ? `${items.length}건` : '';

  if (items.length === 0) {
    grid.innerHTML = `
      <div class="error-box" style="grid-column:1/-1">
        <i class="fa-solid fa-search"></i>
        <p>검색 결과가 없습니다.</p>
      </div>`;
    return;
  }

  items.forEach(item => {
    const card = buildCard(item);
    grid.appendChild(card);
  });
}

function buildCard(item) {
  const a = document.createElement('a');
  a.className  = 'news-card';
  a.href       = item.url || '#';
  a.target     = '_blank';
  a.rel        = 'noopener noreferrer';

  const badgeClass = BADGE_CLASS[item.badge] || 'badge-news';
  const badgeLabel = BADGE_LABEL[item.badge] || item.badge;
  const impClass   = item.importance?.class === 'hot'  ? 'imp-hot'
                   : item.importance?.class === 'star' ? 'imp-star'
                   : 'imp-new';
  const impLabel   = item.importance?.label || '🆕 신규';
  const emoji      = CAT_EMOJI[item.category] || '📰';

  const thumbHTML = item.thumbnail
    ? `<img class="card-thumb" src="${escHtml(item.thumbnail)}"
            alt="" loading="lazy"
            onerror="this.style.display='none';this.nextElementSibling.style.display='flex'">`
    : '';
  const placeholderStyle = item.thumbnail ? 'style="display:none"' : '';

  a.innerHTML = `
    ${thumbHTML}
    <div class="card-thumb-placeholder" ${placeholderStyle}>${emoji}</div>
    <div class="card-meta">
      <span class="badge ${badgeClass}">${badgeLabel}</span>
      <span class="importance-tag ${impClass}">${impLabel}</span>
      <span class="card-source">${escHtml(item.source)}</span>
    </div>
    <div class="card-title">${escHtml(item.title)}</div>
    <div class="card-summary">${escHtml(item.summary)}</div>
    <div class="card-footer">
      <span class="card-date"><i class="fa-regular fa-clock"></i> ${item.date || ''}</span>
      <span class="card-link">읽기 <i class="fa-solid fa-arrow-up-right-from-square"></i></span>
    </div>`;

  return a;
}

// ═══════════════════════════════════════════════════
// 4. 사이드바 렌더링
// ═══════════════════════════════════════════════════
function renderSidebar() {
  renderSourceList();
  renderKeywordBars();
  renderCatChart();
}

function renderSourceList() {
  const ul = document.getElementById('sourceList');
  ul.innerHTML = '';
  const top = SOURCE_STATS.slice(0, 10);
  top.forEach(s => {
    const li = document.createElement('li');
    li.className = 'source-item';
    li.innerHTML = `
      <span class="source-name">${escHtml(s.source)}</span>
      <span class="source-count">${s.count}</span>`;
    ul.appendChild(li);
  });
}

function renderKeywordBars() {
  const wrap = document.getElementById('keywordsWrap');
  wrap.innerHTML = '';
  const top = KEYWORDS.slice(0, 10);
  const max = top[0]?.count || 1;

  top.forEach(kw => {
    const pct = Math.round((kw.count / max) * 100);
    const row = document.createElement('div');
    row.className = 'kw-row';
    row.innerHTML = `
      <span class="kw-label">${escHtml(kw.keyword)}</span>
      <div class="kw-bar-wrap"><div class="kw-bar" style="width:${pct}%"></div></div>
      <span class="kw-count">${kw.count}</span>`;
    wrap.appendChild(row);
  });
}

function renderCatChart() {
  const ctx = document.getElementById('catChart');
  if (!ctx) return;
  if (catChartInst) catChartInst.destroy();

  const labels = Object.keys(CAT_STATS);
  const values = Object.values(CAT_STATS);
  const colors = ['#c084fc','#60a5fa','#f87171','#fb923c','#4ade80','#fbbf24'];

  catChartInst = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels,
      datasets: [{ data: values, backgroundColor: colors, borderWidth: 0 }]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: {
        legend: {
          position: 'bottom',
          labels: { color: getComputedStyle(document.documentElement).getPropertyValue('--text2').trim(), font: { size: 11 }, padding: 10 }
        }
      }
    }
  });
}

// ═══════════════════════════════════════════════════
// 5. 주간 리포트 렌더링
// ═══════════════════════════════════════════════════
function renderWeekly() {
  const now  = new Date();
  const mon  = new Date(now); mon.setDate(now.getDate() - now.getDay() + 1);
  const sun  = new Date(mon); sun.setDate(mon.getDate() + 6);
  document.getElementById('weekRange').textContent =
    `${fmtDate(mon)} ~ ${fmtDate(sun)}`;

  // 통계
  const papers = ALL_ITEMS.filter(i => i.badge === 'paper').length;
  const tools  = ALL_ITEMS.filter(i => i.badge === 'tool').length;
  const news   = ALL_ITEMS.filter(i => i.badge === 'news' || i.badge === 'official').length;
  document.getElementById('wTotalItems').textContent = ALL_ITEMS.length;
  document.getElementById('wPapers').textContent     = papers;
  document.getElementById('wTools').textContent      = tools;
  document.getElementById('wNews').textContent       = news;

  // 분야별 차트
  renderWeeklyBarChart();

  // 키워드 히트맵
  renderKeywordHeatmap('weeklyKeywords', KEYWORDS.slice(0, 16));

  // TOP 5 논문 / 도구
  const topPapers = ALL_ITEMS.filter(i => i.badge === 'paper').slice(0, 5);
  const topTools  = ALL_ITEMS.filter(i => i.badge === 'tool' || i.badge === 'official').slice(0, 5);
  renderTopList('topPapers', topPapers);
  renderTopList('topTools',  topTools);

  // 다운로드 버튼
  document.getElementById('dlBtn').onclick = () => downloadReport();
}

function renderWeeklyBarChart() {
  const ctx = document.getElementById('weeklyBarChart');
  if (!ctx) return;
  if (weeklyBarInst) weeklyBarInst.destroy();

  const labels = Object.keys(CAT_STATS);
  const values = Object.values(CAT_STATS);

  weeklyBarInst = new Chart(ctx, {
    type: 'bar',
    data: {
      labels,
      datasets: [{
        label: '기사 수',
        data: values,
        backgroundColor: ['#c084fc','#60a5fa','#f87171','#fb923c','#4ade80','#fbbf24'],
        borderRadius: 6,
        borderSkipped: false,
      }]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { color: '#9aa3b8', font: { size: 12 } }, grid: { color: 'rgba(255,255,255,0.05)' } },
        y: { ticks: { color: '#9aa3b8', font: { size: 12 } }, grid: { color: 'rgba(255,255,255,0.05)' }, beginAtZero: true }
      }
    }
  });
}

function renderKeywordHeatmap(elId, keywords) {
  const wrap = document.getElementById(elId);
  if (!wrap) return;
  wrap.innerHTML = '';
  const max = keywords[0]?.count || 1;

  keywords.forEach(kw => {
    const ratio = kw.count / max;
    const size  = ratio > 0.8 ? 5 : ratio > 0.6 ? 4 : ratio > 0.4 ? 3 : ratio > 0.2 ? 2 : 1;
    const chip  = document.createElement('span');
    chip.className = `kw-chip kw-size-${size}`;
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
      <div class="top-rank">#${idx + 1}</div>
      <div>
        <div class="top-title">${escHtml(item.title)}</div>
        <div class="top-sub">${escHtml(item.source)} · ${item.date || ''}</div>
        <a class="top-link" href="${escHtml(item.url || '#')}" target="_blank" rel="noopener">
          원문 보기 <i class="fa-solid fa-arrow-up-right-from-square"></i>
        </a>
      </div>`;
    el.appendChild(div);
  });
}

// ═══════════════════════════════════════════════════
// 6. 월간 인사이트 렌더링
// ═══════════════════════════════════════════════════
function renderMonthly() {
  const now = new Date();
  document.getElementById('monthRange').textContent =
    `${now.getFullYear()}년 ${now.getMonth() + 1}월 기준`;

  // 요약 텍스트 (수집 통계 기반 자동 생성)
  const sortedCats  = Object.entries(CAT_STATS).sort((a,b) => b[1]-a[1]);
  const topCat      = sortedCats[0]?.[0] || '-';
  const topKeywords = KEYWORDS.slice(0, 5).map(k => k.keyword).join(', ');
  document.getElementById('monthlySummary').innerHTML = `
    이번 달 총 <strong>${ALL_ITEMS.length}건</strong>의 AI 관련 자료가 수집되었습니다.<br>
    가장 활발한 분야는 <strong>${topCat}</strong>이며,
    핵심 키워드는 <strong>${topKeywords}</strong> 등이 주목받고 있습니다.<br>
    ArXiv, HuggingFace, OpenAI, Google AI 등 ${SOURCE_STATS.length}개 소스에서 실시간 수집된 데이터입니다.`;

  // 소스별 바 차트
  renderMonthlyBarChart();

  // 키워드 히트맵
  renderKeywordHeatmap('monthlyKeywords', KEYWORDS);

  // TOP 10 기사
  renderTopList('monthlyTopItems', ALL_ITEMS.slice(0, 10));
}

function renderMonthlyBarChart() {
  const ctx = document.getElementById('monthlyBarChart');
  if (!ctx) return;
  if (monthlyBarInst) monthlyBarInst.destroy();

  const top12 = SOURCE_STATS.slice(0, 12);
  const labels = top12.map(s => s.source);
  const values = top12.map(s => s.count);

  monthlyBarInst = new Chart(ctx, {
    type: 'bar',
    data: {
      labels,
      datasets: [{
        label: '수집 건수',
        data: values,
        backgroundColor: 'rgba(108,99,255,0.6)',
        borderColor: 'rgba(108,99,255,0.9)',
        borderWidth: 1,
        borderRadius: 6,
        borderSkipped: false,
      }]
    },
    options: {
      indexAxis: 'y',
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { color: '#9aa3b8' }, grid: { color: 'rgba(255,255,255,0.05)' }, beginAtZero: true },
        y: { ticks: { color: '#9aa3b8', font: { size: 12 } }, grid: { display: false } }
      }
    }
  });
}

// ═══════════════════════════════════════════════════
// 7. 다운로드 (주간 리포트 TXT)
// ═══════════════════════════════════════════════════
function downloadReport() {
  const now   = new Date();
  const lines = [
    `AI PULSE — 주간 리포트`,
    `생성 일시: ${now.toLocaleString('ko-KR')}`,
    `총 수집 기사: ${ALL_ITEMS.length}건`,
    `============================================================`,
    '',
    '■ 카테고리별 분포',
    ...Object.entries(CAT_STATS).map(([k,v]) => `  ${k}: ${v}건`),
    '',
    '■ 핵심 키워드 TOP 10',
    ...KEYWORDS.slice(0,10).map((k,i) => `  ${i+1}. ${k.keyword} (${k.count}회)`),
    '',
    '■ 수집 소스 현황',
    ...SOURCE_STATS.slice(0,10).map(s => `  ${s.source}: ${s.count}건`),
    '',
    '■ 주목할 논문 TOP 5',
    ...ALL_ITEMS.filter(i=>i.badge==='paper').slice(0,5).map((it,i) =>
      `  ${i+1}. ${it.title}\n     ${it.url}`),
    '',
    '■ 신규 AI 도구 TOP 5',
    ...ALL_ITEMS.filter(i=>i.badge==='tool'||i.badge==='official').slice(0,5).map((it,i) =>
      `  ${i+1}. ${it.title}\n     ${it.url}`),
    '',
    '============================================================',
    'AI PULSE — https://github.com/your-username/ai-pulse',
  ];

  const blob = new Blob([lines.join('\n')], { type: 'text/plain;charset=utf-8' });
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement('a');
  a.href     = url;
  a.download = `ai_pulse_weekly_${fmtDateFile(now)}.txt`;
  a.click();
  URL.revokeObjectURL(url);
}

// ═══════════════════════════════════════════════════
// 8. UI 헬퍼
// ═══════════════════════════════════════════════════
function showSkeleton(show) {
  const skel = document.getElementById('loadingSkeleton');
  if (skel) skel.style.display = show ? 'contents' : 'none';
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

function escHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g,'&amp;').replace(/</g,'&lt;')
    .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function fmtDate(d) {
  return `${d.getMonth()+1}/${d.getDate()}`;
}
function fmtDateFile(d) {
  const mm = String(d.getMonth()+1).padStart(2,'0');
  const dd = String(d.getDate()).padStart(2,'0');
  return `${d.getFullYear()}${mm}${dd}`;
}

// ═══════════════════════════════════════════════════
// 9. 이벤트 바인딩
// ═══════════════════════════════════════════════════
function bindEvents() {
  // 탭 전환
  document.querySelectorAll('.nav-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.tab-section').forEach(s => s.classList.remove('active'));
      btn.classList.add('active');
      document.getElementById(`tab-${btn.dataset.tab}`).classList.add('active');

      // 차트 리사이즈
      setTimeout(() => {
        [catChartInst, weeklyBarInst, monthlyBarInst].forEach(c => c?.resize());
      }, 50);
    });
  });

  // 필터 버튼
  document.querySelectorAll('.filter-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      currentCat = btn.dataset.cat;
      renderCards();
    });
  });

  // 검색
  document.getElementById('searchInput').addEventListener('input', e => {
    currentSearch = e.target.value.trim();
    renderCards();
  });

  // 다크/라이트 테마
  const themeBtn  = document.getElementById('themeBtn');
  const savedTheme = localStorage.getItem('ai-pulse-theme') || 'dark';
  applyTheme(savedTheme);

  themeBtn.addEventListener('click', () => {
    const cur  = document.documentElement.dataset.theme;
    const next = cur === 'dark' ? 'light' : 'dark';
    applyTheme(next);
    localStorage.setItem('ai-pulse-theme', next);
  });
}

function applyTheme(theme) {
  document.documentElement.dataset.theme = theme;
  const icon = document.querySelector('#themeBtn i');
  if (icon) {
    icon.className = theme === 'dark' ? 'fa-solid fa-sun' : 'fa-solid fa-moon';
  }
  // 차트 색상 업데이트
  setTimeout(() => {
    [catChartInst, weeklyBarInst, monthlyBarInst].forEach(c => c?.update());
  }, 100);
}

// ═══════════════════════════════════════════════════
// 10. 초기화
// ═══════════════════════════════════════════════════
document.addEventListener('DOMContentLoaded', () => {
  bindEvents();
  loadData();
});

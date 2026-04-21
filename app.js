'use strict';
/* ═══════════════════════════════════════════════════════════
   AI 트렌드  app.js  v13
   참고앱(ai-trend.hamsterapp.net) 구조 완전 재구성
   - 소스 / 기간 / 분류 / 정렬 / 보기 필터
   - 카드 뷰 + 리스트 뷰
   - 다크모드
═══════════════════════════════════════════════════════════ */

/* ── 전역 상태 ─────────────────────────────────────────── */
let ALL_ITEMS = [];       // 전체 아이템 (날짜 무관)
let DATA_DATE = '';

const filters = {
  source: '전체',
  period: '전체',
  type:   '전체',
  sort:   'latest',
  minor:  false,
  view:   'card',
};

/* ── 번역 우선순위 ─────────────────────────────────────── */
function bestText(item) {
  const isKo = item.lang === 'ko';
  if (isKo) return item.one_line || item.title || '';
  const kr = (item.one_line_kr || '').trim();
  const isSame = kr === item.one_line || kr === item.title;
  if (kr && !isSame) return kr;
  const tkr = (item.title_kr || '').trim();
  if (tkr && tkr !== item.title) return tkr;
  return item.one_line || item.title || '';
}

/* ── 분류(type) 표시 설정 ──────────────────────────────── */
const TYPE_META = {
  '모델출시': { color: '#8b5cf6', bg: '#f5f3ff', emoji: '🤖' },
  'API변경':  { color: '#0ea5e9', bg: '#f0f9ff', emoji: '🔧' },
  '기능추가': { color: '#10b981', bg: '#f0fdf4', emoji: '✨' },
  '가격변경': { color: '#f59e0b', bg: '#fffbeb', emoji: '💰' },
  '도구출시': { color: '#ef4444', bg: '#fff1f2', emoji: '🚀' },
  '뉴스':     { color: '#6b7280', bg: '#f9fafb', emoji: '📰' },
  '논문':     { color: '#7c3aed', bg: '#faf5ff', emoji: '📄' },
};

const SOURCE_EMOJI = {
  'Anthropic': '🟣', 'Claude Code': '🔧', 'OpenAI': '🟢',
  'GitHub Copilot': '🤖', 'Google': '🔵', 'Meta': '🔷',
  'Mistral': '🟠', 'Cursor': '📝', 'VS Code': '💻',
};

function getSourceEmoji(source) {
  for (const [k, v] of Object.entries(SOURCE_EMOJI)) {
    if (source.includes(k)) return v;
  }
  return '📡';
}

/* ── 날짜 유틸 ─────────────────────────────────────────── */
function getKstNow() {
  const now = new Date();
  // KST = UTC+9
  return new Date(now.getTime() + 9 * 3600 * 1000);
}

function isInPeriod(item, period) {
  const raw = (item.date || item.collect_date || '').slice(0, 10);
  if (!raw) return true;
  const itemDate = new Date(raw + 'T00:00:00+09:00');
  const now = getKstNow();
  const nowDate = new Date(now.toISOString().slice(0, 10) + 'T00:00:00+09:00');
  const diffDays = (nowDate - itemDate) / 86400000;

  if (period === '오늘')   return diffDays < 1;
  if (period === '이번주') return diffDays < 7;
  if (period === '이번달') return diffDays < 30;
  return true; // 전체
}

function fmtDate(dateStr) {
  if (!dateStr) return '';
  const d = new Date(dateStr.replace(' ', 'T'));
  if (isNaN(d)) return dateStr.slice(0, 10);
  const now = getKstNow();
  const diff = (now - d) / 1000;
  if (diff < 3600)  return `${Math.floor(diff / 60)}분 전`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}시간 전`;
  return dateStr.slice(0, 10);
}

/* ── 필터 적용 ─────────────────────────────────────────── */
function applyFilters() {
  let items = [...ALL_ITEMS];

  // 소스
  if (filters.source !== '전체') {
    items = items.filter(i => i.source === filters.source);
  }
  // 기간
  if (filters.period !== '전체') {
    items = items.filter(i => isInPeriod(i, filters.period));
  }
  // 분류
  if (filters.type !== '전체') {
    items = items.filter(i => (i.type || '뉴스') === filters.type);
  }
  // 마이너 제외 (importance = new)
  if (!filters.minor) {
    const nonMinor = items.filter(i => (i.importance?.class || 'new') !== 'new');
    items = nonMinor.length > 0 ? nonMinor : items;
  }
  // 정렬
  if (filters.sort === 'hot') {
    const order = { hot: 0, star: 1, new: 2 };
    items.sort((a, b) =>
      (order[a.importance?.class] ?? 2) - (order[b.importance?.class] ?? 2)
    );
  } else {
    items.sort((a, b) => {
      const da = new Date((a.date || a.collect_date || '').replace(' ', 'T'));
      const db = new Date((b.date || b.collect_date || '').replace(' ', 'T'));
      return db - da;
    });
  }
  return items;
}

/* ── 카드 빌더 ─────────────────────────────────────────── */
function esc(s) {
  return String(s || '')
    .replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function buildCard(item) {
  const type = item.type || '뉴스';
  const tm = TYPE_META[type] || TYPE_META['뉴스'];
  const text = bestText(item);
  const isKo = item.lang === 'ko';
  const origTitle = (!isKo && item.title) ? item.title : '';
  const srcEmoji = getSourceEmoji(item.source || '');
  const dateStr = fmtDate(item.date || item.collect_date);
  const impCls = item.importance?.class || 'new';

  return `<a class="news-card imp-${esc(impCls)}" href="${esc(item.url || '#')}" target="_blank" rel="noopener">
    <div class="nc-type" style="color:${tm.color};background:${tm.bg}">
      ${tm.emoji} ${esc(type)}
    </div>
    <div class="nc-body">
      <div class="nc-text">${esc(text.slice(0, 80))}</div>
      ${origTitle ? `<div class="nc-orig">${esc(origTitle.slice(0, 70))}</div>` : ''}
    </div>
    <div class="nc-footer">
      <span class="nc-src">${srcEmoji} ${esc(item.source || '')}</span>
      <span class="nc-date">${esc(dateStr)}</span>
    </div>
  </a>`;
}

/* ── 리스트 아이템 빌더 ──────────────────────────────────── */
function buildListItem(item) {
  const type = item.type || '뉴스';
  const tm = TYPE_META[type] || TYPE_META['뉴스'];
  const text = bestText(item);
  const srcEmoji = getSourceEmoji(item.source || '');
  const dateStr = fmtDate(item.date || item.collect_date);
  const impCls = item.importance?.class || 'new';

  return `<a class="news-item imp-${esc(impCls)}" href="${esc(item.url || '#')}" target="_blank" rel="noopener">
    <span class="ni-type-dot" style="background:${tm.color}" title="${esc(type)}"></span>
    <div class="ni-body">
      <div class="ni-title">${esc(text.slice(0, 100))}</div>
      <div class="ni-meta">
        <span class="ni-type-badge" style="color:${tm.color};background:${tm.bg}">${tm.emoji} ${esc(type)}</span>
        <span class="ni-src">${srcEmoji} ${esc(item.source || '')}</span>
        <span class="ni-date">${esc(dateStr)}</span>
        ${impCls === 'hot' ? '<span class="ni-hot">🔥</span>' : ''}
      </div>
    </div>
    <span class="ni-arrow">›</span>
  </a>`;
}

/* ── 렌더링 ────────────────────────────────────────────── */
function render() {
  const items = applyFilters();
  const cardGrid = document.getElementById('cardGrid');
  const newsList = document.getElementById('newsList');
  const countEl  = document.getElementById('resultCount');

  countEl.textContent = `${items.length}개 결과`;

  if (filters.view === 'card') {
    cardGrid.style.display = '';
    newsList.style.display = 'none';
    if (!items.length) {
      cardGrid.innerHTML = '<div class="empty-state">조건에 맞는 소식이 없어요.</div>';
    } else {
      cardGrid.innerHTML = items.slice(0, 80).map(buildCard).join('');
    }
  } else {
    cardGrid.style.display = 'none';
    newsList.style.display = '';
    if (!items.length) {
      newsList.innerHTML = '<div class="empty-state">조건에 맞는 소식이 없어요.</div>';
    } else {
      newsList.innerHTML = items.slice(0, 80).map(buildListItem).join('');
    }
  }
}

/* ── 소스 칩 동적 생성 ──────────────────────────────────── */
function buildSourceChips() {
  const container = document.getElementById('sourceChips');
  if (!container) return;

  // 소스별 건수
  const counts = {};
  ALL_ITEMS.forEach(i => {
    counts[i.source] = (counts[i.source] || 0) + 1;
  });

  // 건수 많은 순으로 정렬, 상위 8개만
  const topSources = Object.entries(counts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 8)
    .map(([name]) => name);

  const chips = ['전체', ...topSources];
  container.innerHTML = chips.map(src =>
    `<button class="fchip${src === '전체' ? ' active' : ''}" data-filter="source" data-val="${esc(src)}">${esc(src)}</button>`
  ).join('');

  // 이벤트 재바인딩
  container.querySelectorAll('.fchip').forEach(btn => {
    btn.addEventListener('click', () => handleFilterChip(btn));
  });
}

/* ── 이벤트 바인딩 ──────────────────────────────────────── */
function handleFilterChip(btn) {
  const filterKey = btn.dataset.filter;
  const val = btn.dataset.val;

  // 같은 그룹 active 해제
  document.querySelectorAll(`.fchip[data-filter="${filterKey}"]`)
    .forEach(b => b.classList.remove('active'));
  btn.classList.add('active');

  filters[filterKey] = val;
  render();
}

function bindEvents() {
  // 필터 칩
  document.querySelectorAll('.fchip').forEach(btn => {
    btn.addEventListener('click', () => handleFilterChip(btn));
  });

  // 마이너 토글
  document.getElementById('minorToggle')?.addEventListener('change', e => {
    filters.minor = e.target.checked;
    render();
  });

  // 카드/리스트 보기 전환
  document.getElementById('viewCard')?.addEventListener('click', () => {
    filters.view = 'card';
    document.getElementById('viewCard').classList.add('active');
    document.getElementById('viewList').classList.remove('active');
    render();
  });
  document.getElementById('viewList')?.addEventListener('click', () => {
    filters.view = 'list';
    document.getElementById('viewList').classList.add('active');
    document.getElementById('viewCard').classList.remove('active');
    render();
  });

  // 다크모드
  const saved = localStorage.getItem('ai-trend-theme') || 'light';
  applyTheme(saved);
  document.getElementById('themeBtn')?.addEventListener('click', () => {
    const next = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
    applyTheme(next);
    localStorage.setItem('ai-trend-theme', next);
  });
}

function applyTheme(theme) {
  document.documentElement.dataset.theme = theme;
  const btn = document.getElementById('themeBtn');
  if (btn) btn.textContent = theme === 'dark' ? '☀️' : '🌙';
}

/* ── 데이터 로드 ────────────────────────────────────────── */
async function loadData() {
  const skeleton = document.getElementById('loadingSkeleton');
  try {
    const r = await fetch('data/ai_news.json?_=' + Date.now());
    if (!r.ok) throw new Error('HTTP ' + r.status);
    const d = await r.json();

    DATA_DATE = d.date || '';
    ALL_ITEMS = d.items || [];

    // updateTime
    const el = document.getElementById('updateTime');
    if (el) el.textContent = d.generated_at ? `업데이트: ${d.generated_at} KST` : '';

    if (skeleton) skeleton.style.display = 'none';

    // 소스 칩 동적 생성
    buildSourceChips();

    // 초기 렌더
    render();

  } catch (e) {
    if (skeleton) skeleton.style.display = 'none';
    const box = document.getElementById('errorBox');
    const msg = document.getElementById('errorMsg');
    if (box && msg) {
      msg.textContent = e.message + '\nGitHub Actions 실행 후 새로고침 해주세요.';
      box.style.display = 'flex';
    }
  }
}

/* ── 초기화 ────────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
  bindEvents();
  loadData();
});

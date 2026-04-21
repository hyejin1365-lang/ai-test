'use strict';
/* ═══════════════════════════════════════════════════════════
   AI 트렌드  app.js  v14
   참고앱(ai-trend.hamsterapp.net) 기능 완전 동일 구현
═══════════════════════════════════════════════════════════ */

/* ── 전역 상태 ──────────────────────────────────────────── */
let ALL_ITEMS   = [];   // 전체 아이템
let DATA_DATE   = '';   // 수집 날짜
let curSource   = 'all';
let curView     = 'card';
let likedSet    = new Set(JSON.parse(localStorage.getItem('ai-liked') || '[]'));

/* ── 소스 정의 (참고앱과 동일) ──────────────────────────── */
const SOURCE_DEF = [
  { key:'anthropic',    label:'🟣 Anthropic',       names:['Anthropic News','Anthropic Blog'] },
  { key:'openai',       label:'🟢 OpenAI',           names:['OpenAI Blog','OpenAI News (영상)','OpenAI Dev Changelog'] },
  { key:'google',       label:'🔵 Google',           names:['Google AI Blog','Gemini API Changelog','DeepMind'] },
  { key:'meta',         label:'🔷 Meta',             names:['Meta AI Blog'] },
  { key:'mistral',      label:'🟠 Mistral',          names:['Mistral Changelog'] },
  { key:'cursor',       label:'📝 Cursor',           names:['Cursor Changelog'] },
  { key:'claude-code',  label:'🔧 Claude Code',      names:['Claude Code','Anthropic Blog'] },
  { key:'claude-docs',  label:'📄 Claude Code Docs', names:['Claude Code Docs'] },
  { key:'openai-codex', label:'🔧 OpenAI Codex',     names:['OpenAI Codex','Codex'] },
  { key:'anthropic-sdk',label:'📦 Anthropic SDK',    names:['Anthropic SDK'] },
  { key:'openai-sdk',   label:'📦 OpenAI SDK',       names:['OpenAI SDK'] },
  { key:'llama',        label:'🦙 Llama Models',     names:['Llama','Meta AI Blog'] },
  { key:'vscode',       label:'💻 VS Code',          names:['VS Code Release Notes','VS Code'] },
  { key:'github',       label:'🤖 GitHub Copilot',   names:['GitHub Changelog','GitHub Copilot'] },
  { key:'mcp',          label:'🔌 MCP',              names:['MCP','Model Context Protocol'] },
];

const SOURCE_EMOJI = {
  'Anthropic News':'🟣', 'Anthropic Blog':'🟣',
  'OpenAI Blog':'🟢', 'OpenAI News (영상)':'🟢',
  'Google AI Blog':'🔵', 'DeepMind':'🔵', 'Gemini API Changelog':'🔵',
  'Meta AI Blog':'🔷',
  'Mistral Changelog':'🟠',
  'Cursor Changelog':'📝',
  'GitHub Changelog':'🤖', 'GitHub Copilot':'🤖',
  'VS Code Release Notes':'💻', 'VS Code':'💻',
};

function getSourceEmoji(source) {
  if (!source) return '📡';
  if (SOURCE_EMOJI[source]) return SOURCE_EMOJI[source];
  if (source.includes('Anthropic')) return '🟣';
  if (source.includes('OpenAI'))    return '🟢';
  if (source.includes('Google') || source.includes('Gemini') || source.includes('DeepMind')) return '🔵';
  if (source.includes('Meta') || source.includes('Llama')) return '🔷';
  if (source.includes('Mistral'))   return '🟠';
  if (source.includes('Cursor'))    return '📝';
  if (source.includes('GitHub') || source.includes('Copilot')) return '🤖';
  if (source.includes('Claude'))    return '🔧';
  if (source.includes('VS Code'))   return '💻';
  if (source.includes('ArXiv'))     return '📄';
  if (source.includes('AI타임스') || source.includes('바이라인') || source.includes('더에이아이')) return '🇰🇷';
  return '📡';
}

/* ── 소스 CSS 클래스 ─────────────────────────────────────── */
function getSourceClass(source) {
  if (!source) return '';
  const s = source.toLowerCase();
  if (s.includes('anthropic blog') || s.includes('anthropic news')) return 'source-anthropic';
  if (s.includes('claude code docs')) return 'source-claude-docs';
  if (s.includes('claude code') || s.includes('claude')) return 'source-claude-code';
  if (s.includes('openai codex') || s.includes('codex')) return 'source-openai-codex';
  if (s.includes('openai')) return 'source-openai';
  if (s.includes('gemini') || s.includes('deepmind') || s.includes('google')) return 'source-google';
  if (s.includes('meta') || s.includes('llama')) return 'source-meta';
  if (s.includes('mistral')) return 'source-mistral';
  if (s.includes('cursor')) return 'source-cursor';
  if (s.includes('github')) return 'source-github';
  if (s.includes('vs code') || s.includes('vscode')) return 'source-vscode';
  if (s.includes('anthropic sdk')) return 'source-anthropic-sdk';
  if (s.includes('openai sdk')) return 'source-openai-sdk';
  if (s.includes('mcp')) return 'source-mcp';
  return '';
}

/* ── 분류 배지 CSS 클래스 ────────────────────────────────── */
function getBadgeClass(type) {
  const map = {
    '모델출시': 'badge-model',
    'API변경':  'badge-api',
    '기능추가': 'badge-feature',
    '가격변경': 'badge-pricing',
    '도구출시': 'badge-tool',
    '뉴스':     'badge-other',
    '논문':     'badge-other',
  };
  return map[type] || 'badge-other';
}

/* ── 관심도(heat) 계산 ───────────────────────────────────── */
function getHeat(item) {
  const cls = item.importance?.class || 'new';
  if (cls === 'hot')  return 4;
  if (cls === 'star') return 2;
  return 0;
}

function heatBadgeHTML(heat) {
  if (heat <= 0) return '';
  const flames = heat >= 4 ? '🔥🔥🔥 HOT' : heat >= 3 ? '🔥🔥🔥' : '🔥🔥';
  const title  = `관심도 ${Math.min(heat,5)}/5`;
  return `<span class="heat-badge heat-${Math.min(heat,5)}" title="${title}">${flames}</span>`;
}

/* ── 날짜 유틸 ───────────────────────────────────────────── */
function fmtRelDate(dateStr) {
  if (!dateStr) return '';
  const d = new Date(dateStr.replace(' ', 'T'));
  if (isNaN(d)) return dateStr.slice(0, 10);
  const now = Date.now();
  const diff = (now - d.getTime()) / 1000;
  if (diff < 3600)       return `${Math.floor(diff / 60)}분 전`;
  if (diff < 86400)      return `${Math.floor(diff / 3600)}시간 전`;
  if (diff < 86400 * 2)  return '어제';
  if (diff < 86400 * 7)  return `${Math.floor(diff / 86400)}일 전`;
  if (diff < 86400 * 14) return '1주 전';
  return dateStr.slice(0, 10);
}

function fmtGroupDate(dateStr) {
  if (!dateStr) return '';
  const d = new Date(dateStr + 'T00:00:00');
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const target = new Date(d.getFullYear(), d.getMonth(), d.getDate());
  const diffDays = Math.round((today - target) / 86400000);

  const y = d.getFullYear();
  const m = d.getMonth() + 1;
  const day = d.getDate();
  const base = `📅 ${y}년 ${m}월 ${day}일`;
  if (diffDays === 0) return base + ' (오늘)';
  if (diffDays === 1) return base + ' (어제)';
  return base;
}

function getDaysValue() {
  return parseInt(document.getElementById('daysFilter')?.value || '365');
}

function isInPeriod(item, days) {
  if (days >= 365) return true;
  const raw = (item.date || item.collect_date || '').slice(0, 10);
  if (!raw) return true;
  const d = new Date(raw + 'T00:00:00');
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const diffDays = Math.round((today - d) / 86400000);
  return diffDays < days;
}

/* ── 번역 우선순위 ───────────────────────────────────────── */
function bestTitle(item) {
  const isKo = item.lang === 'ko';
  if (isKo) return item.title || '';
  const tkr = (item.title_kr || '').trim();
  if (tkr && tkr !== item.title) return tkr;
  return item.title || '';
}

function bestEasy(item) {
  const isKo = item.lang === 'ko';
  if (isKo) return item.one_line || item.title || '';
  const kr = (item.one_line_kr || '').trim();
  const isSame = kr === item.one_line || kr === item.title;
  if (kr && !isSame) return kr;
  return item.one_line || '';
}

function bestTip(item) {
  const sum = (item.summary || '').trim();
  const tip = sum.split('\n').find(l => l.includes('💡'));
  if (tip) return tip.replace(/^.*💡/, '💡').trim();
  if (item.lang === 'ko') return '';
  return '';
}

/* ── HTML escape ─────────────────────────────────────────── */
function esc(s) {
  return String(s || '')
    .replace(/&/g,'&amp;').replace(/</g,'&lt;')
    .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

/* ═══════════════════════════════════════════════════════════
   필터 적용
═══════════════════════════════════════════════════════════ */
function applyFilters() {
  const days     = getDaysValue();
  const category = document.getElementById('categoryFilter')?.value || 'all';
  const sort     = document.getElementById('sortFilter')?.value || 'date';
  const minor    = document.getElementById('showMinor')?.checked || false;

  let items = ALL_ITEMS.filter(item => {
    // 소스 필터
    if (curSource !== 'all') {
      const def = SOURCE_DEF.find(d => d.key === curSource);
      if (def && !def.names.some(n => (item.source || '').includes(n))) return false;
    }
    // 기간 필터
    if (!isInPeriod(item, days)) return false;
    // 분류 필터
    if (category !== 'all' && (item.type || '뉴스') !== category) return false;
    // 마이너 제외
    if (!minor) {
      if ((item.importance?.class || 'new') === 'new') {
        // 마이너: importance=new 이고 국내 뉴스·논문·비즈니스 카테고리
        const minorCats = new Set(['논문', '비즈니스', 'AI법률']);
        if (minorCats.has(item.category)) return false;
      }
    }
    return true;
  });

  // 정렬
  if (sort === 'heat') {
    items.sort((a, b) => getHeat(b) - getHeat(a));
  } else {
    items.sort((a, b) => {
      const da = new Date((a.date || a.collect_date || '').replace(' ','T'));
      const db = new Date((b.date || b.collect_date || '').replace(' ','T'));
      return db - da;
    });
  }

  renderFeed(items);
}

/* ═══════════════════════════════════════════════════════════
   카드 렌더링
═══════════════════════════════════════════════════════════ */
function buildCard(item) {
  const srcCls  = getSourceClass(item.source);
  const srcEmoji= getSourceEmoji(item.source);
  const heat    = getHeat(item);
  const title   = bestTitle(item);
  const easy    = bestEasy(item);
  const tip     = bestTip(item);
  const origSum = (item.lang !== 'ko' && item.title) ? item.title : '';
  const type    = item.type || '뉴스';
  const bdgCls  = getBadgeClass(type);
  const dateStr = fmtRelDate(item.date || item.collect_date);
  const liked   = likedSet.has(item.id);
  const id      = esc(item.id || '');

  return `<div class="update-card ${esc(srcCls)}">
    <div class="card-header">
      <span class="card-source">${srcEmoji} ${esc(item.source || '')}</span>
      ${heat > 0 ? heatBadgeHTML(heat) : ''}
    </div>
    <div class="card-title">
      <a href="${esc(item.url || '#')}" target="_blank" rel="noopener">${esc(title)}</a>
    </div>
    ${origSum ? `<div class="card-summary">${esc(origSum)}</div>` : ''}
    ${easy ? `<div class="card-easy">💬 ${esc(easy)}</div>` : ''}
    ${tip  ? `<div class="card-usage">${esc(tip)}</div>` : ''}
    <div class="card-meta">
      <span class="badge ${bdgCls}">${esc(type)}</span>
      <span>${esc(dateStr)}</span>
      <button class="like-btn${liked ? ' liked' : ''}" onclick="toggleLike('${id}',this)">
        ${liked ? '❤️' : '🤍'} <span class="like-count"></span>
      </button>
      <button class="yt-btn" onclick="findVideos('${esc(item.url || '')}',this)">▶ 영상 찾기</button>
    </div>
  </div>`;
}

/* ── 리스트 아이템 빌더 ───────────────────────────────────── */
function buildListItem(item) {
  const srcCls  = getSourceClass(item.source);
  const title   = bestTitle(item);
  const easy    = bestEasy(item);
  const type    = item.type || '뉴스';
  const bdgCls  = getBadgeClass(type);
  const dateStr = fmtRelDate(item.date || item.collect_date);
  // 소스 보더 색상을 dot에 적용하기 위해 class 전달
  return `<a class="list-item" href="${esc(item.url || '#')}" target="_blank" rel="noopener">
    <span class="list-dot ${esc(srcCls)}" style="background:currentColor"></span>
    <div class="list-body">
      <div class="list-title">${esc(title)}</div>
      <div class="list-meta">
        <span class="badge ${bdgCls}">${esc(type)}</span>
        <span class="list-src">${esc(item.source || '')}</span>
        ${easy ? `<span class="list-date">· ${esc(easy.slice(0,50))}</span>` : ''}
        <span class="list-date">${esc(dateStr)}</span>
      </div>
    </div>
    <span class="list-arrow">›</span>
  </a>`;
}

/* ── 날짜 그룹 빌더 ──────────────────────────────────────── */
function renderFeed(items) {
  const container = document.getElementById('updatesList');
  if (!container) return;

  if (!items.length) {
    container.innerHTML = '<div class="empty-state">조건에 맞는 소식이 없어요.</div>';
    return;
  }

  const sort = document.getElementById('sortFilter')?.value || 'date';

  if (sort === 'heat' || curView === 'list') {
    // 관심도순: 날짜 그룹 없이 일렬
    if (curView === 'list') {
      const dateGroups = groupByDate(items);
      container.innerHTML = '<div class="list-view">' +
        dateGroups.map(([date, grpItems]) =>
          `<div class="date-group">
            <div class="date-label">${fmtGroupDate(date)}</div>
            ${grpItems.map(buildListItem).join('')}
          </div>`
        ).join('') +
      '</div>';
    } else {
      // 관심도순 카드: 날짜 그룹 없이
      container.innerHTML = items.slice(0, 100).map(buildCard).join('');
    }
  } else {
    // 최신순 카드: 날짜별 그룹
    const dateGroups = groupByDate(items);
    container.innerHTML = dateGroups.map(([date, grpItems]) =>
      `<div class="date-group">
        <div class="date-label">${fmtGroupDate(date)}</div>
        ${grpItems.map(buildCard).join('')}
      </div>`
    ).join('');
  }
}

function groupByDate(items) {
  const map = new Map();
  items.forEach(item => {
    const d = (item.date || item.collect_date || '').slice(0, 10) || 'unknown';
    if (!map.has(d)) map.set(d, []);
    map.get(d).push(item);
  });
  return [...map.entries()].sort((a, b) => b[0].localeCompare(a[0]));
}

/* ═══════════════════════════════════════════════════════════
   소스 탭 동적 생성
═══════════════════════════════════════════════════════════ */
function buildSourceTabs() {
  const container = document.getElementById('sourceTabs');
  if (!container) return;

  // 실제 데이터에 있는 소스만 표시
  const existingSources = new Set(ALL_ITEMS.map(i => i.source || ''));

  // 전체 버튼 (이미 있음)
  let html = `<button class="${curSource === 'all' ? 'active' : ''}" data-source="all" onclick="selectSource('all',this)">전체</button>`;

  let addedSep = false;
  SOURCE_DEF.forEach((def, idx) => {
    const hasData = def.names.some(n => [...existingSources].some(s => s.includes(n)));
    if (!hasData) return;

    // 구분선: Claude Code / OpenAI Codex 전에
    if (!addedSep && (def.key === 'claude-code' || def.key === 'openai-codex')) {
      html += `<span class="filter-sep">│</span>`;
      addedSep = true;
    }

    html += `<button class="${curSource === def.key ? 'active' : ''}" data-source="${def.key}" onclick="selectSource('${def.key}',this)">${def.label}</button>`;
  });

  container.innerHTML = html;
}

function selectSource(key, btn) {
  curSource = key;
  document.querySelectorAll('#sourceTabs button').forEach(b => b.classList.remove('active'));
  if (btn) btn.classList.add('active');
  applyFilters();
}

/* ═══════════════════════════════════════════════════════════
   보기 전환
═══════════════════════════════════════════════════════════ */
function setView(mode) {
  curView = mode;
  document.getElementById('btnCard')?.classList.toggle('active', mode === 'card');
  document.getElementById('btnList')?.classList.toggle('active', mode === 'list');
  applyFilters();
}

/* ═══════════════════════════════════════════════════════════
   좋아요
═══════════════════════════════════════════════════════════ */
function toggleLike(id, btn) {
  if (likedSet.has(id)) {
    likedSet.delete(id);
    btn.innerHTML = '🤍 <span class="like-count"></span>';
    btn.classList.remove('liked');
  } else {
    likedSet.add(id);
    btn.innerHTML = '❤️ <span class="like-count"></span>';
    btn.classList.add('liked');
  }
  localStorage.setItem('ai-liked', JSON.stringify([...likedSet]));
}

/* ═══════════════════════════════════════════════════════════
   영상 찾기 (YouTube 검색 링크)
═══════════════════════════════════════════════════════════ */
function findVideos(urlOrTitle, btn) {
  // 제목을 카드에서 찾아서 YouTube 검색
  const card = btn.closest('.update-card');
  const titleEl = card?.querySelector('.card-title a');
  const query = titleEl ? titleEl.textContent.trim() : urlOrTitle;
  const ytUrl = 'https://www.youtube.com/results?search_query=' + encodeURIComponent(query + ' AI');
  window.open(ytUrl, '_blank');
}

/* ═══════════════════════════════════════════════════════════
   다크/라이트 모드
═══════════════════════════════════════════════════════════ */
function applyTheme(theme) {
  document.documentElement.dataset.theme = theme;
  const btn = document.getElementById('themeBtn');
  if (btn) btn.textContent = theme === 'dark' ? '☀️' : '🌙';
}

/* ═══════════════════════════════════════════════════════════
   데이터 로드
═══════════════════════════════════════════════════════════ */
async function loadData() {
  const loading = document.getElementById('loadingWrap');
  const errWrap = document.getElementById('errorWrap');
  const errMsg  = document.getElementById('errorMsg');

  try {
    const r = await fetch('data/ai_news.json?_=' + Date.now());
    if (!r.ok) throw new Error('HTTP ' + r.status);
    const d = await r.json();

    DATA_DATE  = d.date || '';
    ALL_ITEMS  = d.items || [];

    // 헤더 업데이트
    const ut = document.getElementById('updateTime');
    if (ut && d.generated_at) {
      ut.textContent = `마지막 빌드: ${d.generated_at} (KST) · 업데이트 ${ALL_ITEMS.length}건`;
    }

    if (loading) loading.style.display = 'none';

    // 소스 탭 동적 생성
    buildSourceTabs();

    // 초기 렌더 (이번주 기본)
    applyFilters();

  } catch (e) {
    if (loading) loading.style.display = 'none';
    if (errWrap && errMsg) {
      errMsg.textContent = e.message + '\nGitHub Actions 실행 후 새로고침 해주세요.';
      errWrap.style.display = 'flex';
    }
  }
}

/* ═══════════════════════════════════════════════════════════
   이벤트 바인딩
═══════════════════════════════════════════════════════════ */
function bindEvents() {
  // 테마
  const saved = localStorage.getItem('ai-theme') || 'dark';
  applyTheme(saved);
  document.getElementById('themeBtn')?.addEventListener('click', () => {
    const next = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
    applyTheme(next);
    localStorage.setItem('ai-theme', next);
  });

  // 보기 버튼
  document.getElementById('btnCard')?.addEventListener('click', () => setView('card'));
  document.getElementById('btnList')?.addEventListener('click', () => setView('list'));
}

/* ═══════════════════════════════════════════════════════════
   초기화
═══════════════════════════════════════════════════════════ */
document.addEventListener('DOMContentLoaded', () => {
  bindEvents();
  loadData();
});

/* ============================================================
   app.js — 서울 지하철 AI 비서 | 메인 애플리케이션 로직
   ============================================================ */

'use strict';

// ── 설정 ──────────────────────────────────────────────────────
const API_BASE_URL = window.ENV_API_BASE_URL || 'http://localhost:8000';

// ── 상태 ──────────────────────────────────────────────────────
let currentConvId = null;   // 진행 중인 대화 ID
let chartTrend    = null;   // Chart.js 인스턴스
let chartLine     = null;
let chartWeekday  = null;
let isColdStart   = false;

// ── 탭 전환 ───────────────────────────────────────────────────
function switchTab(name) {
  document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
  document.getElementById(`tab-${name}`).classList.add('active');
  document.getElementById(`nav-${name}`).classList.add('active');

  if (name === 'data')    loadData();
  if (name === 'history') loadConversations();
  if (name === 'stats')   loadStats();
}

// ── 다크/라이트 모드 ──────────────────────────────────────
function toggleTheme() {
  const html = document.documentElement;
  const isDark = html.dataset.theme === 'dark';
  html.dataset.theme = isDark ? 'light' : 'dark';
  // 차트 색상 업데이트
  if (chartTrend) loadStats();
}

// ── 토스트 ────────────────────────────────────────────────────
function showToast(msg, type = 'info', duration = 3000) {
  const icons = { success: '✅', error: '❌', info: 'ℹ️' };
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  el.innerHTML = `<span>${icons[type]}</span><span>${msg}</span>`;
  document.getElementById('toast-container').appendChild(el);
  setTimeout(() => el.remove(), duration);
}

// ── API 헬퍼 ──────────────────────────────────────────────────
async function apiFetch(path, options = {}) {
  const url = `${API_BASE_URL}${path}`;
  try {
    const res = await fetch(url, {
      headers: { 'Content-Type': 'application/json', ...options.headers },
      ...options,
    });
    if (res.status === 204) return null;
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
    return data;
  } catch (err) {
    // 콜드스타트 감지 (연결 오류 또는 타임아웃)
    if (!isColdStart && (err.message.includes('fetch') || err.message.includes('network'))) {
      showColdStartBanner();
    }
    throw err;
  }
}

function showColdStartBanner() {
  isColdStart = true;
  document.getElementById('cold-start-banner').style.display = 'flex';
  setTimeout(() => {
    document.getElementById('cold-start-banner').style.display = 'none';
    isColdStart = false;
  }, 60000);
}

// ── 숫자 포맷 ─────────────────────────────────────────────────
const fmt = n => Number(n).toLocaleString('ko-KR');

// ════════════════════════════════════════════════════════════════
// ① 채팅
// ════════════════════════════════════════════════════════════════

async function sendMessage() {
  const input = document.getElementById('chat-input');
  const msg   = input.value.trim();
  if (!msg) return;

  input.value = '';
  input.style.height = 'auto';

  // 사용자 메시지 표시
  appendMsg('user', msg);

  // 로딩 인디케이터
  const loadingEl = appendLoading();

  // 전송 버튼 비활성화
  const sendBtn = document.getElementById('send-btn');
  sendBtn.disabled = true;

  try {
    const body = { message: msg, conversation_id: currentConvId, history: [] };
    const data = await apiFetch('/api/chat', {
      method: 'POST',
      body: JSON.stringify(body),
    });

    loadingEl.remove();
    appendMsg('assistant', data.answer, data.tool_calls_used);
    currentConvId = data.conversation_id;

    // Function Calling 로그
    if (data.tool_calls_used?.length) {
      logToolCalls(data.tool_calls_used);
    }
  } catch (err) {
    loadingEl.remove();
    appendMsg('assistant', `❌ 오류가 발생했습니다: ${err.message}`);
    showToast(err.message, 'error');
  } finally {
    sendBtn.disabled = false;
  }
}

function appendMsg(role, content, tools = []) {
  const container = document.getElementById('chat-messages');
  const el = document.createElement('div');
  el.className = `msg ${role}`;

  const avatar = role === 'user' ? '👤' : '🤖';
  const toolBadges = tools.map(t =>
    `<span class="badge badge-tool">🔧 ${t}</span>`
  ).join(' ');

  el.innerHTML = `
    <div class="msg-avatar">${avatar}</div>
    <div class="msg-body">
      <div class="msg-bubble">${escapeHtml(content).replace(/\n/g, '<br>')}</div>
      ${toolBadges ? `<div class="msg-tools">${toolBadges}</div>` : ''}
    </div>
  `;
  container.appendChild(el);
  container.scrollTop = container.scrollHeight;
  return el;
}

function appendLoading() {
  const container = document.getElementById('chat-messages');
  const el = document.createElement('div');
  el.className = 'msg assistant';
  el.innerHTML = `
    <div class="msg-avatar">🤖</div>
    <div class="msg-body">
      <div class="msg-bubble">
        <div class="typing-indicator">
          <span></span><span></span><span></span>
        </div>
      </div>
    </div>
  `;
  container.appendChild(el);
  container.scrollTop = container.scrollHeight;
  return el;
}

function logToolCalls(tools) {
  const log = document.getElementById('tools-log');
  const items = tools.map(t => `<div class="badge badge-tool" style="margin-bottom:4px">🔧 ${t}</div>`).join('');
  log.innerHTML = `<div style="font-size:0.8rem; color:var(--text-muted); margin-bottom:6px;">최근 사용 도구:</div>${items}`;
}

// Enter 전송 (Shift+Enter = 줄바꿈)
document.addEventListener('DOMContentLoaded', () => {
  const input = document.getElementById('chat-input');
  input.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });

  // 초기 데이터 요약 로딩
  loadSummary();
});

// ── 요약 패널 ─────────────────────────────────────────────────
async function loadSummary() {
  const panel = document.getElementById('summary-panel');
  panel.innerHTML = '<div style="color:var(--text-muted); text-align:center; padding:16px;">로딩 중...</div>';
  try {
    const s = await apiFetch('/api/data/summary');
    const trendClass = s.trend.includes('상승') ? 'badge-up' : s.trend.includes('하락') ? 'badge-down' : 'badge-flat';

    panel.innerHTML = `
      <div style="display:flex; flex-direction:column; gap:10px;">
        <div style="font-size:0.8rem; color:var(--text-muted)">기간</div>
        <div style="font-size:0.9rem; font-weight:600">${s.period}</div>
        <div style="font-size:0.8rem; color:var(--text-muted)">총 레코드</div>
        <div style="font-size:1.2rem; font-weight:700; color:var(--accent-2)">${fmt(s.count)}건</div>
        <div style="font-size:0.8rem; color:var(--text-muted)">일평균 승하차</div>
        <div style="font-size:1.1rem; font-weight:700">${fmt(s.metrics.average)}명</div>
        <div style="font-size:0.8rem; color:var(--text-muted)">최고 / 최저</div>
        <div style="font-size:0.88rem">${fmt(s.metrics.max)} / ${fmt(s.metrics.min)}</div>
        <div style="font-size:0.8rem; color:var(--text-muted)">트렌드</div>
        <div><span class="badge ${trendClass}">${s.trend}</span></div>
        <div style="font-size:0.8rem; color:var(--text-muted)">TOP 역</div>
        <div style="font-size:0.82rem; line-height:1.7">${s.top_stations.join('<br>')}</div>
      </div>
    `;
  } catch (err) {
    panel.innerHTML = `<div style="color:var(--danger); font-size:0.85rem">❌ ${err.message}</div>`;
  }
}

// ════════════════════════════════════════════════════════════════
// ② 데이터 관리
// ════════════════════════════════════════════════════════════════

async function loadData() {
  const tbody = document.getElementById('data-tbody');
  tbody.innerHTML = '<tr><td colspan="4" style="text-align:center; color:var(--text-muted)">로딩 중...</td></tr>';
  try {
    const data = await apiFetch('/api/data');
    renderDataTable(data);
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="4" style="color:var(--danger)">${err.message}</td></tr>`;
    showToast(err.message, 'error');
  }
}

function renderDataTable(data) {
  const tbody = document.getElementById('data-tbody');
  if (!data.length) {
    tbody.innerHTML = '<tr><td colspan="4" class="empty-state">데이터가 없습니다.</td></tr>';
    return;
  }

  // 날짜 내림차순 정렬
  const sorted = [...data].sort((a, b) => b.date.localeCompare(a.date));

  tbody.innerHTML = sorted.map(row => `
    <tr id="row-${row.id}">
      <td>${row.date}</td>
      <td>${fmt(row.value)}</td>
      <td>${escapeHtml(row.memo)}</td>
      <td>
        <div class="actions">
          <button class="btn btn-secondary btn-sm" onclick="openEditModal('${row.id}','${row.date}','${row.value}','${escapeHtml(row.memo)}')">✏️</button>
          <button class="btn btn-danger btn-sm" onclick="deleteData('${row.id}')">🗑️</button>
        </div>
      </td>
    </tr>
  `).join('');
}

async function createData() {
  const date  = document.getElementById('data-date').value;
  const value = document.getElementById('data-value').value;
  const memo  = document.getElementById('data-memo').value.trim();

  if (!date || !value || !memo) { showToast('모든 필드를 입력해 주세요.', 'error'); return; }

  try {
    await apiFetch('/api/data', {
      method: 'POST',
      body: JSON.stringify({ date, value: parseInt(value), memo }),
    });
    showToast('데이터가 추가되었습니다!', 'success');
    document.getElementById('data-date').value = '';
    document.getElementById('data-value').value = '';
    document.getElementById('data-memo').value = '';
    loadData();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

// ── 수정 모달 ─────────────────────────────────────────────────
function openEditModal(id, date, value, memo) {
  document.getElementById('edit-id').value   = id;
  document.getElementById('edit-date').value  = date;
  document.getElementById('edit-value').value = value;
  document.getElementById('edit-memo').value  = memo;
  document.getElementById('edit-modal').style.display = 'flex';
}

function closeEditModal(e) {
  if (!e || e.target.id === 'edit-modal') {
    document.getElementById('edit-modal').style.display = 'none';
  }
}

async function saveEdit() {
  const id    = document.getElementById('edit-id').value;
  const date  = document.getElementById('edit-date').value;
  const value = document.getElementById('edit-value').value;
  const memo  = document.getElementById('edit-memo').value.trim();

  try {
    await apiFetch(`/api/data/${id}`, {
      method: 'PUT',
      body: JSON.stringify({ date, value: parseInt(value), memo }),
    });
    showToast('수정되었습니다!', 'success');
    closeEditModal();
    loadData();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

async function deleteData(id) {
  if (!confirm('이 데이터를 삭제할까요?')) return;
  try {
    await apiFetch(`/api/data/${id}`, { method: 'DELETE' });
    showToast('삭제되었습니다.', 'success');
    document.getElementById(`row-${id}`)?.remove();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

// ── 내보내기 (보너스) ─────────────────────────────────────────
async function exportData(format) {
  try {
    const res = await fetch(`${API_BASE_URL}/api/data/export?format=${format}`);
    if (!res.ok) throw new Error('내보내기 실패');
    const blob = await res.blob();
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement('a');
    a.href     = url;
    a.download = `subway_data.${format}`;
    a.click();
    URL.revokeObjectURL(url);
    showToast(`${format.toUpperCase()} 다운로드 시작!`, 'success');
  } catch (err) {
    showToast(err.message, 'error');
  }
}

// ════════════════════════════════════════════════════════════════
// ③ 대화 기록
// ════════════════════════════════════════════════════════════════

async function loadConversations() {
  const container = document.getElementById('conv-list-container');
  container.innerHTML = '<div style="color:var(--text-muted); font-size:0.85rem">로딩 중...</div>';
  try {
    const convs = await apiFetch('/api/conversations');
    if (!convs.length) {
      container.innerHTML = '<div class="empty-state" style="padding:20px 0"><div class="empty-icon">💬</div><div>저장된 대화가 없습니다</div></div>';
      return;
    }
    container.innerHTML = convs.map(c => `
      <div class="conv-item" id="conv-item-${c.id}" onclick="loadConversation('${c.id}')">
        <div>
          <div class="conv-title">${escapeHtml(c.title)}</div>
          <div class="conv-date">${formatDate(c.created_at)}</div>
        </div>
        <button class="btn btn-danger btn-sm" style="flex-shrink:0" onclick="deleteConv(event,'${c.id}')">🗑️</button>
      </div>
    `).join('');
  } catch (err) {
    container.innerHTML = `<div style="color:var(--danger); font-size:0.85rem">${err.message}</div>`;
  }
}

async function loadConversation(id) {
  // 선택 표시
  document.querySelectorAll('.conv-item').forEach(el => el.classList.remove('selected'));
  document.getElementById(`conv-item-${id}`)?.classList.add('selected');

  const viewer = document.getElementById('conv-viewer');
  viewer.innerHTML = '<div style="text-align:center; color:var(--text-muted)">불러오는 중...</div>';

  try {
    const conv = await apiFetch(`/api/conversations/${id}`);
    viewer.innerHTML = `
      <div style="font-weight:700; font-size:1rem; margin-bottom:8px">${escapeHtml(conv.title)}</div>
      <div style="font-size:0.8rem; color:var(--text-muted); margin-bottom:16px">${formatDate(conv.created_at)}</div>
      ${conv.messages.map(m => `
        <div class="msg ${m.role}" style="margin-bottom:8px">
          <div class="msg-avatar">${m.role === 'user' ? '👤' : '🤖'}</div>
          <div class="msg-body">
            <div class="msg-bubble">${escapeHtml(m.content).replace(/\n/g, '<br>')}</div>
          </div>
        </div>
      `).join('')}
    `;
  } catch (err) {
    viewer.innerHTML = `<div style="color:var(--danger)">${err.message}</div>`;
  }
}

async function deleteConv(e, id) {
  e.stopPropagation();
  if (!confirm('이 대화를 삭제할까요?')) return;
  try {
    await apiFetch(`/api/conversations/${id}`, { method: 'DELETE' });
    showToast('삭제되었습니다.', 'success');
    loadConversations();
    document.getElementById('conv-viewer').innerHTML = `
      <div class="conv-empty"><div>💬</div><div style="font-size:1rem">대화를 선택하면 내용이 표시됩니다</div></div>
    `;
  } catch (err) {
    showToast(err.message, 'error');
  }
}

// ════════════════════════════════════════════════════════════════
// ④ 통계/시각화 (보너스)
// ════════════════════════════════════════════════════════════════

async function loadStats() {
  const grid = document.getElementById('stats-summary-grid');
  const trendContainer = document.querySelector('#trend-chart')?.parentElement;
  const lineContainer = document.querySelector('#line-chart')?.parentElement;
  const weekdayContainer = document.querySelector('#weekday-chart')?.parentElement;

  // 1) 스켈레톤 로딩 UI 표시
  if (grid) {
    grid.innerHTML = Array(6).fill(0).map(() => `
      <div class="stat-card" style="opacity:0.65">
        <div class="stat-label">데이터 분석 중</div>
        <div class="stat-value" style="font-size:1.2rem">로딩 중...</div>
      </div>
    `).join('');
  }

  const showChartLoading = (container, text) => {
    if (!container) return;
    container.style.position = 'relative';
    let overlay = container.querySelector('.chart-loading-overlay');
    if (!overlay) {
      overlay = document.createElement('div');
      overlay.className = 'chart-loading-overlay';
      overlay.style.cssText = 'position:absolute; inset:0; background:rgba(0,0,0,0.15); display:flex; align-items:center; justify-content:center; border-radius:6px; font-size:13px; color:var(--text-muted); z-index:10; backdrop-filter:blur(2px);';
      container.appendChild(overlay);
    }
    overlay.innerHTML = `<span style="display:inline-block; animation:spin 1s linear infinite; margin-right:8px;">⏳</span> ${text}`;
  };

  const removeChartLoading = (container) => {
    const overlay = container?.querySelector('.chart-loading-overlay');
    if (overlay) overlay.remove();
  };

  showChartLoading(trendContainer, '월별 추이 데이터를 분석 중입니다...');
  showChartLoading(lineContainer, '노선별 데이터 집계 중...');
  showChartLoading(weekdayContainer, '요일별 데이터 집계 중...');

  try {
    // 2) 요약 및 통계 독립적 병렬 호출 (하나가 실패해도 다른 하나는 렌더링)
    const [summaryRes, statsRes] = await Promise.allSettled([
      apiFetch('/api/data/summary'),
      apiFetch('/api/data/statistics'),
    ]);

    // 요약 그리드 렌더링
    if (summaryRes.status === 'fulfilled' && summaryRes.value) {
      renderStatsSummaryGrid(summaryRes.value);
    } else {
      if (grid) grid.innerHTML = `<div class="stat-card" style="grid-column: 1 / -1; color:var(--danger)">⚠️ 요약 지표를 불러오지 못했습니다.</div>`;
    }

    // 차트 라이브러리 가용성 체크
    if (typeof Chart === 'undefined') {
      throw new Error('Chart.js 라이브러리를 불러오지 못했습니다. 네트워크 연결을 확인해주세요.');
    }

    // 통계 차트 렌더링
    if (statsRes.status === 'fulfilled' && statsRes.value) {
      const stats = statsRes.value;
      renderTrendChart(stats.by_month || {});
      renderLineChart(stats.by_line || {});
      renderWeekdayChart(stats.by_weekday || {});
    } else {
      const err = statsRes.reason?.message || '통계 API 오류';
      [trendContainer, lineContainer, weekdayContainer].forEach(c => {
        if (c) {
          c.innerHTML = `
            <div style="display:flex; flex-direction:column; align-items:center; justify-content:center; height:100%; color:var(--text-muted); gap:8px;">
              <div>⚠️ 통계 데이터를 불러오지 못했습니다 (${escapeHtml(err)})</div>
              <button class="btn btn-secondary btn-sm" onclick="loadStats()">🔄 다시 시도</button>
            </div>
          `;
        }
      });
    }
  } catch (err) {
    showToast('통계 로딩 실패: ' + err.message, 'error');
    console.error('loadStats error:', err);
  } finally {
    removeChartLoading(trendContainer);
    removeChartLoading(lineContainer);
    removeChartLoading(weekdayContainer);
  }
}

function renderStatsSummaryGrid(s) {
  const grid = document.getElementById('stats-summary-grid');
  if (!grid || !s) return;

  const trendStr = s.trend || '데이터 없음';
  const trendClass = trendStr.includes('상승') ? 'badge-up' : trendStr.includes('하락') ? 'badge-down' : 'badge-flat';
  const avg = s.metrics?.average ?? 0;
  const mx = s.metrics?.max ?? 0;
  const mn = s.metrics?.min ?? 0;

  grid.innerHTML = `
    <div class="stat-card">
      <div class="stat-label">데이터 기간</div>
      <div class="stat-value" style="font-size:1rem">${escapeHtml(s.period || '-')}</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">총 레코드</div>
      <div class="stat-value">${fmt(s.count || 0)}</div>
      <div class="stat-sub">건</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">일평균 승하차</div>
      <div class="stat-value">${fmt(avg)}</div>
      <div class="stat-sub">명</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">최고 기록</div>
      <div class="stat-value" style="color:var(--success)">${fmt(mx)}</div>
      <div class="stat-sub">명</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">최저 기록</div>
      <div class="stat-value" style="color:var(--danger)">${fmt(mn)}</div>
      <div class="stat-sub">명</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">최근 트렌드</div>
      <div class="stat-value" style="font-size:1rem"><span class="badge ${trendClass}">${escapeHtml(trendStr)}</span></div>
    </div>
  `;
}

function getChartDefaults() {
  const isDark = document.documentElement.dataset.theme !== 'light';
  return {
    textColor: isDark ? '#a0a8c0' : '#4a4e6a',
    gridColor: isDark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.06)',
  };
}

function renderTrendChart(byMonth) {
  const canvas = document.getElementById('trend-chart');
  if (!canvas) return;
  const { textColor, gridColor } = getChartDefaults();
  const labels = Object.keys(byMonth || {});
  const values = Object.values(byMonth || {});

  if (chartTrend) {
    try { chartTrend.destroy(); } catch (e) {}
  }
  chartTrend = new Chart(canvas, {
    type: 'line',
    data: {
      labels,
      datasets: [{
        label: '월평균 승하차 (명)',
        data: values,
        borderColor: '#6c63ff',
        backgroundColor: 'rgba(108,99,255,0.1)',
        fill: true,
        tension: 0.4,
        pointBackgroundColor: '#00d9ff',
        pointRadius: 4,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { labels: { color: textColor } } },
      scales: {
        x: { ticks: { color: textColor }, grid: { color: gridColor } },
        y: { ticks: { color: textColor, callback: v => fmt(v) }, grid: { color: gridColor } },
      },
    },
  });
}

function renderLineChart(byLine) {
  const canvas = document.getElementById('line-chart');
  if (!canvas) return;
  const { textColor, gridColor } = getChartDefaults();
  const labels = Object.keys(byLine || {}).slice(0, 8);
  const values = labels.map(k => byLine[k]);
  const colors = ['#6c63ff','#00d9ff','#ff6b9d','#4ade80','#facc15','#fb923c','#a78bfa','#34d399'];

  if (chartLine) {
    try { chartLine.destroy(); } catch (e) {}
  }
  chartLine = new Chart(canvas, {
    type: 'bar',
    data: {
      labels,
      datasets: [{
        label: '노선별 평균 (명)',
        data: values,
        backgroundColor: colors,
        borderRadius: 6,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { color: textColor, maxRotation: 45 }, grid: { display: false } },
        y: { ticks: { color: textColor, callback: v => fmt(v) }, grid: { color: gridColor } },
      },
    },
  });
}

function renderWeekdayChart(byWeekday) {
  const canvas = document.getElementById('weekday-chart');
  if (!canvas) return;
  const { textColor, gridColor } = getChartDefaults();
  const labels = Object.keys(byWeekday || {});
  const values = Object.values(byWeekday || {});

  if (chartWeekday) {
    try { chartWeekday.destroy(); } catch (e) {}
  }
  chartWeekday = new Chart(canvas, {
    type: 'radar',
    data: {
      labels,
      datasets: [{
        label: '요일별 평균 (명)',
        data: values,
        borderColor: '#ff6b9d',
        backgroundColor: 'rgba(255,107,157,0.15)',
        pointBackgroundColor: '#ff6b9d',
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { labels: { color: textColor } } },
      scales: {
        r: {
          ticks: { color: textColor, backdropColor: 'transparent', callback: v => fmt(v) },
          grid: { color: gridColor },
          pointLabels: { color: textColor },
        },
      },
    },
  });
}

// ── 유틸리티 ──────────────────────────────────────────────────
function escapeHtml(str) {
  return String(str ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function formatDate(iso) {
  if (!iso) return '';
  try {
    return new Date(iso).toLocaleString('ko-KR', {
      year: 'numeric', month: '2-digit', day: '2-digit',
      hour: '2-digit', minute: '2-digit',
    });
  } catch { return iso; }
}

// ── 공공데이터 동기화 ─────────────────────────────────────────
function initSyncMonth() {
  const input = document.getElementById('sync-month');
  if (!input) return;
  // 서울 열린데이터광장 최신 집계월 기본값 (2026년 7월)
  input.value = '2026-07';
}

async function syncPublicData() {
  const monthInput = document.getElementById('sync-month');
  const syncBtn    = document.getElementById('sync-btn');
  const resultEl   = document.getElementById('sync-result');

  const targetMonth = monthInput?.value || '';  // 'YYYY-MM'

  // 버튼 로딩 상태
  syncBtn.disabled = true;
  const originalHTML = syncBtn.innerHTML;
  syncBtn.innerHTML = `
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="15" height="15"
         style="animation:spin 1s linear infinite">
      <path d="M23 4v6h-6"/><path d="M1 20v-6h6"/>
      <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/>
    </svg> 동기화 중...`;

  resultEl.style.display = 'none';

  try {
    const query = targetMonth ? `?target_date=${targetMonth.replace('-', '')}` : '';
    const data = await apiFetch(`/api/data/sync-public${query}`, { method: 'POST' });

    resultEl.style.display = 'block';
    const isSuccess = data.inserted > 0;
    resultEl.className = `sync-result ${isSuccess ? 'sync-success' : 'sync-info'}`;
    resultEl.innerHTML = `
      <strong>${isSuccess ? '✅' : 'ℹ️'} ${data.message}</strong>
      <div style="margin-top:6px; font-size:13px; opacity:0.8">
        대상 연월: <strong>${data.target_ym}</strong>
        &nbsp;|&nbsp; 추가: <strong>${data.inserted}건</strong>
        &nbsp;|&nbsp; 스킵(중복): <strong>${data.skipped}건</strong>
      </div>
    `;

    if (data.inserted > 0) {
      showToast(`✅ ${data.inserted}건 공공데이터 추가 완료`, 'success');
      loadData();   // 목록 새로고침
      loadSummary(); // 요약 새로고침
    } else {
      showToast('ℹ️ 추가된 데이터가 없습니다 (모두 중복)', 'info');
    }
  } catch (err) {
    resultEl.style.display = 'block';
    resultEl.className = 'sync-result sync-error';
    resultEl.innerHTML = `
      <strong>❌ 동기화 실패</strong>
      <div style="margin-top:6px; font-size:13px; opacity:0.85">${escapeHtml(err.message)}</div>
      <div style="margin-top:6px; font-size:12px; opacity:0.65">
        SEOUL_API_KEY 환경변수가 설정되어 있는지 확인하세요.
        (<a href="https://data.seoul.go.kr" target="_blank" style="color:inherit">data.seoul.go.kr</a>에서 무료 발급)
      </div>
    `;
    showToast('❌ 공공데이터 동기화 실패', 'error');
  } finally {
    syncBtn.disabled = false;
    syncBtn.innerHTML = originalHTML;
  }
}

// ── 초기화 ────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  initSyncMonth();
});

const statusEl = document.getElementById('status');
const activeDurationEl = document.getElementById('activeDuration');
const appCountEl = document.getElementById('appCount');
const avgSwitchRateEl = document.getElementById('avgSwitchRate');
const timeRangeEl = document.getElementById('timeRange');
const appListEl = document.getElementById('appList');
const inputTableEl = document.getElementById('inputTable');
const inputSummaryEl = document.getElementById('inputSummary');
const inputTrendEl = document.getElementById('inputTrend');
const hourlyChartEl = document.getElementById('hourlyChart');
const hourlyYAxisEl = document.getElementById('hourlyYAxis');
const hourlyXAxisEl = document.getElementById('hourlyXAxis');
const hourlyTooltipEl = document.getElementById('hourlyTooltip');
const visualRangeHintEl = document.getElementById('visualRangeHint');
const donutChartEl = document.getElementById('donutChart');
const donutTotalEl = document.getElementById('donutTotal');
const refreshBtn = document.getElementById('refreshBtn');
const reportBtn = document.getElementById('reportBtn');
const rangeSelect = document.getElementById('rangeSelect');

const FALLBACK_COLORS = ['#60a5fa', '#34d399', '#fbbf24', '#a78bfa', '#f9a8d4', '#67e8f9', '#86efac', '#fdba74'];
const KEY_HOURS = new Set([0, 4, 8, 12, 16, 20, 24]);

const appState = {
  activeHour: null,
  colorMap: new Map(),
  visualization: null,
  loadToken: 0,
  bridgeReadyPromise: null
};

function formatDuration(seconds) {
  if (!seconds || seconds <= 0) return '-';
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  if (hours <= 0) return `${minutes}m`;
  return `${hours}h ${minutes}m`;
}

function formatPreciseDuration(seconds) {
  if (!seconds || seconds <= 0) return '0m';
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const remainSeconds = Math.round(seconds % 60);
  if (hours > 0) return `${hours}h ${minutes}m`;
  if (minutes > 0) return `${minutes}m ${remainSeconds}s`;
  return `${remainSeconds}s`;
}

function formatHour(hour) {
  return `${hour.toString().padStart(2, '0')}:00`;
}

function formatMinutes(seconds) {
  return `${Math.round((seconds || 0) / 60)}m`;
}

function formatNumber(value) {
  return new Intl.NumberFormat('zh-CN').format(Math.round(value || 0));
}

function formatRate(value) {
  if (!value) return '0 / 小时';
  return `${Math.round(value)} / 小时`;
}

function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

function setColorMap(colorMap = {}) {
  appState.colorMap = new Map(Object.entries(colorMap));
}

function getColor(key) {
  if (appState.colorMap.has(key)) {
    return appState.colorMap.get(key);
  }
  let hash = 0;
  for (let i = 0; i < key.length; i += 1) {
    hash = (hash + key.charCodeAt(i) * 31) % FALLBACK_COLORS.length;
  }
  const color = FALLBACK_COLORS[hash];
  appState.colorMap.set(key, color);
  return color;
}

function setActiveHour(hour) {
  appState.activeHour = Number.isInteger(hour) ? hour : null;
}

function onHourSelect(hour) {
  setActiveHour(hour);
  renderVisualizations(appState.visualization);
}

function buildTooltipContent(item) {
  const topSegments = (item.segments || []).slice(0, 5);
  if (!topSegments.length) {
    return `
      <div class="tooltip-header">
        <span class="tooltip-hour">${formatHour(item.hour)}</span>
        <span class="tooltip-total">总活跃 0m</span>
      </div>
      <div class="tooltip-list">
        <div class="tooltip-item"><span class="tooltip-name">暂无活跃应用</span></div>
      </div>
    `;
  }

  return `
    <div class="tooltip-header">
      <span class="tooltip-hour">${formatHour(item.hour)}</span>
      <span class="tooltip-total">总活跃 ${formatMinutes(item.total)}</span>
    </div>
    <div class="tooltip-list">
      ${topSegments.map(segment => `
        <div class="tooltip-item">
          <span class="tooltip-swatch" style="background:${segment.color || getColor(segment.app)}"></span>
          <span class="tooltip-name">${escapeHtml(segment.app)}</span>
          <span class="tooltip-value">${formatPreciseDuration(segment.duration)}</span>
        </div>
      `).join('')}
    </div>
  `;
}

function showHourlyTooltip(item) {
  if (!hourlyTooltipEl) return;
  hourlyTooltipEl.innerHTML = buildTooltipContent(item);
  hourlyTooltipEl.hidden = false;
}

function hideHourlyTooltip() {
  if (!hourlyTooltipEl) return;
  hourlyTooltipEl.hidden = true;
  hourlyTooltipEl.innerHTML = '';
}

function renderApps(items) {
  appListEl.innerHTML = '';
  if (!items.length) {
    const li = document.createElement('li');
    li.className = 'app-summary-item empty';
    li.textContent = '暂无数据';
    appListEl.appendChild(li);
    return;
  }

  items.forEach(item => {
    const li = document.createElement('li');
    li.className = 'app-summary-item';
    const label = item.display_name || item.app;
    const metaName = item.display_name && item.display_name !== item.app ? item.app : '';
    li.innerHTML = `
      <span class="app-summary-swatch" style="background:${getColor(item.app)}"></span>
      <div class="app-summary-main">
        <div class="app-summary-topline">
          <span class="app-summary-name">${escapeHtml(label)}</span>
          <span class="app-summary-duration">${formatDuration(item.duration)}</span>
        </div>
        <div class="app-summary-subline">
          ${metaName ? `<span class="app-summary-process">${escapeHtml(metaName)}</span>` : ''}
          <span class="app-summary-metrics">键盘 ${formatNumber(item.presses || 0)} / 点击 ${formatNumber(item.clicks || 0)} / 滚轮 ${formatNumber(item.scroll || 0)}</span>
        </div>
      </div>
    `;
    appListEl.appendChild(li);
  });
}

function createMetricBlock(label, value, maxValue, accentClass = '') {
  const wrapper = document.createElement('div');
  wrapper.className = `input-metric-block ${accentClass}`.trim();
  const ratio = maxValue > 0 ? value / maxValue : 0;
  const width = value > 0 ? Math.max(ratio * 100, 10) : 0;
  wrapper.innerHTML = `
    <div class="input-metric-header">
      <span>${label}</span>
      <span>${formatNumber(value)}</span>
    </div>
    <div class="input-metric-track">
      <span class="input-metric-fill" style="width:${width}%"></span>
    </div>
  `;
  return wrapper;
}

function renderInputSummary(inputSummary) {
  if (!inputSummaryEl) return;
  inputSummaryEl.innerHTML = '';

  if (!inputSummary?.available) {
    inputSummaryEl.innerHTML = '<div class="input-summary-card empty-state">暂无输入数据桶</div>';
    return;
  }

  const totals = inputSummary.totals || {};
  const cards = [
    { label: '键盘敲击', value: formatNumber(totals.presses), meta: '按键总次数' },
    { label: '鼠标点击', value: formatNumber(totals.clicks), meta: '左键/右键聚合' },
    { label: '滚轮滚动', value: formatNumber(totals.scroll), meta: 'scrollX + scrollY' },
    { label: '鼠标移动', value: formatNumber(totals.moves), meta: 'deltaX + deltaY' },
    { label: '平均速率', value: formatRate(inputSummary.averagePerHour), meta: '每小时输入总量' },
    { label: '峰值时段', value: inputSummary.peakHour ? formatHour(inputSummary.peakHour.hour) : '-', meta: inputSummary.peakHour ? `${formatNumber(inputSummary.peakHour.total)} 次输入` : '暂无峰值' }
  ];

  cards.forEach(card => {
    const item = document.createElement('div');
    item.className = 'input-summary-card';
    item.innerHTML = `
      <span class="input-summary-label">${card.label}</span>
      <strong class="input-summary-value">${card.value}</strong>
      <span class="input-summary-meta">${card.meta}</span>
    `;
    inputSummaryEl.appendChild(item);
  });
}

function renderInputTrend(items) {
  if (!inputTrendEl) return;
  inputTrendEl.innerHTML = '';

  if (!items?.length) {
    inputTrendEl.innerHTML = '<div class="input-empty">暂无数据</div>';
    return;
  }

  const maxTotal = Math.max(...items.map(item => item.total || 0), 0);
  items.forEach(item => {
    const bar = document.createElement('div');
    bar.className = 'input-trend-bar';
    const height = maxTotal > 0 ? Math.max((item.total / maxTotal) * 100, item.total > 0 ? 14 : 8) : 8;
    bar.innerHTML = `
      <div class="input-trend-stack" style="height:${height}%">
        <span class="input-trend-segment presses" style="height:${item.total > 0 ? (item.presses / item.total) * 100 : 0}%"></span>
        <span class="input-trend-segment clicks" style="height:${item.total > 0 ? (item.clicks / item.total) * 100 : 0}%"></span>
        <span class="input-trend-segment scroll" style="height:${item.total > 0 ? (item.scroll / item.total) * 100 : 0}%"></span>
      </div>
      <span class="input-trend-label">${String(item.hour).padStart(2, '0')}</span>
    `;
    inputTrendEl.appendChild(bar);
  });
}

function renderInputTable(items) {
  inputTableEl.innerHTML = '';

  if (!items.length) {
    const empty = document.createElement('div');
    empty.className = 'input-empty';
    empty.textContent = '暂无数据';
    inputTableEl.appendChild(empty);
    return;
  }

  const maxPresses = Math.max(...items.map(item => item.presses || 0), 0);
  const maxClicks = Math.max(...items.map(item => item.clicks || 0), 0);
  const maxScroll = Math.max(...items.map(item => item.scroll || 0), 0);
  const maxMoves = Math.max(...items.map(item => item.moves || 0), 0);

  items.forEach(item => {
    const row = document.createElement('div');
    row.className = 'input-bar-row';

    const app = document.createElement('div');
    app.className = 'input-bar-app';
    app.innerHTML = `
      <span class="input-app-swatch" style="background:${getColor(item.app)}"></span>
      <span>${escapeHtml(item.display_name || item.app)}</span>
    `;

    const metrics = document.createElement('div');
    metrics.className = 'input-bar-metrics';
    metrics.appendChild(createMetricBlock('键盘', item.presses || 0, maxPresses, 'presses'));
    metrics.appendChild(createMetricBlock('点击', item.clicks || 0, maxClicks, 'clicks'));
    metrics.appendChild(createMetricBlock('滚轮', item.scroll || 0, maxScroll, 'scroll'));
    metrics.appendChild(createMetricBlock('移动', item.moves || 0, maxMoves, 'moves'));

    row.appendChild(app);
    row.appendChild(metrics);
    inputTableEl.appendChild(row);
  });
}

function buildDonutSegments(items) {
  const total = items.reduce((sum, item) => sum + (item.duration || 0), 0);
  if (!total) return [];

  let current = 0;
  return items.map(item => {
    const value = item.duration || 0;
    const start = current;
    const ratio = value / total;
    current += ratio * 360;
    return {
      ...item,
      start,
      end: current,
      ratio,
      color: getColor(item.app)
    };
  });
}

function renderDonut(items) {
  donutTotalEl.textContent = '-';
  donutChartEl.style.background = 'conic-gradient(#dbe6ff 0deg 360deg)';

  if (!items.length) {
    return;
  }

  const segments = buildDonutSegments(items);
  const total = items.reduce((sum, item) => sum + (item.duration || 0), 0);
  donutTotalEl.textContent = formatDuration(total);
  donutChartEl.style.background = `conic-gradient(${segments.map(segment => `${segment.color} ${segment.start}deg ${segment.end}deg`).join(', ')})`;
}

function renderYAxis(maxDuration) {
  if (!hourlyYAxisEl) return;
  hourlyYAxisEl.innerHTML = '';
  const ticks = [0, 0.25, 0.5, 0.75, 1].map(ratio => Math.round((maxDuration * ratio) / 60));
  ticks.reverse().forEach(value => {
    const tick = document.createElement('span');
    tick.textContent = `${value}`;
    hourlyYAxisEl.appendChild(tick);
  });
}

function renderXAxis() {
  if (!hourlyXAxisEl) return;
  hourlyXAxisEl.innerHTML = '';
  Array.from({ length: 25 }, (_, hour) => hour).forEach(hour => {
    const tick = document.createElement('span');
    tick.textContent = KEY_HOURS.has(hour) ? String(hour).padStart(2, '0') : '';
    if (KEY_HOURS.has(hour)) tick.classList.add('major');
    hourlyXAxisEl.appendChild(tick);
  });
}

function renderHourlyChart(hourlyBars) {
  hourlyChartEl.innerHTML = '';
  hideHourlyTooltip();
  renderXAxis();
  if (!hourlyBars?.length) {
    renderYAxis(0);
    return;
  }

  const maxDuration = Math.max(...hourlyBars.map(item => item.total || 0), 0);
  renderYAxis(maxDuration);

  hourlyBars.forEach(item => {
    const barDiv = document.createElement('div');
    barDiv.className = 'hour-bar';
    barDiv.dataset.hour = String(item.hour);
    barDiv.tabIndex = 0;
    if (appState.activeHour === item.hour) barDiv.classList.add('selected');

    const segmentsDiv = document.createElement('div');
    segmentsDiv.className = 'bar-segments';
    const barHeight = maxDuration > 0 ? Math.max((item.total / maxDuration) * 250, item.total > 0 ? 12 : 8) : 8;
    segmentsDiv.style.height = `${barHeight}px`;

    (item.segments || []).forEach(segment => {
      const segmentEl = document.createElement('div');
      segmentEl.className = 'bar-segment';
      const segmentHeight = item.total > 0 ? Math.max((segment.duration / item.total) * barHeight, 4) : 4;
      segmentEl.style.height = `${segmentHeight}px`;
      segmentEl.style.background = segment.color || getColor(segment.app);
      segmentsDiv.appendChild(segmentEl);
    });

    const label = document.createElement('div');
    label.className = 'hour-label';
    label.textContent = item.hour.toString().padStart(2, '0');

    barDiv.appendChild(segmentsDiv);
    barDiv.appendChild(label);
    barDiv.addEventListener('click', () => onHourSelect(item.hour));
    barDiv.addEventListener('mouseenter', () => showHourlyTooltip(item));
    barDiv.addEventListener('focus', () => showHourlyTooltip(item));
    barDiv.addEventListener('mouseleave', hideHourlyTooltip);
    barDiv.addEventListener('blur', hideHourlyTooltip);

    hourlyChartEl.appendChild(barDiv);
  });
}

function renderVisualizations(visualization) {
  appState.visualization = visualization;
  const hourlyBars = visualization?.hourlyBars || [];
  const meta = visualization?.meta || {};

  renderHourlyChart(hourlyBars);

  if (visualRangeHintEl) {
    if (meta.rangeStart && meta.rangeEnd) {
      const daysLabel = meta.days > 1 ? ` · ${meta.days} 天投影` : '';
      visualRangeHintEl.textContent = `${meta.rangeStart.slice(0, 10)} → ${meta.rangeEnd.slice(0, 10)}${daysLabel}`;
    } else {
      visualRangeHintEl.textContent = '';
    }
  }
}

function calculateAverageSwitchRate(appEvents, durationSeconds) {
  if (!appEvents?.length || !durationSeconds) return '-';
  const hours = durationSeconds / 3600;
  if (!hours) return '-';
  return `${(appEvents.length / hours).toFixed(1)} 次/小时`;
}

function clearDashboard() {
  activeDurationEl.textContent = '-';
  appCountEl.textContent = '-';
  avgSwitchRateEl.textContent = '-';
  timeRangeEl.textContent = '-';
  renderApps([]);
  renderDonut([]);
  renderInputSummary(null);
  renderInputTrend([]);
  renderInputTable([]);
  renderVisualizations(null);
}

function setDashboardFromPayload(payload) {
  const summary = payload.summary || {};
  const result = summary.result || {};
  const duration = result?.window?.duration || 0;
  const appEvents = result?.window?.app_events || [];
  const visualization = payload.visualization || null;

  activeDurationEl.textContent = formatDuration(duration);
  appCountEl.textContent = appEvents.length.toString();
  avgSwitchRateEl.textContent = calculateAverageSwitchRate(appEvents, duration);

  const range = summary.time_range || {};
  if (range.start && range.end) {
    timeRangeEl.textContent = `${range.start.slice(0, 10)} → ${range.end.slice(0, 10)}`;
  } else {
    timeRangeEl.textContent = '-';
  }

  setColorMap(visualization?.colorMap || {});

  const activity = payload.activity || [];
  renderApps(activity);
  renderDonut(activity);
  renderInputSummary(payload.inputSummary || null);
  renderInputTrend(payload.inputTrend || []);
  renderInputTable(payload.inputByApp || payload.inputTopApps || []);

  setActiveHour(visualization?.activeHour ?? null);
  renderVisualizations(visualization);
}

function getErrorMessage(payload) {
  const code = payload?.error?.code;
  if (code === 'bridge_not_ready') return '前端桥接尚未就绪';
  if (code === 'missing_buckets') return '缺少数据桶';
  if (code === 'query_failed') return '查询数据失败';
  return '加载失败';
}

function waitForPywebviewApi(timeoutMs = 8000) {
  if (window.pywebview?.api) {
    return Promise.resolve(window.pywebview.api);
  }
  if (appState.bridgeReadyPromise) {
    return appState.bridgeReadyPromise;
  }

  appState.bridgeReadyPromise = new Promise((resolve, reject) => {
    const startedAt = Date.now();

    const check = () => {
      if (window.pywebview?.api) {
        appState.bridgeReadyPromise = null;
        resolve(window.pywebview.api);
        return;
      }
      if (Date.now() - startedAt >= timeoutMs) {
        appState.bridgeReadyPromise = null;
        reject(new Error('pywebview bridge not ready'));
        return;
      }
      window.setTimeout(check, 100);
    };

    check();
  });

  return appState.bridgeReadyPromise;
}

async function loadDashboardPayload(days) {
  const api = await waitForPywebviewApi();
  return api.get_dashboard_data(days, 12, 0, 6);
}

async function generateReport() {
  statusEl.textContent = '生成报告中...';
  try {
    const api = await waitForPywebviewApi();
    const path = await api.generate_report_today();
    if (path) {
      statusEl.textContent = '报告已生成';
      alert(`今日报告已生成并保存至:\n${path}`);
    } else {
      statusEl.textContent = '生成失败';
      alert('报告生成失败，请检查数据是否完整。');
    }
  } catch (err) {
    statusEl.textContent = '生成失败';
    console.error(err);
  }
}

async function loadData() {
  const token = ++appState.loadToken;
  const days = Number(rangeSelect.value || 1);
  statusEl.textContent = '加载中';
  refreshBtn.disabled = true;

  try {
    const payload = await loadDashboardPayload(days);
    if (token !== appState.loadToken) return;

    if (!payload?.ok) {
      clearDashboard();
      statusEl.textContent = getErrorMessage(payload);
      return;
    }

    setDashboardFromPayload(payload);
    statusEl.textContent = payload.warnings?.length ? payload.warnings[0] : '已更新';
  } catch (err) {
    if (token !== appState.loadToken) return;
    clearDashboard();
    statusEl.textContent = err?.message === 'pywebview bridge not ready'
      ? '前端桥接尚未就绪'
      : '加载失败';
    console.error(err);
  } finally {
    if (token === appState.loadToken) {
      refreshBtn.disabled = false;
    }
  }
}

refreshBtn.addEventListener('click', () => loadData());
reportBtn.addEventListener('click', () => generateReport());
rangeSelect.addEventListener('change', () => loadData());

window.onHourSelect = onHourSelect;

window.addEventListener('DOMContentLoaded', async () => {
  try {
    await waitForPywebviewApi();
  } catch (err) {
    clearDashboard();
    statusEl.textContent = '前端桥接尚未就绪';
    console.error(err);
    return;
  }
  loadData();
});

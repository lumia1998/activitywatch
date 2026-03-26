const {
  formatDuration,
  formatPreciseDuration,
  formatHour,
  formatMinutes,
  formatNumber,
  formatRate
} = window.AwUiFormatters;
const { escapeHtml } = window.AwUiHtml;
const { createColorHelpers } = window.AwUiColors;
const {
  renderYAxisFor,
  renderXAxisFor,
  buildTooltipContent,
  showTooltip,
  hideTooltip,
  createHourlyStackedBarChartRenderer
} = window.AwUiCharts;
const { renderInputSummary: renderInputSummaryGrid } = window.AwUiRenderers;

const KEY_HOURS = new Set([0, 4, 8, 12, 16, 20, 24]);

function syncXAxisTickLabel(tick, hour) {
  tick.textContent = KEY_HOURS.has(hour) ? String(hour).padStart(2, '0') : '';
  return tick;
}

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
const browserSummaryEl = document.getElementById('browserSummary');
const browserDomainListEl = document.getElementById('browserDomainList');
const browserDonutChartEl = document.getElementById('browserDonutChart');
const browserDonutTotalEl = document.getElementById('browserDonutTotal');
const browserTrendChartEl = document.getElementById('browserTrendChart');
const browserTrendYAxisEl = document.getElementById('browserTrendYAxis');
const browserTrendXAxisEl = document.getElementById('browserTrendXAxis');
const browserTrendTooltipEl = document.getElementById('browserTrendTooltip');
const browserTrendHintEl = document.getElementById('browserTrendHint');
const settingsModalEl = document.getElementById('settingsModal');
const settingsCloseBtn = document.getElementById('settingsCloseBtn');
const excludedAppInputEl = document.getElementById('excludedAppInput');
const addExcludedAppBtn = document.getElementById('addExcludedAppBtn');
const excludedAppsListEl = document.getElementById('excludedAppsList');
const aliasEditorSectionEl = document.getElementById('aliasEditorSection');
const aliasAppInputEl = document.getElementById('aliasAppInput');
const aliasNameInputEl = document.getElementById('aliasNameInput');
const addAliasBtn = document.getElementById('addAliasBtn');
const aliasListEl = document.getElementById('aliasList');
const detectedAppsListEl = document.getElementById('detectedAppsList');
const settingsSaveBtn = document.getElementById('settingsSaveBtn');
const themeToggleBtn = document.getElementById('themeToggle');
const dashboardTabEls = Array.from(document.querySelectorAll('.dashboard-tab'));
const dashboardPanelEls = Array.from(document.querySelectorAll('.dashboard-panel'));

const THEME_STORAGE_KEY = 'aw-pywebview-theme';
const DEFAULT_THEME = 'light';

const appState = {
  activeHour: null,
  browserActiveHour: null,
  currentPanel: 'applications',
  colorMap: new Map(),
  visualization: null,
  loadToken: 0,
  bridgeReadyPromise: null,
  theme: DEFAULT_THEME,
  settings: {
    excluded_apps: [],
    app_aliases: {}
  },
  detectedApps: [],
  editingDetectedAliasApp: ''
};

const { setColorMap, getColor } = createColorHelpers(appState);

function normalizeTheme(theme) {
  return theme === 'dark' ? 'dark' : DEFAULT_THEME;
}

function readStoredTheme() {
  try {
    return normalizeTheme(window.localStorage.getItem(THEME_STORAGE_KEY));
  } catch (_error) {
    return DEFAULT_THEME;
  }
}

function persistTheme(theme) {
  try {
    window.localStorage.setItem(THEME_STORAGE_KEY, theme);
  } catch (_error) {
    // ignore storage errors to avoid blocking dashboard loading
  }
}

function updateThemeToggle() {
  if (!themeToggleBtn) return;
  const isDark = appState.theme === 'dark';
  themeToggleBtn.setAttribute('aria-pressed', String(isDark));
  themeToggleBtn.setAttribute('aria-label', isDark ? '切换到浅色主题' : '切换到深色主题');
  themeToggleBtn.setAttribute('title', isDark ? '切换到浅色主题' : '切换到深色主题');
}

function applyTheme(theme, persist = false) {
  const nextTheme = normalizeTheme(theme);
  appState.theme = nextTheme;
  document.documentElement.dataset.theme = nextTheme;
  updateThemeToggle();
  if (persist) {
    persistTheme(nextTheme);
  }
}

function toggleTheme() {
  applyTheme(appState.theme === 'dark' ? 'light' : 'dark', true);
}

function initializeTheme() {
  const initialTheme = normalizeTheme(document.documentElement.dataset.theme || readStoredTheme());
  applyTheme(initialTheme);
}

function setActiveHour(hour) {
  appState.activeHour = Number.isInteger(hour) ? hour : null;
}

function onHourSelect(hour) {
  setActiveHour(hour);
  renderVisualizations(appState.visualization);
}

function showHourlyTooltip(item) {
  showTooltip(hourlyTooltipEl, item, {
    labelKey: 'app',
    emptyLabel: '暂无活跃应用',
    totalLabel: '总活跃',
    formatHour,
    formatMinutes,
    formatPreciseDuration,
    escapeHtml,
    getColor
  });
}

function hideHourlyTooltip() {
  hideTooltip(hourlyTooltipEl);
}

function showBrowserTrendTooltip(item) {
  showTooltip(browserTrendTooltipEl, item, {
    labelKey: 'domain',
    emptyLabel: '暂无网页浏览',
    totalLabel: '总浏览',
    formatHour,
    formatMinutes,
    formatPreciseDuration,
    escapeHtml,
    getColor
  });
}

function hideBrowserTrendTooltip() {
  hideTooltip(browserTrendTooltipEl);
}

const renderApplicationHourlyBars = createHourlyStackedBarChartRenderer({
  chartEl: hourlyChartEl,
  axisEl: hourlyYAxisEl,
  xAxisEl: hourlyXAxisEl,
  tooltipEl: hourlyTooltipEl,
  getSelectedHour: () => appState.activeHour,
  setSelectedHour: setActiveHour,
  onHourChange: () => renderVisualizations(appState.visualization),
  onShowTooltip: showHourlyTooltip,
  onHideTooltip: hideHourlyTooltip,
  getSegmentKey: segment => segment.app,
  getColor,
  xAxisOptions: {
    keyHours: KEY_HOURS,
    decorateTick: syncXAxisTickLabel
  }
});

const renderBrowserHourlyBars = createHourlyStackedBarChartRenderer({
  chartEl: browserTrendChartEl,
  axisEl: browserTrendYAxisEl,
  xAxisEl: browserTrendXAxisEl,
  tooltipEl: browserTrendTooltipEl,
  getSelectedHour: () => appState.browserActiveHour,
  setSelectedHour: hour => {
    appState.browserActiveHour = hour;
  },
  onHourChange: trend => renderBrowserTrend(trend),
  onShowTooltip: showBrowserTrendTooltip,
  onHideTooltip: hideBrowserTrendTooltip,
  getSegmentKey: segment => segment.domain,
  getColor,
  renderHint: trend => {
    if (!browserTrendHintEl) return;
    const meta = trend?.meta || {};
    const daysLabel = meta.days > 1 ? ` · ${meta.days} 天投影` : '';
    browserTrendHintEl.textContent = `24 小时网页浏览趋势${daysLabel}`;
  },
  renderEmptyHint: () => {
    if (browserTrendHintEl) {
      browserTrendHintEl.textContent = '24 小时网页浏览趋势';
    }
  }
});

function normalizeAliasLookupKey(value) {
  const normalized = String(value || '').trim().toLowerCase();
  return normalized.endsWith('.exe') ? normalized.slice(0, -4) : normalized;
}

function applyAliasToItem(item) {
  if (!item || typeof item !== 'object') return item;
  const aliasKey = normalizeAliasLookupKey(item.app);
  const aliasName = appState.settings.app_aliases?.[aliasKey];
  if (!aliasName) return item;
  return {
    ...item,
    display_name: aliasName
  };
}

function applyAliasesToItems(items) {
  return Array.isArray(items) ? items.map(applyAliasToItem) : [];
}

function renderApps(items) {
  appListEl.innerHTML = '';
  const aliasedItems = applyAliasesToItems(items);
  if (!aliasedItems.length) {
    const li = document.createElement('li');
    li.className = 'app-summary-item empty';
    li.textContent = '暂无数据';
    appListEl.appendChild(li);
    return;
  }

  aliasedItems.forEach(item => {
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

function buildSummaryCards(summary, cards) {
  return cards.map(card => `
    <div class="input-summary-card">
      <span class="input-summary-label">${card.label}</span>
      <strong class="input-summary-value">${card.value}</strong>
      <span class="input-summary-meta">${card.meta}</span>
    </div>
  `).join('');
}

function renderBrowserSummary(browserSummary) {
  if (!browserSummaryEl) return;
  if (!browserSummary?.available) {
    browserSummaryEl.innerHTML = '<div class="input-summary-card empty-state">暂无浏览器数据</div>';
    return;
  }

  const topDomain = browserSummary.topDomain;
  browserSummaryEl.innerHTML = buildSummaryCards(browserSummary, [
    {
      label: '浏览总时长',
      value: formatDuration(browserSummary.totalDuration),
      meta: '当前时间范围内网页前台停留时长'
    },
    {
      label: '活跃域名数',
      value: formatNumber(browserSummary.domainCount),
      meta: `覆盖 ${formatNumber(browserSummary.urlCount || 0)} 个 URL 聚合项`
    },
    {
      label: 'Top 域名',
      value: topDomain?.domain || '-',
      meta: topDomain ? `${formatDuration(topDomain.duration)} · ${(topDomain.share * 100).toFixed(1)}%` : '暂无主域名'
    }
  ]);
}

function renderBrowserList(items) {
  if (!browserDomainListEl) return;
  browserDomainListEl.innerHTML = '';
  if (!items?.length) {
    browserDomainListEl.innerHTML = '<li class="app-summary-item empty">暂无浏览器数据</li>';
    return;
  }

  items.forEach(item => {
    const li = document.createElement('li');
    li.className = 'app-summary-item';
    li.innerHTML = `
      <span class="app-summary-swatch" style="background:${getColor(item.domain)}"></span>
      <div class="app-summary-main">
        <div class="app-summary-topline">
          <span class="app-summary-name">${escapeHtml(item.domain)}</span>
          <span class="app-summary-duration">${formatDuration(item.duration)}</span>
        </div>
        <div class="app-summary-subline">
          <span class="app-summary-process">${formatNumber(item.urlCount || 0)} 个 URL</span>
          <span class="app-summary-metrics">占比 ${(item.share * 100).toFixed(1)}%</span>
        </div>
      </div>
    `;
    browserDomainListEl.appendChild(li);
  });
}

function buildDonutSegments(items, keyName) {
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
      color: getColor(item[keyName])
    };
  });
}

function renderDonut(items) {
  donutTotalEl.textContent = '-';
  donutChartEl.style.background = 'conic-gradient(var(--donut-empty) 0deg 360deg)';

  if (!items.length) {
    return;
  }

  const segments = buildDonutSegments(items, 'app');
  const total = items.reduce((sum, item) => sum + (item.duration || 0), 0);
  donutTotalEl.textContent = formatDuration(total);
  donutChartEl.style.background = `conic-gradient(${segments.map(segment => `${segment.color} ${segment.start}deg ${segment.end}deg`).join(', ')})`;
}

function renderBrowserDonut(items) {
  if (!browserDonutChartEl || !browserDonutTotalEl) return;
  browserDonutTotalEl.textContent = '-';
  browserDonutChartEl.style.background = 'conic-gradient(var(--donut-empty) 0deg 360deg)';
  if (!items?.length) return;

  const segments = buildDonutSegments(items, 'domain');
  const total = items.reduce((sum, item) => sum + (item.duration || 0), 0);
  browserDonutTotalEl.textContent = formatDuration(total);
  browserDonutChartEl.style.background = `conic-gradient(${segments.map(segment => `${segment.color} ${segment.start}deg ${segment.end}deg`).join(', ')})`;
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

function renderInputSummary(summary) {
  renderInputSummaryGrid(inputSummaryEl, summary, {
    formatNumber,
    formatRate
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
  const aliasedItems = applyAliasesToItems(items);

  if (!aliasedItems.length) {
    const empty = document.createElement('div');
    empty.className = 'input-empty';
    empty.textContent = '暂无数据';
    inputTableEl.appendChild(empty);
    return;
  }

  const maxPresses = Math.max(...aliasedItems.map(item => item.presses || 0), 0);
  const maxClicks = Math.max(...aliasedItems.map(item => item.clicks || 0), 0);
  const maxScroll = Math.max(...aliasedItems.map(item => item.scroll || 0), 0);
  const maxMoves = Math.max(...aliasedItems.map(item => item.moves || 0), 0);

  aliasedItems.forEach(item => {
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

function renderHourlyChart(hourlyBars) {
  renderApplicationHourlyBars({ hourlyBars: hourlyBars || [] });
}

function renderBrowserTrend(trend) {
  renderBrowserHourlyBars(trend || { hourlyBars: [] });
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
  renderBrowserSummary(null);
  renderBrowserList([]);
  renderBrowserDonut([]);
  renderBrowserTrend(null);
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

  const mergedColorMap = {
    ...(visualization?.colorMap || {}),
    ...((payload.browserTrend && payload.browserTrend.colorMap) || {})
  };
  setColorMap(mergedColorMap);

  const activity = payload.activity || [];
  renderApps(activity);
  renderDonut(activity);
  renderBrowserSummary(payload.browserSummary || null);
  renderBrowserList(payload.browserByDomain || []);
  renderBrowserDonut(payload.browserByDomain || []);
  appState.browserActiveHour = payload.browserTrend?.activeHour ?? null;
  renderBrowserTrend(payload.browserTrend || null);
  renderInputSummary(payload.inputSummary || null);
  renderInputTrend(payload.inputTrend || []);
  renderInputTable(payload.inputByApp || payload.inputTopApps || []);

  setActiveHour(visualization?.activeHour ?? null);
  renderVisualizations(visualization);
}

function sortExcludedApps(items) {
  return [...items].sort((left, right) => left.localeCompare(right, 'zh-CN', { sensitivity: 'base' }));
}

function normalizeExcludedAppName(value) {
  return String(value || '').trim();
}

function sortAliases(aliases) {
  return Object.fromEntries(
    Object.entries(aliases || {}).sort(([left], [right]) => left.localeCompare(right, 'zh-CN', { sensitivity: 'base' }))
  );
}

function normalizeAliasKey(value) {
  const normalized = String(value || '').trim().toLowerCase();
  return normalized.endsWith('.exe') ? normalized.slice(0, -4) : normalized;
}

function normalizeAliasValue(value) {
  return String(value || '').trim();
}

function renderDetectedApps() {
  if (!detectedAppsListEl) return;
  detectedAppsListEl.innerHTML = '';
  const items = Array.isArray(appState.detectedApps) ? appState.detectedApps : [];
  if (!items.length) {
    detectedAppsListEl.innerHTML = '<div class="input-empty">暂无检测记录</div>';
    return;
  }

  items.forEach(item => {
    const appName = item.app || '';
    const displayName = item.display_name || '';
    const isEditing = appState.editingDetectedAliasApp === appName;
    const row = document.createElement('div');
    row.className = `settings-row detected-app-row${isEditing ? ' editing' : ''}`;
    row.innerHTML = isEditing
      ? `
        <div class="detected-app-inline-editor">
          <input class="settings-input detected-alias-app" type="text" value="${escapeHtml(appName)}" readonly />
          <span class="settings-row-arrow">→</span>
          <input class="settings-input detected-alias-name" type="text" value="${escapeHtml(displayName)}" data-inline-alias-input="${escapeHtml(appName)}" />
          <div class="settings-row-actions">
            <button class="btn" type="button" data-inline-alias-save="${escapeHtml(appName)}">保存别名</button>
            <button class="btn secondary" type="button" data-inline-alias-cancel="${escapeHtml(appName)}">取消</button>
          </div>
        </div>
      `
      : `
        <span class="settings-row-label">${escapeHtml(appName)}</span>
        <span class="settings-row-arrow">→</span>
        <span class="settings-row-label">${escapeHtml(displayName)}</span>
        <div class="settings-row-actions">
          <button class="btn secondary settings-chip-remove" type="button" data-detected-app="${escapeHtml(appName)}">屏蔽</button>
          <button class="btn secondary settings-chip-remove" type="button" data-detected-alias-app="${escapeHtml(appName)}" data-detected-alias-name="${escapeHtml(displayName)}">设为别名</button>
        </div>
      `;
    detectedAppsListEl.appendChild(row);

    if (isEditing) {
      const input = row.querySelector('[data-inline-alias-input]');
      if (input) {
        window.setTimeout(() => {
          input.focus();
          input.select();
        }, 0);
      }
    }
  });
}

async function loadDetectedApps() {
  const api = await waitForPywebviewApi();
  appState.detectedApps = await api.get_detected_apps(50);
  renderDetectedApps();
}

function renderAliasList() {
  if (!aliasListEl) return;
  const items = Object.entries(sortAliases(appState.settings.app_aliases || {}));
  aliasListEl.innerHTML = '';
  if (!items.length) {
    aliasListEl.innerHTML = '<div class="input-empty">暂无应用别名</div>';
    return;
  }

  items.forEach(([appName, aliasName]) => {
    const row = document.createElement('div');
    row.className = 'settings-row';
    row.innerHTML = `
      <span class="settings-row-label">${escapeHtml(appName)}</span>
      <span class="settings-row-arrow">→</span>
      <span class="settings-row-label">${escapeHtml(aliasName)}</span>
      <button class="btn secondary settings-chip-remove" type="button" data-alias-app="${escapeHtml(appName)}">×</button>
    `;
    aliasListEl.appendChild(row);
  });
}

function applyDetectedAppAsExcluded(appName) {
  if (!appName) return;
  const items = new Set(appState.settings.excluded_apps || []);
  items.add(appName);
  appState.settings.excluded_apps = sortExcludedApps(Array.from(items));
  renderExcludedApps();
}

function applyDetectedAppAsAlias(appName, _aliasName) {
  if (!appName) return;
  appState.editingDetectedAliasApp = appName;
  renderDetectedApps();
}

function cancelDetectedAppAliasEdit() {
  appState.editingDetectedAliasApp = '';
  renderDetectedApps();
}

async function saveDetectedAppAlias(appName, aliasName) {
  const normalizedAppName = normalizeAliasKey(appName);
  const normalizedAliasName = normalizeAliasValue(aliasName);
  if (!normalizedAppName || !normalizedAliasName) return;
  appState.settings.app_aliases = sortAliases({
    ...(appState.settings.app_aliases || {}),
    [normalizedAppName]: normalizedAliasName
  });
  appState.editingDetectedAliasApp = '';
  renderAliasList();
  renderDetectedApps();
  await persistSettings(false);
}

async function addAlias() {
  const appName = normalizeAliasKey(aliasAppInputEl?.value);
  const aliasName = normalizeAliasValue(aliasNameInputEl?.value);
  if (!appName || !aliasName) return;
  appState.settings.app_aliases = sortAliases({
    ...(appState.settings.app_aliases || {}),
    [appName]: aliasName
  });
  if (aliasAppInputEl) aliasAppInputEl.value = '';
  if (aliasNameInputEl) {
    aliasNameInputEl.value = '';
    aliasAppInputEl?.focus();
  }
  renderAliasList();
  await persistSettings(false);
}

function removeAlias(appName) {
  const nextAliases = { ...(appState.settings.app_aliases || {}) };
  delete nextAliases[appName];
  appState.settings.app_aliases = sortAliases(nextAliases);
  renderAliasList();
}


function openSettingsModal() {
  if (!settingsModalEl) return;
  settingsModalEl.hidden = false;
  excludedAppInputEl?.focus();
}

async function openSettingsFromTray() {
  openSettingsModal();
  try {
    await Promise.all([loadSettings(), loadDetectedApps()]);
  } catch (err) {
    console.error(err);
  }
}

function closeSettingsModal() {
  if (!settingsModalEl) return;
  settingsModalEl.hidden = true;
}

function renderExcludedApps() {
  if (!excludedAppsListEl) return;
  const items = sortExcludedApps(appState.settings.excluded_apps || []);
  excludedAppsListEl.innerHTML = '';
  if (!items.length) {
    excludedAppsListEl.innerHTML = '<div class="input-empty">暂无黑名单应用</div>';
    return;
  }

  items.forEach(appName => {
    const chip = document.createElement('div');
    chip.className = 'settings-chip';
    chip.innerHTML = `
      <span class="settings-chip-label">${escapeHtml(appName)}</span>
      <button class="btn secondary settings-chip-remove" type="button" data-app="${escapeHtml(appName)}">×</button>
    `;
    excludedAppsListEl.appendChild(chip);
  });
}

function addExcludedApp() {
  const appName = normalizeExcludedAppName(excludedAppInputEl?.value);
  if (!appName) return;
  const items = new Set(appState.settings.excluded_apps || []);
  items.add(appName);
  appState.settings.excluded_apps = sortExcludedApps(Array.from(items));
  if (excludedAppInputEl) {
    excludedAppInputEl.value = '';
    excludedAppInputEl.focus();
  }
  renderExcludedApps();
}

function removeExcludedApp(appName) {
  appState.settings.excluded_apps = (appState.settings.excluded_apps || []).filter(item => item !== appName);
  renderExcludedApps();
}

async function loadSettings() {
  const api = await waitForPywebviewApi();
  const payload = await api.get_settings();
  appState.settings = {
    excluded_apps: Array.isArray(payload?.excluded_apps) ? sortExcludedApps(payload.excluded_apps.map(normalizeExcludedAppName).filter(Boolean)) : [],
    app_aliases: sortAliases(payload?.app_aliases || {})
  };
  renderExcludedApps();
  renderAliasList();
}

async function persistSettings(closeAfterSave = false) {
  const api = await waitForPywebviewApi();
  const payload = await api.save_settings(appState.settings.excluded_apps || [], appState.settings.app_aliases || {});
  appState.settings = {
    excluded_apps: Array.isArray(payload?.excluded_apps) ? sortExcludedApps(payload.excluded_apps.map(normalizeExcludedAppName).filter(Boolean)) : [],
    app_aliases: sortAliases(payload?.app_aliases || {})
  };
  renderExcludedApps();
  renderAliasList();
  renderDetectedApps();
  if (closeAfterSave) {
    closeSettingsModal();
  }
  await loadData();
}


async function saveSettings() {
  settingsSaveBtn.disabled = true;
  try {
    await persistSettings(true);
  } finally {
    settingsSaveBtn.disabled = false;
  }
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

async function loadData() {
  const token = ++appState.loadToken;
  const days = 1;

  try {
    const payload = await loadDashboardPayload(days);
    if (token !== appState.loadToken) return;

    if (!payload?.ok) {
      clearDashboard();
      return;
    }

    setDashboardFromPayload(payload);
  } catch (err) {
    if (token !== appState.loadToken) return;
    clearDashboard();
    console.error(err);
  }
}

function setActivePanel(panelName) {
  appState.currentPanel = panelName;
  dashboardTabEls.forEach(button => {
    const selected = button.dataset.panel === panelName;
    button.classList.toggle('active', selected);
    button.setAttribute('aria-pressed', String(selected));
  });
  dashboardPanelEls.forEach(panel => {
    panel.hidden = panel.dataset.panel !== panelName;
  });
}

function initializeDashboardTabs() {
  if (!dashboardTabEls.length || !dashboardPanelEls.length) return;
  dashboardTabEls.forEach(button => {
    button.addEventListener('click', () => {
      setActivePanel(button.dataset.panel || 'applications');
    });
  });
  setActivePanel(appState.currentPanel);
}

if (themeToggleBtn) {
  themeToggleBtn.addEventListener('click', toggleTheme);
}
if (settingsCloseBtn) {
  settingsCloseBtn.addEventListener('click', () => closeSettingsModal());
}
if (addExcludedAppBtn) {
  addExcludedAppBtn.addEventListener('click', () => addExcludedApp());
}
if (excludedAppInputEl) {
  excludedAppInputEl.addEventListener('keydown', event => {
    if (event.key === 'Enter') {
      event.preventDefault();
      addExcludedApp();
    }
  });
}
if (excludedAppsListEl) {
  excludedAppsListEl.addEventListener('click', event => {
    const button = event.target.closest('[data-app]');
    if (!button) return;
    removeExcludedApp(button.dataset.app || '');
  });
}
if (addAliasBtn) {
  addAliasBtn.addEventListener('click', () => addAlias().catch(console.error));
}
if (aliasAppInputEl && aliasNameInputEl) {
  const onAliasKeydown = event => {
    if (event.key === 'Enter') {
      event.preventDefault();
      addAlias().catch(console.error);
    }
  };
  aliasAppInputEl.addEventListener('keydown', onAliasKeydown);
  aliasNameInputEl.addEventListener('keydown', onAliasKeydown);
}
if (aliasListEl) {
  aliasListEl.addEventListener('click', event => {
    const button = event.target.closest('[data-alias-app]');
    if (!button) return;
    removeAlias(button.dataset.aliasApp || '');
  });
}
if (settingsSaveBtn) {
  settingsSaveBtn.addEventListener('click', () => saveSettings());
}
if (settingsModalEl) {
  settingsModalEl.addEventListener('click', event => {
    if (event.target === settingsModalEl) {
      closeSettingsModal();
    }
  });
}

if (detectedAppsListEl) {
  detectedAppsListEl.addEventListener('click', event => {
    const excludedButton = event.target.closest('[data-detected-app]');
    if (excludedButton) {
      applyDetectedAppAsExcluded(excludedButton.dataset.detectedApp || '');
      return;
    }
    const aliasButton = event.target.closest('[data-detected-alias-app]');
    if (aliasButton) {
      applyDetectedAppAsAlias(aliasButton.dataset.detectedAliasApp || '', aliasButton.dataset.detectedAliasName || '');
      return;
    }
    const saveButton = event.target.closest('[data-inline-alias-save]');
    if (saveButton) {
      const appName = saveButton.dataset.inlineAliasSave || '';
      const row = saveButton.closest('.detected-app-row');
      const input = row?.querySelector('[data-inline-alias-input]');
      saveDetectedAppAlias(appName, input?.value || '').catch(console.error);
      return;
    }
    const cancelButton = event.target.closest('[data-inline-alias-cancel]');
    if (cancelButton) {
      cancelDetectedAppAliasEdit();
    }
  });
  detectedAppsListEl.addEventListener('keydown', event => {
    const input = event.target.closest('[data-inline-alias-input]');
    if (!input) return;
    if (event.key === 'Enter') {
      event.preventDefault();
      saveDetectedAppAlias(input.dataset.inlineAliasInput || '', input.value || '').catch(console.error);
    }
    if (event.key === 'Escape') {
      event.preventDefault();
      cancelDetectedAppAliasEdit();
    }
  });
}

window.onHourSelect = onHourSelect;
window.AwPywebviewApp = {
  KEY_HOURS,
  renderYAxisFor,
  renderXAxisFor,
  buildTooltipContent,
  showTooltip,
  hideTooltip,
  openSettingsFromTray
};

window.addEventListener('DOMContentLoaded', async () => {
  initializeTheme();
  initializeDashboardTabs();
  try {
    await waitForPywebviewApi();
    await loadDetectedApps();
    await loadSettings();
  } catch (err) {
    clearDashboard();
    console.error(err);
    return;
  }
  loadData();
});

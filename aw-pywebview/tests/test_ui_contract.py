from pathlib import Path


ROOT = Path(__file__).resolve().parents[1] / "aw_pywebview" / "ui"


def test_frontend_daily_summary_hooks_exist():
    app_js = (ROOT / "app.js").read_text(encoding="utf-8")

    assert "window.onHourSelect = onHourSelect;" in app_js
    assert "return api.get_dashboard_data(days, 12, 0, 6);" in app_js
    assert "await waitForPywebviewApi();" in app_js
    assert "renderDonut(activity);" in app_js
    assert "renderHourlyChart(hourlyBars);" in app_js
    assert "setActiveHour(visualization?.activeHour ?? null);" in app_js
    assert "showHourlyTooltip(" in app_js
    assert "renderBrowserSummary(payload.browserSummary || null);" in app_js
    assert "renderBrowserList(payload.browserByDomain || []);" in app_js
    assert "renderBrowserDonut(payload.browserByDomain || []);" in app_js
    assert "renderBrowserTrend(payload.browserTrend || null);" in app_js
    assert "function setActivePanel(panelName)" in app_js
    assert "function initializeDashboardTabs()" in app_js
    assert "setActivePanel(appState.currentPanel);" in app_js
    assert "button.dataset.panel || 'applications'" in app_js
    assert "calculateAverageSwitchRate(" in app_js
    assert "renderInputSummary(payload.inputSummary || null);" in app_js
    assert "renderInputTrend(payload.inputTrend || []);" in app_js
    assert "renderInputTable(payload.inputByApp || payload.inputTopApps || []);" in app_js
    assert "const KEY_HOURS = new Set([0, 4, 8, 12, 16, 20, 24]);" in app_js
    assert "tick.textContent = KEY_HOURS.has(hour) ? String(hour).padStart(2, '0') : '';" in app_js
    assert "renderLegend(" not in app_js
    assert "app-summary-item" in app_js
    assert "input-summary-card" in app_js
    assert "input-trend-bar" in app_js
    assert "input-bar-row" in app_js
    assert "input-metric-fill" in app_js
    assert "statusEl" not in app_js


def test_frontend_daily_summary_layout_containers_exist():
    index_html = (ROOT / "index.html").read_text(encoding="utf-8")
    style_css = (ROOT / "style.css").read_text(encoding="utf-8")
    app_js = (ROOT / "app.js").read_text(encoding="utf-8")

    assert 'class="dashboard-layout"' in index_html
    assert 'class="dashboard-tabs-wrap card-shell translucent"' in index_html
    assert 'class="dashboard-tab active" type="button" data-panel="applications"' in index_html
    assert 'class="dashboard-tab" type="button" data-panel="browser"' in index_html
    assert 'class="dashboard-tab" type="button" data-panel="input"' in index_html
    assert 'class="dashboard-panel" data-panel="applications"' in index_html
    assert 'class="dashboard-panel" data-panel="browser" hidden' in index_html
    assert 'class="dashboard-panel" data-panel="input" hidden' in index_html
    assert '.dashboard-layout {' in style_css
    assert 'position: sticky;' in style_css
    assert 'top: 18px;' in style_css
    assert 'background: var(--tab-track-bg);' in style_css
    assert 'background: var(--tab-active-bg);' in style_css
    assert '@keyframes fade-slide-in {' in style_css
    assert 'class="stats-strip topbar-stats"' in index_html
    assert 'id="activeDuration"' in index_html
    assert 'id="appCount"' in index_html
    assert 'id="avgSwitchRate"' in index_html
    assert 'id="donutChart"' in index_html
    assert 'id="donutTotal"' in index_html
    assert 'id="appList" class="app-summary-list two-column-list"' in index_html
    assert 'id="browserSummary" class="browser-summary-grid"' in index_html
    assert 'id="browserDonutChart" class="donut-chart"' in index_html
    assert 'id="browserDonutTotal" class="donut-center-value"' in index_html
    assert 'id="browserDomainList" class="app-summary-list two-column-list"' in index_html
    assert 'id="browserTrendChart" class="hourly-chart full-width-hourly-chart"' in index_html
    assert 'id="browserTrendYAxis"' in index_html
    assert 'id="browserTrendXAxis"' in index_html
    assert 'id="browserTrendTooltip"' in index_html
    assert 'id="inputSummary" class="input-summary-grid"' in index_html
    assert 'id="inputTrend" class="input-trend-chart"' in index_html
    assert 'id="inputTable" class="input-bars"' in index_html
    assert 'id="settingsBtn" class="btn secondary icon-btn"' in index_html
    assert 'id="quickSettingsBtn" class="btn secondary icon-btn"' in index_html
    assert 'id="settingsModal" class="modal-backdrop" hidden' in index_html
    assert 'id="excludedAppInput" class="settings-input"' in index_html
    assert 'id="addExcludedAppBtn" class="btn" type="button">添加黑名单<' in index_html
    assert 'id="excludedAppsList" class="settings-chip-list"' in index_html
    assert 'id="detectedAppsList" class="settings-list settings-list-rows"' in index_html
    assert '最近检测到的应用' in index_html
    assert 'id="aliasAppInput" class="settings-input"' in index_html
    assert 'id="aliasNameInput" class="settings-input"' in index_html
    assert 'id="addAliasBtn" class="btn" type="button">添加别名<' in index_html
    assert 'id="aliasList" class="settings-list settings-list-rows"' in index_html
    assert '.modal-backdrop {' in style_css
    assert '.settings-modal {' in style_css
    assert '.settings-chip {' in style_css
    assert '.settings-form-grid {' in style_css
    assert '.settings-row {' in style_css
    assert 'await persistSettings(false);' in app_js
    assert "addExcludedApp().catch(console.error);" in app_js
    assert "removeExcludedApp(button.dataset.app || '').catch(console.error);" in app_js
    assert 'function renderDetectedApps()' in app_js
    assert 'await api.get_detected_apps(50);' in app_js
    assert 'function renderAliasList()' in app_js
    assert 'function addAlias()' in app_js
    assert 'function removeAlias(appName)' in app_js
    assert 'await persistSettings(false);' in app_js
    assert "removeAlias(button.dataset.aliasApp || '').catch(console.error);" in app_js
    assert 'function openSettingsFromTray()' in app_js
    assert 'await loadSettings();' in app_js
    assert 'openSettingsFromTray' in app_js
    assert 'await api.get_settings();' in app_js
    assert 'await api.save_settings(appState.settings.excluded_apps || [], appState.settings.app_aliases || {});' in app_js
    assert 'data-alias-app=' in app_js
    assert 'sortAliases(payload?.app_aliases || {})' in app_js
    assert 'removeAlias(button.dataset.aliasApp || ' in app_js
    assert 'id="settingsSaveBtn" class="btn" type="button">保存设置<' in index_html
    assert '.toolbar-actions {' in style_css
    assert '.status-wrap {' not in style_css
    assert '.badge {' not in style_css
    assert 'id="status"' not in index_html
    assert '0 - 24' in index_html
    assert '应用时长占比' in index_html
    assert '浏览器网页分析' in index_html
    assert '24 小时网页浏览趋势' in index_html
    assert '24 小时活跃度分析' in index_html
    assert '24 小时输入趋势' in index_html
    assert '应用输入归因' in index_html
    assert '>输入强度<' in index_html
    assert '侧边标签栏' not in index_html
    assert '分析视图' not in index_html
    assert 'class="dashboard-sidebar card-shell translucent"' not in index_html
    assert 'class="stats-strip full-span-stats"' not in index_html
    assert 'id="hourlyLegend"' not in index_html
    assert 'id="status"' not in index_html
    assert '.toolbar-actions {' in style_css
    assert '.status-wrap {' not in style_css
    assert '.badge {' not in style_css
    assert '0 - 24' in index_html
    assert '应用时长占比' in index_html
    assert '浏览器网页分析' in index_html
    assert '24 小时网页浏览趋势' in index_html
    assert '24 小时活跃度分析' in index_html
    assert '24 小时输入趋势' in index_html
    assert '应用输入归因' in index_html
    assert '>输入强度<' in index_html
    assert '侧边标签栏' not in index_html
    assert '分析视图' not in index_html
    assert 'class="dashboard-sidebar card-shell translucent"' not in index_html
    assert 'class="stats-strip full-span-stats"' not in index_html
    assert 'id="hourlyLegend"' not in index_html


def test_frontend_removed_old_gantt_heatmap_and_timeline_sections():
    index_html = (ROOT / "index.html").read_text(encoding="utf-8")
    app_js = (ROOT / "app.js").read_text(encoding="utf-8")

    assert 'id="ganttScroll"' not in index_html
    assert 'id="ganttHourHighlight"' not in index_html
    assert 'id="ganttChart"' not in index_html
    assert 'id="heatmap"' not in index_html
    assert 'id="timeline"' not in index_html
    assert 'id="timelineBars"' not in index_html
    assert "renderGanttChart(" not in app_js
    assert "renderHeatmap(" not in app_js
    assert "renderTimeline(" not in app_js

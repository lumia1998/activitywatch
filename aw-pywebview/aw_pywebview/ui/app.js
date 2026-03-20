const statusEl = document.getElementById('status');
const activeDurationEl = document.getElementById('activeDuration');
const appCountEl = document.getElementById('appCount');
const timeRangeEl = document.getElementById('timeRange');
const appListEl = document.getElementById('appList');
const timelineEl = document.getElementById('timeline');
const timelineBarsEl = document.getElementById('timelineBars');
const inputTableEl = document.getElementById('inputTable');
const refreshBtn = document.getElementById('refreshBtn');
const reportBtn = document.getElementById('reportBtn');
const rangeSelect = document.getElementById('rangeSelect');

const palette = ['#f7d8b5', '#cfd9c9', '#f2c9c9', '#d8d2f0', '#f2e2a9', '#d7e3f7'];

function formatDuration(seconds) {
  if (!seconds || seconds <= 0) return '-';
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  return `${hours}h ${minutes}m`;
}

function formatTimeRange(startIso, endIso) {
  const start = new Date(startIso);
  const end = new Date(endIso);
  const pad = value => value.toString().padStart(2, '0');
  return `${pad(start.getHours())}:${pad(start.getMinutes())} - ${pad(end.getHours())}:${pad(end.getMinutes())}`;
}

function colorForCategory(category) {
  let hash = 0;
  for (let i = 0; i < category.length; i += 1) {
    hash = (hash + category.charCodeAt(i) * 31) % palette.length;
  }
  return palette[hash];
}

function renderApps(items) {
  appListEl.innerHTML = '';
  if (!items.length) {
    const li = document.createElement('li');
    li.className = 'list-item';
    li.textContent = '暂无数据';
    appListEl.appendChild(li);
    return;
  }
  items.forEach(item => {
    const li = document.createElement('li');
    li.className = 'list-item';
    const name = document.createElement('span');
    name.textContent = item.app;
    const duration = document.createElement('span');
    duration.textContent = formatDuration(item.duration);
    li.appendChild(name);
    li.appendChild(duration);
    appListEl.appendChild(li);
  });
}

function renderInputTable(items) {
  inputTableEl.innerHTML = '';

  const header = document.createElement('div');
  header.className = 'input-row header';
  header.innerHTML = '<div>应用</div><div>键盘</div><div>点击</div><div>滚轮</div>';
  inputTableEl.appendChild(header);

  if (!items.length) {
    const row = document.createElement('div');
    row.className = 'input-row';
    row.innerHTML = '<div>暂无数据</div><div>-</div><div>-</div><div>-</div>';
    inputTableEl.appendChild(row);
    return;
  }

  items.forEach(item => {
    const row = document.createElement('div');
    row.className = 'input-row';
    row.innerHTML = `<div>${item.app}</div><div>${item.presses}</div><div>${item.clicks}</div><div>${item.scroll}</div>`;
    inputTableEl.appendChild(row);
  });
}

function renderTimeline(items) {
  timelineEl.innerHTML = '';
  timelineBarsEl.innerHTML = '';
  if (!items.length) {
    const empty = document.createElement('div');
    empty.className = 'timeline-item';
    empty.textContent = '暂无时间线数据';
    timelineEl.appendChild(empty);
    return;
  }

  const baseDay = new Date(items[0].start);
  baseDay.setHours(0, 0, 0, 0);
  const dayStart = baseDay.getTime();
  const dayMs = 24 * 60 * 60 * 1000;

  items.forEach((item, index) => {
    const row = document.createElement('div');
    row.className = 'timeline-item';

    const time = document.createElement('div');
    time.className = 'timeline-time';
    time.textContent = formatTimeRange(item.start, item.end);

    const content = document.createElement('div');
    content.className = 'timeline-content';

    const app = document.createElement('div');
    app.className = 'timeline-app';
    app.textContent = item.app || 'unknown';

    const title = document.createElement('div');
    title.className = 'timeline-title';
    title.textContent = item.title || '无标题';

    const category = document.createElement('div');
    category.className = 'timeline-category';
    category.textContent = item.category || '未分类';

    content.appendChild(app);
    content.appendChild(title);
    content.appendChild(category);

    row.appendChild(time);
    row.appendChild(content);
    timelineEl.appendChild(row);

    const bar = document.createElement('div');
    bar.className = 'timeline-bar';
    bar.textContent = item.category || item.app || '未分类';

    const start = new Date(item.start).getTime();
    const end = new Date(item.end).getTime();
    const left = ((start - dayStart) / dayMs) * 100;
    const width = Math.max(((end - start) / dayMs) * 100, 0.4);

    bar.style.left = `${Math.max(0, left)}%`;
    bar.style.width = `${Math.min(100 - left, width)}%`;
    bar.style.top = `${index * 22}px`;
    bar.style.background = colorForCategory(item.category || item.app || '未分类');

    timelineBarsEl.appendChild(bar);
  });
}

async function generateReport() {
  statusEl.textContent = '生成报告中...';
  try {
    const path = await window.pywebview.api.generate_report_today();
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
  statusEl.textContent = '加载中';
  const days = Number(rangeSelect.value || 1);
  try {
    const summary = await window.pywebview.api.get_summary(days);
    if (summary.error) {
      statusEl.textContent = '缺少数据桶';
      renderTimeline([]);
      renderInputTable([]);
      return;
    }

    const result = summary.result;
    const duration = result?.window?.duration || 0;
    const appEvents = result?.window?.app_events || [];

    activeDurationEl.textContent = formatDuration(duration);
    appCountEl.textContent = appEvents.length.toString();
    timeRangeEl.textContent = `${summary.time_range.start.slice(0, 10)} → ${summary.time_range.end.slice(0, 10)}`;

    const apps = await window.pywebview.api.get_activity(days, 12);
    renderApps(apps);

    const inputStats = await window.pywebview.api.get_input_top_apps(days, 6);
    renderInputTable(inputStats);

    const timeline = await window.pywebview.api.get_timeline(days, 40);
    renderTimeline(timeline);

    statusEl.textContent = '已更新';
  } catch (err) {
    statusEl.textContent = '加载失败';
    renderTimeline([]);
    renderInputTable([]);
  }
}

refreshBtn.addEventListener('click', () => loadData());
reportBtn.addEventListener('click', () => generateReport());
rangeSelect.addEventListener('change', () => loadData());

window.addEventListener('DOMContentLoaded', () => {
  loadData();
});

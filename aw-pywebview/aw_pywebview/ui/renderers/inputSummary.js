(() => {
  function renderInputSummary(inputSummaryEl, summary, helpers) {
    if (!inputSummaryEl) return;
    const { formatNumber, formatRate } = helpers;

    if (!summary?.available) {
      inputSummaryEl.innerHTML = '<div class="input-summary-card empty-state">暂无输入数据</div>';
      return;
    }

    const totals = summary.totals || {};
    const peakHour = summary.peakHour;
    inputSummaryEl.innerHTML = [
      {
        label: '总键盘点击',
        value: formatNumber(totals.presses || 0),
        meta: '当前时间范围内记录的键盘按键次数'
      },
      {
        label: '总鼠标点击',
        value: formatNumber(totals.clicks || 0),
        meta: '当前时间范围内记录的鼠标点击次数'
      },
      {
        label: '平均输入强度',
        value: formatRate(summary.averagePerHour),
        meta: peakHour ? `峰值 ${String(peakHour.hour).padStart(2, '0')}:00 · ${formatNumber(peakHour.total)} 次/小时` : '暂无峰值时段'
      },
      {
        label: '滚动与移动',
        value: `${formatNumber(totals.scroll || 0)} / ${formatNumber(totals.moves || 0)}`,
        meta: '滚轮次数 / 鼠标移动距离累计'
      }
    ].map(card => `
      <div class="input-summary-card">
        <span class="input-summary-label">${card.label}</span>
        <strong class="input-summary-value">${card.value}</strong>
        <span class="input-summary-meta">${card.meta}</span>
      </div>
    `).join('');
  }

  window.AwUiRenderers = {
    renderInputSummary
  };
})();

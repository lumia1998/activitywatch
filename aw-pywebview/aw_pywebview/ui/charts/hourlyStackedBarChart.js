(() => {
  const CHART_KEY_HOURS = new Set([0, 4, 8, 12, 16, 20, 24]);

  function renderYAxisFor(axisEl, maxDuration) {
    if (!axisEl) return;
    axisEl.innerHTML = '';
    const ticks = [0, 0.25, 0.5, 0.75, 1].map(ratio => Math.round((maxDuration * ratio) / 60));
    ticks.reverse().forEach(value => {
      const tick = document.createElement('span');
      tick.textContent = `${value}`;
      axisEl.appendChild(tick);
    });
  }

  function renderXAxisFor(axisEl, options = {}) {
    if (!axisEl) return;
    const keyHours = options.keyHours || CHART_KEY_HOURS;
    const decorateTick = typeof options.decorateTick === 'function' ? options.decorateTick : null;
    axisEl.innerHTML = '';
    Array.from({ length: 25 }, (_, hour) => hour).forEach(hour => {
      const tick = document.createElement('span');
      tick.textContent = keyHours.has(hour) ? String(hour).padStart(2, '0') : '';
      if (keyHours.has(hour)) tick.classList.add('major');
      if (decorateTick) {
        decorateTick(tick, hour, keyHours);
      }
      axisEl.appendChild(tick);
    });
  }

  function buildTooltipContent(item, options = {}) {
    const {
      labelKey = 'app',
      emptyLabel = '暂无活跃应用',
      totalLabel = '总活跃',
      formatHour,
      formatMinutes,
      formatPreciseDuration,
      escapeHtml,
      getColor
    } = options;
    const topSegments = (item.segments || []).slice(0, 5);
    if (!topSegments.length) {
      return `
      <div class="tooltip-header">
        <span class="tooltip-hour">${formatHour(item.hour)}</span>
        <span class="tooltip-total">${totalLabel} 0m</span>
      </div>
      <div class="tooltip-list">
        <div class="tooltip-item"><span class="tooltip-name">${emptyLabel}</span></div>
      </div>
    `;
    }

    return `
    <div class="tooltip-header">
      <span class="tooltip-hour">${formatHour(item.hour)}</span>
      <span class="tooltip-total">${totalLabel} ${formatMinutes(item.total)}</span>
    </div>
    <div class="tooltip-list">
      ${topSegments.map(segment => {
        const label = segment[labelKey] || segment.app || segment.domain || '未知';
        return `
        <div class="tooltip-item">
          <span class="tooltip-swatch" style="background:${segment.color || getColor(label)}"></span>
          <span class="tooltip-name">${escapeHtml(label)}</span>
          <span class="tooltip-value">${formatPreciseDuration(segment.duration)}</span>
        </div>
      `;
      }).join('')}
    </div>
  `;
  }

  function showTooltip(tooltipEl, item, options = {}) {
    if (!tooltipEl) return;
    tooltipEl.innerHTML = buildTooltipContent(item, options);
    tooltipEl.hidden = false;
  }

  function hideTooltip(tooltipEl) {
    if (!tooltipEl) return;
    tooltipEl.hidden = true;
    tooltipEl.innerHTML = '';
  }

  function createHourlyStackedBarChartRenderer(options) {
    const {
      chartEl,
      axisEl,
      xAxisEl,
      tooltipEl,
      getSelectedHour,
      setSelectedHour,
      onHourChange,
      onShowTooltip,
      onHideTooltip,
      getSegmentKey,
      getColor,
      renderHint,
      renderEmptyHint,
      renderXAxis = renderXAxisFor,
      renderYAxis = renderYAxisFor,
      xAxisOptions
    } = options;

    return function renderHourlyStackedBarChart(data) {
      if (!chartEl || !axisEl || !xAxisEl) return;
      chartEl.innerHTML = '';
      hideTooltip(tooltipEl);
      renderXAxis(xAxisEl, xAxisOptions || {});

      const hourlyBars = data?.hourlyBars || [];
      if (!hourlyBars.length) {
        renderYAxis(axisEl, 0);
        if (renderEmptyHint) {
          renderEmptyHint(data);
        }
        return;
      }

      const maxDuration = Math.max(...hourlyBars.map(item => item.total || 0), 0);
      renderYAxis(axisEl, maxDuration);

      hourlyBars.forEach(item => {
        const barDiv = document.createElement('div');
        barDiv.className = 'hour-bar';
        barDiv.dataset.hour = String(item.hour);
        barDiv.tabIndex = 0;
        if (getSelectedHour() === item.hour) barDiv.classList.add('selected');

        const segmentsDiv = document.createElement('div');
        segmentsDiv.className = 'bar-segments';
        const barHeight = maxDuration > 0 ? Math.max((item.total / maxDuration) * 250, item.total > 0 ? 12 : 8) : 8;
        segmentsDiv.style.height = `${barHeight}px`;

        (item.segments || []).forEach(segment => {
          const segmentEl = document.createElement('div');
          segmentEl.className = 'bar-segment';
          const segmentHeight = item.total > 0 ? Math.max((segment.duration / item.total) * barHeight, 4) : 4;
          segmentEl.style.height = `${segmentHeight}px`;
          segmentEl.style.background = segment.color || getColor(getSegmentKey(segment));
          segmentsDiv.appendChild(segmentEl);
        });

        const label = document.createElement('div');
        label.className = 'hour-label';
        label.textContent = item.hour.toString().padStart(2, '0');

        barDiv.appendChild(segmentsDiv);
        barDiv.appendChild(label);
        barDiv.addEventListener('click', () => {
          setSelectedHour(item.hour);
          if (onHourChange) {
            onHourChange(data);
          }
        });
        barDiv.addEventListener('mouseenter', () => onShowTooltip(item));
        barDiv.addEventListener('focus', () => onShowTooltip(item));
        barDiv.addEventListener('mouseleave', onHideTooltip);
        barDiv.addEventListener('blur', onHideTooltip);

        chartEl.appendChild(barDiv);
      });

      if (renderHint) {
        renderHint(data);
      }
    };
  }

  window.AwUiCharts = {
    KEY_HOURS: CHART_KEY_HOURS,
    renderYAxisFor,
    renderXAxisFor,
    buildTooltipContent,
    showTooltip,
    hideTooltip,
    createHourlyStackedBarChartRenderer
  };
})();

(() => {
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

  window.AwUiFormatters = {
    formatDuration,
    formatPreciseDuration,
    formatHour,
    formatMinutes,
    formatNumber,
    formatRate
  };
})();

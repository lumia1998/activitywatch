(() => {
  const FALLBACK_COLORS = ['#60a5fa', '#34d399', '#fbbf24', '#a78bfa', '#f9a8d4', '#67e8f9', '#86efac', '#fdba74'];

  function createColorHelpers(state) {
    function setColorMap(colorMap = {}) {
      state.colorMap = new Map(Object.entries(colorMap));
    }

    function getColor(key) {
      if (state.colorMap.has(key)) {
        return state.colorMap.get(key);
      }
      let hash = 0;
      for (let i = 0; i < key.length; i += 1) {
        hash = (hash + key.charCodeAt(i) * 31) % FALLBACK_COLORS.length;
      }
      const color = FALLBACK_COLORS[hash];
      state.colorMap.set(key, color);
      return color;
    }

    return {
      setColorMap,
      getColor
    };
  }

  window.AwUiColors = {
    FALLBACK_COLORS,
    createColorHelpers
  };
})();

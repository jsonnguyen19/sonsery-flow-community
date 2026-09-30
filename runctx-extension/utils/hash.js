window.__RUNCTX__ = window.__RUNCTX__ || {};

window.__RUNCTX__.HashUtils = {
  hashText(text) {
    let hash = 0;
    for (let i = 0; i < text.length; i += 1) {
      hash = (hash << 5) - hash + text.charCodeAt(i);
      hash |= 0;
    }
    return String(hash);
  },

  cleanCodeBlock(text) {
    return (text || "").replace(/\r/g, "").trim();
  },
};

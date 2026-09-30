window.__RUNCTX__ = window.__RUNCTX__ || {};

function copyTextFallback(text) {
  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.setAttribute("readonly", "");
  textarea.style.position = "fixed";
  textarea.style.left = "-9999px";
  textarea.style.top = "-9999px";
  document.body.appendChild(textarea);
  textarea.focus();
  textarea.select();

  try {
    return document.execCommand("copy");
  } finally {
    textarea.remove();
  }
}

window.__RUNCTX__.ClipboardTransport = {
  async read() {
    return navigator.clipboard.readText();
  },

  async write(text) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch {
      return copyTextFallback(text);
    }
  },
};

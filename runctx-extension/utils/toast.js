window.__RUNCTX__ = window.__RUNCTX__ || {};

window.__RUNCTX__.shouldShowToasts = async function () {
  const state = await chrome.storage.local.get(["showToasts"]);
  return state.showToasts !== false;
};

function getToastRoot() {
  let root = document.getElementById("runctx-bridge-toast-root");
  if (!root) {
    root = document.createElement("div");
    root.id = "runctx-bridge-toast-root";
    root.style.cssText = `
      position: fixed;
      left: 50%;
      top: 18px;
      transform: translateX(-50%);
      z-index: 2147483647;
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 6px;
      pointer-events: none;
    `;
    document.body.appendChild(root);
  }
  return root;
}

function getVariantColor(variant) {
  switch (variant) {
    case "success":
      return "#10b981";
    case "warn":
      return "#f59e0b";
    case "error":
      return "#f43f5e";
    case "info":
    default:
      return "#6366f1";
  }
}

function createToastElement(message, variant = "info") {
  const toast = document.createElement("div");
  const dotColor = getVariantColor(variant);

  toast.style.cssText = `
    display: inline-flex;
    align-items: center;
    gap: 8px;
    max-width: 420px;
    padding: 7px 13px;
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 8px;
    background: rgba(18, 18, 20, 0.94);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    color: #f4f4f5;
    font: 500 12.5px/1.4 ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", Inter, sans-serif;
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4), 0 1px 2px rgba(0, 0, 0, 0.2);
    transform: translateY(-6px) scale(0.98);
    opacity: 0;
    transition: transform 180ms cubic-bezier(0.16, 1, 0.3, 1), opacity 180ms ease;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    pointer-events: auto;
  `;

  const dot = document.createElement("span");
  dot.style.cssText = `
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: ${dotColor};
    flex-shrink: 0;
    box-shadow: 0 0 6px ${dotColor}66;
  `;

  const text = document.createElement("span");
  text.textContent = message;
  text.style.cssText = `
    overflow: hidden;
    text-overflow: ellipsis;
  `;

  toast.appendChild(dot);
  toast.appendChild(text);
  return toast;
}

window.__RUNCTX__.showToast = function showToast(message, variant = "info") {
  const root = getToastRoot();
  const toast = createToastElement(message, variant);
  root.appendChild(toast);

  requestAnimationFrame(() => {
    toast.style.opacity = "1";
    toast.style.transform = "translateY(0) scale(1)";
  });

  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transform = "translateY(-6px) scale(0.98)";
    setTimeout(() => toast.remove(), 180);
  }, 2400);
};

window.__RUNCTX__.showStickyToast = function showStickyToast(id, message, variant = "info") {
  if (!id) return;
  window.__RUNCTX__.hideStickyToast(id);

  const root = getToastRoot();
  const toast = createToastElement(message, variant);
  toast.dataset.stickyId = id;
  root.appendChild(toast);

  requestAnimationFrame(() => {
    toast.style.opacity = "1";
    toast.style.transform = "translateY(0) scale(1)";
  });
};

window.__RUNCTX__.hideStickyToast = function hideStickyToast(id) {
  if (!id) return;
  const root = document.getElementById("runctx-bridge-toast-root");
  if (!root) return;
  const toast = root.querySelector(`[data-sticky-id="${id}"]`);
  if (!toast) return;
  toast.style.opacity = "0";
  toast.style.transform = "translateY(-6px) scale(0.98)";
  setTimeout(() => toast.remove(), 180);
};

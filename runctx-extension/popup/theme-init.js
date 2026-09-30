// Anti-FOUC: set data-theme before the body renders.
(async () => {
  try {
    const KEY = "theme";
    const data = await chrome.storage.local.get([KEY]);
    const raw = data[KEY];
    const theme = ["system", "dark", "light"].includes(raw) ? raw : "system";
    let effective = theme;

    if (theme === "system") {
      effective = window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
    }

    document.documentElement.setAttribute("data-theme", effective);
  } catch {
    document.documentElement.setAttribute("data-theme", "dark");
  }
})();

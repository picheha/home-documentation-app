/* Presentation only: no Home Assistant state, credentials or API requests. */
(() => {
  "use strict";
  const root = document.documentElement;
  const storageKey = "piche.documentation.theme";
  const text = {
    en: { auto: "Auto", follow: "Follow Home Assistant theme", light: "Switch to light theme", dark: "Switch to dark theme" },
    lv: { auto: "Automātiski", follow: "Sekot Home Assistant tēmai", light: "Pārslēgties uz gaišo tēmu", dark: "Pārslēgties uz tumšo tēmu" },
    ru: { auto: "Авто", follow: "Использовать тему Home Assistant", light: "Включить светлую тему", dark: "Включить тёмную тему" }
  };
  const labels = text[(root.lang || "en").toLowerCase().split(/[-_]/)[0]] || text.en;
  const variables = {
    "--primary-background-color": "--doc-background",
    "--card-background-color": "--doc-surface",
    "--primary-text-color": "--doc-text",
    "--secondary-text-color": "--doc-muted",
    "--primary-color": "--doc-primary",
    "--accent-color": "--doc-accent",
    "--divider-color": "--doc-border",
    "--app-header-background-color": "--doc-header",
    "--app-header-text-color": "--doc-header-text",
    "--sidebar-selected-text-color": "--doc-selected",
    "--primary-font-family": "--doc-font",
    "--ha-font-family-body": "--doc-font"
  };
  const light = {
    "--doc-background": "#fafafa", "--doc-surface": "#ffffff",
    "--doc-text": "#212121", "--doc-muted": "#727272",
    "--doc-border": "rgba(0,0,0,.12)", "--doc-header": "#ffffff",
    "--doc-header-text": "#212121"
  };
  const dark = {
    "--doc-background": "#111111", "--doc-surface": "#1c1c1c",
    "--doc-text": "#e1e1e1", "--doc-muted": "#9b9b9b",
    "--doc-border": "rgba(225,225,225,.12)", "--doc-header": "#1c1c1c",
    "--doc-header-text": "#e1e1e1"
  };
  const icons = {
    light: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1.5 1.5m11 11L19 19M5 19l1.5-1.5m11-11L19 5"/></svg>',
    dark: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20 15.5A8.7 8.7 0 0 1 8.5 4 8.8 8.8 0 1 0 20 15.5Z"/></svg>'
  };
  let preference = "auto";
  let mode = "light";
  let controls;
  let toggle;
  let auto;
  let applied = new Set();
  try {
    const saved = window.localStorage.getItem(storageKey);
    if (saved === "light" || saved === "dark") preference = saved;
  } catch (_) { /* Storage may be unavailable in private browsing. */ }
  function framePalette() {
    const palette = {};
    try {
      const frame = window.frameElement;
      if (frame && window.parent !== window) {
        const style = window.parent.getComputedStyle(frame);
        for (const [source, target] of Object.entries(variables)) {
          const value = style.getPropertyValue(source).trim();
          if (value) palette[target] = value;
        }
      }
    } catch (_) { /* Isolated frames keep the system-theme fallback. */ }
    return palette;
  }
  function applyPalette(palette) {
    for (const name of applied) {
      if (!(name in palette)) root.style.removeProperty(name);
    }
    for (const [name, value] of Object.entries(palette)) {
      if (root.style.getPropertyValue(name) !== value) root.style.setProperty(name, value);
    }
    applied = new Set(Object.keys(palette));
  }
  function choose(value) {
    preference = value;
    try {
      if (value === "auto") window.localStorage.removeItem(storageKey);
      else window.localStorage.setItem(storageKey, value);
    } catch (_) { /* The current page still changes without persistent storage. */ }
    syncTheme();
  }
  function mountControls() {
    if (controls) return;
    const nav = document.querySelector(".navbar .container");
    if (!nav) return;
    controls = document.createElement("div");
    controls.className = "doc-theme-controls";
    toggle = document.createElement("button");
    toggle.type = "button";
    toggle.className = "doc-theme-toggle";
    toggle.addEventListener("click", () => choose(mode === "dark" ? "light" : "dark"));
    auto = document.createElement("button");
    auto.type = "button";
    auto.className = "doc-theme-auto";
    auto.textContent = labels.auto;
    auto.title = labels.follow;
    auto.setAttribute("aria-label", labels.follow);
    auto.addEventListener("click", () => choose("auto"));
    controls.append(toggle, auto);
    nav.append(controls);
  }
  function syncTheme() {
    const frame = framePalette();
    root.dataset.homeAssistantTheme = Object.keys(frame).length ? "true" : "false";
    let palette = frame;
    if (preference !== "auto") {
      palette = { ...(preference === "dark" ? dark : light) };
      for (const name of ["--doc-font", "--doc-primary", "--doc-selected"]) {
        if (frame[name]) palette[name] = frame[name];
      }
    }
    applyPalette(palette);
    const color = window.getComputedStyle(document.body).backgroundColor;
    const rgb = color.match(/^rgba?\(\s*([\d.]+)[, ]+([\d.]+)[, ]+([\d.]+)/);
    mode = preference === "auto" ? "light" : preference;
    if (preference === "auto" && rgb) {
      const brightness = .2126 * Number(rgb[1]) + .7152 * Number(rgb[2]) + .0722 * Number(rgb[3]);
      mode = brightness < 128 ? "dark" : "light";
    }
    root.dataset.docThemeMode = mode;
    root.style.colorScheme = mode;
    mountControls();
    if (toggle) {
      const next = mode === "dark" ? "light" : "dark";
      toggle.innerHTML = icons[next];
      toggle.title = labels[next];
      toggle.setAttribute("aria-label", toggle.title);
      auto.hidden = preference === "auto";
    }
  }
  let timer;
  function startSync() {
    syncTheme();
    if (timer === undefined) timer = window.setInterval(syncTheme, 1500);
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", startSync, { once: true });
  else startSync();
  window.addEventListener("pageshow", startSync);
  window.addEventListener("focus", syncTheme);
  window.addEventListener("pagehide", () => {
    window.clearInterval(timer);
    timer = undefined;
  });
})();

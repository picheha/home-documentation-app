// Loaded by Home Assistant so the sidebar can translate before the guide opens.
const sidebarEntryId = "sidebar-panel-60e09302_documentation";
const titles = new Map([
  ["en", "Documentation"],
  ["lv", "Dokumentācija"],
  ["ru", "Документация"],
]);
const knownTitles = new Set(titles.values());

function updateText(element, title) {
  // Keep the text node and comment markers Home Assistant's renderer owns.
  const node = [...(element?.childNodes ?? [])].find(
    (child) => child.nodeType === Node.TEXT_NODE && knownTitles.has(child.data.trim()),
  );
  const current = node?.data.trim();
  if (current && current !== title) {
    node.data = node.data.replace(current, title);
  }
}

let observedSidebar;
const sidebarObserver = new MutationObserver(syncSidebar);

function syncSidebar() {
  const app = document.querySelector("home-assistant");
  const main = app?.shadowRoot?.querySelector("home-assistant-main");
  const sidebar = main?.shadowRoot?.querySelector("ha-sidebar")?.shadowRoot;

  if (sidebar !== observedSidebar) {
    sidebarObserver.disconnect();
    observedSidebar = sidebar;
    if (sidebar) {
      sidebarObserver.observe(sidebar, {
        characterData: true,
        childList: true,
        subtree: true,
      });
    }
  }

  const entry = sidebar?.getElementById(sidebarEntryId);
  if (!entry) return;

  const language = app.hass?.locale?.language || app.hass?.language ||
    document.documentElement.lang;
  const locale = language.toLowerCase().split(/[-_]/)[0];
  const title = titles.get(locale) ?? titles.get("en");
  updateText(entry.querySelector(".item-text"), title);
  updateText(sidebar.querySelector(`ha-tooltip[for="${sidebarEntryId}"]`), title);
}

let timer;
const languageObserver = new MutationObserver(syncSidebar);

function start() {
  if (timer !== undefined) return;

  languageObserver.observe(document.documentElement, {
    attributes: true,
    attributeFilter: ["lang"],
  });
  syncSidebar();
  // The profile locale is a Home Assistant property. A shadow root can also
  // be replaced without notifying an observer outside that root.
  timer = window.setInterval(syncSidebar, 500);
}

window.addEventListener("pageshow", start);
window.addEventListener("pagehide", () => {
  window.clearInterval(timer);
  timer = undefined;
  languageObserver.disconnect();
  sidebarObserver.disconnect();
  observedSidebar = undefined;
});
start();

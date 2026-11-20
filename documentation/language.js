/* Follow only the surrounding page's public language attribute. No HA API or credentials. */
(() => {
  "use strict";
  const settings = document.querySelector("script[data-doc-language]");
  if (!settings) return;
  const current = settings.dataset.docLanguage || "en";
  let targets;
  try { targets = JSON.parse(settings.dataset.docTargets || "{}"); }
  catch (_) { return; }
  const waiting = document.body?.hasAttribute("data-doc-waiting");
  const waitingText = waiting ? [...document.querySelectorAll("[data-waiting-lv][data-waiting-ru]")]
    .map((element) => ({
      element,
      en: element.textContent,
      lv: element.dataset.waitingLv,
      ru: element.dataset.waitingRu,
    })) : [];
  let waitingLanguage = current;
  function selectedLanguage() {
    try {
      if (window.parent !== window) {
        const language = window.parent.document.documentElement.lang;
        if (language) return language.toLowerCase().split(/[-_]/)[0];
      }
    } catch (_) { /* Isolated frames use the English fallback. */ }
    return "en";
  }
  let navigating = false;
  function sync() {
    const selected = selectedLanguage();
    if (waiting) {
      const language = selected === "lv" || selected === "ru" ? selected : "en";
      if (language !== waitingLanguage) {
        for (const text of waitingText) text.element.textContent = text[language];
        document.documentElement.lang = language;
        waitingLanguage = language;
      }
      return;
    }
    const desired = Object.hasOwn(targets, selected) ? selected : "en";
    if (desired === current || !Object.hasOwn(targets, desired) || navigating) return;
    const target = new URL(targets[desired], window.location.href);
    if (target.origin !== window.location.origin) return;
    // Queries and section anchors refer to the previous language and are cleared.
    // replace() avoids a back-button loop between the original and localized page.
    navigating = true;
    window.location.replace(target.href);
  }
  sync();
  window.addEventListener("focus", sync);
  window.addEventListener("pageshow", () => { navigating = false; sync(); });
  let timer = window.setInterval(sync, 1500);
  window.addEventListener("pagehide", () => { window.clearInterval(timer); timer = undefined; });
  window.addEventListener("pageshow", () => {
    if (timer === undefined) timer = window.setInterval(sync, 1500);
  });
})();

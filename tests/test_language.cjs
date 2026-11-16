const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const test = require('node:test');
const source = fs.readFileSync(path.join(__dirname, '../documentation/language.js'), 'utf8');

function harness({ current = 'en', language = 'lv', embedded = true, isolated = false, targets, href } = {}) {
  const parentRoot = { lang: language };
  const handlers = {};
  const navigations = [];
  let tick;
  let starts = 0;
  const document = { querySelector: () => ({ dataset: {
    docLanguage: current,
    docTargets: JSON.stringify(targets || {
      en: current === 'en' ? 'article.html' : '../article.html',
      lv: current === 'lv' ? 'article.html' : current === 'en' ? 'lv/article.html' : '../lv/article.html',
      ru: current === 'ru' ? 'article.html' : current === 'en' ? 'ru/article.html' : '../ru/article.html',
    })
  } }) };
  const window = {
    location: { href: href || `https://ha.example/api/hassio_ingress/test/${current === 'en' ? '' : current + '/'}article.html`, origin: 'https://ha.example', replace: value => navigations.push(value) },
    addEventListener: (name, fn) => { (handlers[name] ||= []).push(fn); },
    setInterval: fn => { tick = fn; return ++starts; }, clearInterval() {},
  };
  window.parent = embedded ? { get document() { if (isolated) throw new Error('Isolated frame'); return { documentElement: parentRoot }; } } : window;
  vm.runInNewContext(source, { document, window, URL });
  return { navigations, parentRoot, tick: () => tick(), starts: () => starts, event: name => (handlers[name] || []).forEach(fn => fn()) };
}

test('follows Latvian and Russian HA profiles including regional language codes', () => {
  for (const language of ['lv', 'lv-LV', 'ru', 'ru_RU']) {
    const state = harness({ language });
    assert.equal(state.navigations[0], `https://ha.example/api/hassio_ingress/test/${language.slice(0, 2)}/article.html`);
  }
});
test('correct language stays on the current article without repeated reloads', () => {
  const state = harness({ current: 'lv' }); state.tick();
  assert.equal(state.navigations.length, 0);
});
test('a language change switches between translations of the current article', () => {
  const state = harness({ current: 'lv' });
  state.parentRoot.lang = 'ru'; state.tick(); state.tick();
  assert.deepEqual(state.navigations, ['https://ha.example/api/hassio_ingress/test/ru/article.html']);
});
test('unsupported languages and inaccessible frames fall back to English', () => {
  for (const options of [{ language: 'de' }, { isolated: true }, { embedded: false }]) {
    const state = harness({ current: 'ru', ...options });
    assert.equal(state.navigations[0], 'https://ha.example/api/hassio_ingress/test/article.html');
  }
});
test('old website packages without translations do not redirect to missing files', () => {
  const state = harness({ targets: { en: 'article.html' } });
  assert.equal(state.navigations.length, 0);
});
test('language switching clears old search queries and translated section anchors', () => {
  const state = harness({ href: 'https://ha.example/api/hassio_ingress/test/article.html?q=old#old-section' });
  assert.equal(state.navigations[0], 'https://ha.example/api/hassio_ingress/test/lv/article.html');
});
test('language targets cannot redirect to an external origin', () => {
  const state = harness({ targets: { en: 'article.html', lv: 'https://other.example/article.html' } });
  assert.equal(state.navigations.length, 0);
});
test('polling resumes after a browser history restore', () => {
  const state = harness({ current: 'lv' });
  state.event('pagehide'); state.event('pageshow');
  assert.equal(state.starts(), 2);
  state.parentRoot.lang = 'en'; state.tick();
  assert.equal(state.navigations[0], 'https://ha.example/api/hassio_ingress/test/article.html');
});

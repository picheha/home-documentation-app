const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const test = require('node:test');
const source = fs.readFileSync(path.join(__dirname, '../documentation/theme.js'), 'utf8');

function harness({ embedded = true, inaccessible = false, saved = null, language = 'en' } = {}) {
  const values = new Map();
  const root = { lang: language, dataset: {}, style: {
    setProperty: (name, value) => values.set(name, value),
    getPropertyValue: name => values.get(name) || '',
    removeProperty: name => values.delete(name),
  } };
  const handlers = {};
  let tick;
  let starts = 0;
  const palette = { '--primary-background-color': '#111111', '--primary-text-color': '#eeeeee', '--primary-color': '#12b3c7' };
  const storage = new Map(saved ? [['piche.documentation.theme', saved]] : []);
  const nodes = [];
  const nav = { append: value => nodes.push(value) };
  const document = {
    documentElement: root, body: {}, readyState: 'complete', addEventListener() {},
    querySelector: () => nav,
    createElement: () => ({
      events: {}, children: [], attributes: {},
      addEventListener(name, callback) { this.events[name] = callback; },
      setAttribute(name, value) { this.attributes[name] = value; },
      append(...children) { this.children.push(...children); },
    }),
  };
  const window = {
    frameElement: embedded ? {} : null,
    addEventListener: (name, handler) => { handlers[name] = handler; },
    setInterval: (fn) => { tick = fn; starts += 1; return starts; },
    clearInterval() {},
    getComputedStyle: () => ({ backgroundColor: ['#ffffff', '#fafafa'].includes(values.get('--doc-background')) ? 'rgb(255, 255, 255)' : 'rgb(17, 17, 17)' }),
    localStorage: {
      getItem: key => storage.get(key) || null,
      setItem: (key, value) => storage.set(key, value),
      removeItem: key => storage.delete(key),
    },
  };
  window.parent = embedded ? { getComputedStyle() {
    if (inaccessible) throw new Error('Cross-origin access denied');
    return { getPropertyValue: name => palette[name] || '' };
  } } : window;
  vm.runInNewContext(source, { document, window });
  return { values, root, palette, handlers, storage, controls: nodes[0].children, tick: () => tick(), starts: () => starts };
}

test('copies actual Home Assistant custom colours and selects dark controls', () => {
  const state = harness();
  assert.equal(state.values.get('--doc-primary'), '#12b3c7');
  assert.equal(state.values.get('--doc-background'), '#111111');
  assert.equal(state.root.dataset.homeAssistantTheme, 'true');
  assert.equal(state.root.style.colorScheme, 'dark');
});
test('tracks a Home Assistant theme change without reloading', () => {
  const state = harness();
  state.palette['--primary-background-color'] = '#ffffff';
  state.palette['--primary-text-color'] = '#222222';
  state.tick();
  assert.equal(state.values.get('--doc-background'), '#ffffff');
  assert.equal(state.values.get('--doc-text'), '#222222');
  assert.equal(state.root.style.colorScheme, 'light');
});
test('standalone and isolated frames leave CSS system-theme fallback intact', () => {
  for (const options of [{ embedded: false }, { inaccessible: true }]) {
    const state = harness(options);
    assert.equal(state.values.size, 0);
    assert.equal(state.root.dataset.homeAssistantTheme, 'false');
  }
});
test('theme updates resume after returning through browser history', () => {
  const state = harness();
  assert.equal(state.starts(), 1);
  state.handlers.pagehide();
  state.handlers.pageshow();
  assert.equal(state.starts(), 2);
});
test('sun/moon button changes mode and remembers the choice', () => {
  const state = harness();
  const [toggle, auto] = state.controls;
  assert.equal(toggle.attributes['aria-label'], 'Switch to light theme');
  assert.equal(auto.hidden, true);
  toggle.events.click();
  assert.equal(state.root.dataset.docThemeMode, 'light');
  assert.equal(state.values.get('--doc-background'), '#fafafa');
  assert.equal(state.storage.get('piche.documentation.theme'), 'light');
  assert.equal(auto.hidden, false);
  toggle.events.click();
  assert.equal(state.root.dataset.docThemeMode, 'dark');
  assert.equal(state.storage.get('piche.documentation.theme'), 'dark');
});
test('manual choice survives theme polling; Auto restores Home Assistant', () => {
  const state = harness({ saved: 'light' });
  assert.equal(state.root.dataset.docThemeMode, 'light');
  state.tick();
  assert.equal(state.root.dataset.docThemeMode, 'light');
  state.controls[1].events.click();
  assert.equal(state.root.dataset.docThemeMode, 'dark');
  assert.equal(state.storage.has('piche.documentation.theme'), false);
  assert.equal(state.controls[1].hidden, true);
});

test('theme controls use the article language for Latvian and Russian', () => {
  for (const [language, expected, autoLabel] of [['lv', 'Pārslēgties uz gaišo tēmu', 'Automātiski'], ['ru', 'Включить светлую тему', 'Авто']]) {
    const state = harness({ language });
    assert.equal(state.controls[0].attributes['aria-label'], expected);
    assert.equal(state.controls[1].textContent, autoLabel);
  }
});

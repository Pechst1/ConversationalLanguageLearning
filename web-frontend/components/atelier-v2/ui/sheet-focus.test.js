/**
 * #197 — a field inside a bottom sheet keeps the learner's typing.
 *
 * The browser walk (CI, 16 Oct; fr + en, A1.1, day 4) failed `day-completes`
 * with `locator.pressSequentially: Timeout`. The screen: La Forge finished, its
 * recap's button opened the reprise sheet on Home («Tâche de reprise», field «La
 * phrase corrigée»). The first keystroke re-rendered the page; the page passes
 * the sheet an inline `onClose`, so the sheet's focus effect ran again and moved
 * focus to its first control, the close button. The next space pressed it and
 * the sheet closed under the learner's typing (inputs=[] on the failing screen).
 *
 * No DOM in this suite (plain node, like the other ui tests), so the component
 * is run under a small hook dispatcher that keeps React's documented rule: an
 * effect runs again only when one of its dependencies changed (Object.is), and
 * its cleanup runs first. The document is a stub with just what the sheet uses.
 *
 * Run: `node --test components/atelier-v2/ui/sheet-focus.test.js`
 */

const assert = require('node:assert/strict');
const path = require('node:path');
const Module = require('node:module');
const test = require('node:test');

const WEB_ROOT = path.resolve(__dirname, '../../..');
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/ts'));
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/tsx'));
const originalResolve = Module._resolveFilename;
Module._resolveFilename = function resolveWithAlias(request, ...rest) {
  if (typeof request === 'string' && request.startsWith('@/')) {
    return originalResolve.call(this, path.join(WEB_ROOT, request.slice(2)), ...rest);
  }
  return originalResolve.call(this, request, ...rest);
};

const React = require('react');
const { BottomSheet, Dialog } = require('./Sheet.tsx');

const internals = React.__SECRET_INTERNALS_DO_NOT_USE_OR_YOU_WILL_BE_FIRED;
const sameDeps = (a, b) => Array.isArray(a) && Array.isArray(b) && a.length === b.length && a.every((x, i) => Object.is(x, b[i]));

/** One mounted component: renders it again and again, committing effects like React. */
function mount(Component) {
  const slots = [];
  let index = 0;
  let pending = [];
  const dispatcher = {
    useRef(initial) {
      const k = index++;
      if (!slots[k]) slots[k] = { current: initial };
      return slots[k];
    },
    useId() {
      index += 1;
      return ':r0:';
    },
    useContext(context) {
      return context._currentValue;
    },
    useCallback(fn, deps) {
      const k = index++;
      if (slots[k] && sameDeps(slots[k].deps, deps)) return slots[k].fn;
      slots[k] = { fn, deps };
      return fn;
    },
    useMemo(make, deps) {
      const k = index++;
      if (slots[k] && sameDeps(slots[k].deps, deps)) return slots[k].value;
      slots[k] = { value: make(), deps };
      return slots[k].value;
    },
    useState(initial) {
      const k = index++;
      if (!slots[k]) slots[k] = { value: typeof initial === 'function' ? initial() : initial };
      return [slots[k].value, () => {}];
    },
    useEffect(effect, deps) {
      const k = index++;
      const previous = slots[k];
      if (previous && deps && sameDeps(previous.deps, deps)) return;
      pending.push({ k, effect, deps });
    },
  };
  dispatcher.useLayoutEffect = dispatcher.useEffect;
  return {
    render(props) {
      index = 0;
      pending = [];
      const saved = internals.ReactCurrentDispatcher.current;
      internals.ReactCurrentDispatcher.current = dispatcher;
      let tree;
      try {
        tree = Component(props);
      } finally {
        internals.ReactCurrentDispatcher.current = saved;
      }
      return {
        tree,
        commit() {
          for (const { k, effect, deps } of pending) {
            if (slots[k] && typeof slots[k].cleanup === 'function') slots[k].cleanup();
            slots[k] = { deps, cleanup: effect() };
          }
        },
      };
    },
  };
}

/** The element in a rendered tree that carries `className`. */
function findByClass(node, className) {
  if (!node || typeof node !== 'object') return null;
  if (Array.isArray(node)) {
    for (const child of node) {
      const hit = findByClass(child, className);
      if (hit) return hit;
    }
    return null;
  }
  if (node.props && node.props.className === className) return node;
  return node.props ? findByClass(node.props.children, className) : null;
}

/** A page with a sheet: a close button first, then the learner's field. */
function stubPage() {
  const listeners = new Set();
  const doc = {
    activeElement: null,
    body: { style: { overflow: '' } },
    addEventListener: (type, fn) => listeners.add(fn),
    removeEventListener: (type, fn) => listeners.delete(fn),
    press(key) {
      for (const fn of [...listeners]) fn({ key, shiftKey: false, stopPropagation() {}, preventDefault() {} });
    },
  };
  const focusable = (name) => {
    const el = { name, offsetParent: {}, focus: () => { doc.activeElement = el; } };
    return el;
  };
  const opener = focusable('the button that opened the sheet');
  const close = focusable('close button');
  const field = focusable('textarea «La phrase corrigée»');
  const sheet = {
    name: 'sheet',
    focus: () => { doc.activeElement = sheet; },
    querySelector: () => close,
    querySelectorAll: () => [close, field],
  };
  return { doc, opener, close, field, sheet };
}

for (const [label, Component, className, extra] of [
  ['BottomSheet', BottomSheet, 'av2-sheet', { title: 'Je suis, tu es : les pronoms et être', children: 'body' }],
  ['Dialog', Dialog, 'av2-dialog', { title: 'Stop here?', actions: null }],
]) {
  test(`${label}: a re-render of the page behind while the learner types keeps focus in the field (#197)`, () => {
    const page = stubPage();
    const previousDocument = global.document;
    global.document = page.doc;
    try {
      page.opener.focus();
      const closes = [];
      const sheet = mount(Component);
      // First render: open. The page behind hands an inline onClose, as atelier.tsx does.
      const first = sheet.render({ open: true, onClose: () => closes.push('first'), ...extra });
      findByClass(first.tree, className).ref.current = page.sheet;
      first.commit();
      assert.equal(page.doc.activeElement, page.close, 'on open, focus moves into the sheet');

      // The learner taps the field and types a letter: the page re-renders with a new onClose.
      page.field.focus();
      sheet.render({ open: true, onClose: () => closes.push('second'), ...extra }).commit();
      assert.equal(
        page.doc.activeElement,
        page.field,
        `after a keystroke focus must stay in the field, not jump to the ${page.doc.activeElement && page.doc.activeElement.name}`,
      );

      // Escape still closes, with the onClose of the latest render.
      page.doc.press('Escape');
      assert.deepEqual(closes, ['second']);
    } finally {
      global.document = previousDocument;
    }
  });
}

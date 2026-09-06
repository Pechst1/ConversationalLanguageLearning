/**
 * Behavioural coverage for the Atelier V2 design system (WP-01).
 *
 * Same harness as `journey.test.js` and `lib/atelier-next.test.js`: a plain
 * node script with `node:assert/strict` and sucrase, so it adds no test
 * framework and no dependency.
 *
 * These are failure-mode tests, not snapshots. What they hold down:
 *
 *   1. the stylesheet's two dark-token blocks cannot drift apart (globals.css
 *      shipped exactly that bug once);
 *   2. every vendored font is actually on disk, licensed, and `swap`;
 *   3. the stylesheet cannot reach a legacy page — every rule is scoped;
 *   4. status is never colour alone;
 *   5. a disabled or graded control keeps its label legible;
 *   6. copy is complete in all three languages and falls back rather than
 *      rendering keys.
 *
 * Run: `node components/atelier-v2/ui/atelier-v2-ui.test.js`
 */

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');

const HERE = __dirname;
const WEB_ROOT = path.resolve(HERE, '../../..');

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
const { renderToStaticMarkup } = require('react-dom/server');

const ui = require('./index.ts');
const {
  atelierCopy,
  atelierChrome,
  normalizeControlLanguage,
  stepOfLabel,
  CONTROL_LANGUAGES,
} = require('@/lib/atelier-v2-copy');

const CSS_PATH = path.join(WEB_ROOT, 'styles/atelier-v2.css');
const css = fs.readFileSync(CSS_PATH, 'utf8');
const render = (element) => renderToStaticMarkup(element);
const h = React.createElement;

// ===========================================================================
// 1. The stylesheet cannot touch a legacy page
// ===========================================================================

{
  // Strip comments, then drop the two at-rule blocks that legitimately have no
  // `.av2` ancestor: @font-face (a resource declaration, not a rule) and
  // @keyframes (whose bodies are percentages, not selectors).
  let bare = css.replace(/\/\*[\s\S]*?\*\//g, '');
  bare = bare.replace(/@font-face\s*\{[^}]*\}/g, '');
  bare = bare.replace(/@keyframes[^{]*\{(?:[^{}]*\{[^{}]*\})*[^{}]*\}/g, '');

  // Everything that remains and opens a rule body is a selector we must check.
  const selectors = [];
  const re = /(^|[};{])\s*([^{}]+?)\s*\{/g;
  let match;
  while ((match = re.exec(bare)) !== null) {
    const selector = match[2].trim();
    // `@media` is a wrapper; the selectors *inside* it are matched separately
    // by the same pass, so the wrapper itself is skipped rather than trusted.
    if (selector.startsWith('@')) continue;
    selectors.push(selector);
  }

  assert.ok(selectors.length > 60, `found ${selectors.length} selectors to check`);

  // Split a selector list on top-level commas only — a comma inside
  // `:where(div, section, …)` is part of one selector, not a separator.
  const topLevelParts = (selector) => {
    const parts = [];
    let depth = 0;
    let current = '';
    for (const char of selector) {
      if (char === '(') depth += 1;
      else if (char === ')') depth -= 1;
      if (char === ',' && depth === 0) {
        parts.push(current);
        current = '';
      } else {
        current += char;
      }
    }
    parts.push(current);
    return parts;
  };

  for (const selector of selectors) {
    for (const part of topLevelParts(selector)) {
      const one = part.trim();
      if (!one) continue;
      assert.ok(
        one.includes('.av2'),
        `every rule must be scoped under .av2, but "${one}" is not`,
      );
    }
  }

  // No bare element or universal reset anywhere.
  assert.ok(!/(^|\n)\s*(html|body|\*)\s*[,{]/.test(bare), 'no bare element or * rule');
  // No :root token block — tokens must not leak into legacy surfaces.
  assert.ok(
    !/(^|[};])\s*:root\s*\{/.test(bare),
    'tokens are never declared on :root, only under .av2',
  );
}

// ===========================================================================
// 2. The two dark-token blocks must stay identical
//
// globals.css shipped this exact bug: its `[data-theme="dark"]` block redefined
// tokens that its `prefers-color-scheme` block did not, so the default "system"
// theme on a dark OS kept light channels. This asserts the V2 blocks agree.
// ===========================================================================

{
  // Comments are stripped from the WHOLE block before splitting: a prose
  // semicolon inside a comment would otherwise cut a declaration in half and
  // silently hide it from this comparison.
  const declarationsOf = (block) => {
    const map = new Map();
    const clean = block.replace(/\/\*[\s\S]*?\*\//g, '');
    for (const line of clean.split(';')) {
      const trimmed = line.trim();
      if (!trimmed.startsWith('--')) continue;
      const [name, ...value] = trimmed.split(':');
      map.set(name.trim(), value.join(':').trim());
    }
    return map;
  };

  const explicit = css.match(
    /:root\[data-theme='dark'\] \.av2:not\(\.av2--light\),\s*\n\.av2--dark \{([\s\S]*?)\n\}/,
  );
  assert.ok(explicit, 'the explicit dark block is present');

  const system = css.match(
    /@media \(prefers-color-scheme: dark\) \{[\s\S]*?:root:not\(\[data-theme\]\) \.av2:not\(\.av2--light\) \{([\s\S]*?)\n  \}/,
  );
  assert.ok(system, 'the prefers-color-scheme dark block is present');

  const a = declarationsOf(explicit[1]);
  const b = declarationsOf(system[1]);

  assert.ok(a.size >= 20, `the dark block declares ${a.size} tokens`);
  assert.deepEqual(
    [...a.keys()].sort(),
    [...b.keys()].sort(),
    'both dark blocks must declare the SAME tokens',
  );
  for (const [name, value] of a) {
    assert.equal(b.get(name), value, `${name} must have the same value in both dark blocks`);
  }

  // The light block must declare every token the dark blocks override, or a
  // dark-only token would be undefined in light mode.
  const light = css.match(/\n\.av2 \{([\s\S]*?)\n\}/);
  assert.ok(light, 'the light token block is present');
  const lightTokens = declarationsOf(light[1]);
  for (const name of a.keys()) {
    assert.ok(lightTokens.has(name), `${name} is overridden in dark but never defined in light`);
  }

  // Semantic roles survive the flip: each accent still has a distinct shadow.
  for (const [face, shadow] of [
    ['--av2-red', '--av2-red-deep'],
    ['--av2-blue', '--av2-blue-deep'],
    ['--av2-yellow', '--av2-yellow-deep'],
    ['--av2-green', '--av2-green-deep'],
    ['--av2-ink', '--av2-ink-deep'],
  ]) {
    assert.notEqual(a.get(face), a.get(shadow), `${face} and ${shadow} differ in dark`);
    assert.notEqual(
      lightTokens.get(face),
      lightTokens.get(shadow),
      `${face} and ${shadow} differ in light`,
    );
  }
}

// ===========================================================================
// 2b. Colour contrast, computed from the tokens themselves
//
// The design is a *visual* source of truth, not an accessibility one: its red
// action with paper-white text measures 4.32:1, under AA for a 17px label. The
// ratios are asserted here from the token values, so a palette tweak that
// breaks a pair fails the build rather than shipping.
// ===========================================================================

{
  const srgb = (channel) => {
    const v = channel / 255;
    return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
  };
  const luminance = (hex) => {
    const clean = hex.trim().replace('#', '');
    const full = clean.length === 3 ? clean.split('').map((c) => c + c).join('') : clean;
    const [r, g, b] = [0, 2, 4].map((i) => parseInt(full.slice(i, i + 2), 16));
    return 0.2126 * srgb(r) + 0.7152 * srgb(g) + 0.0722 * srgb(b);
  };
  const contrast = (a, b) => {
    const [x, y] = [luminance(a), luminance(b)].sort((m, n) => n - m);
    return (x + 0.05) / (y + 0.05);
  };

  const tokensOf = (block) => {
    const map = new Map();
    const clean = block.replace(/\/\*[\s\S]*?\*\//g, '');
    for (const line of clean.split(';')) {
      const trimmed = line.trim();
      if (!trimmed.startsWith('--')) continue;
      const [name, ...value] = trimmed.split(':');
      map.set(name.trim(), value.join(':').trim());
    }
    return map;
  };

  const lightBlock = tokensOf(css.match(/\n\.av2 \{([\s\S]*?)\n\}/)[1]);
  const darkBlock = tokensOf(
    css.match(/:root\[data-theme='dark'\] \.av2:not\(\.av2--light\),\s*\n\.av2--dark \{([\s\S]*?)\n\}/)[1],
  );

  // Every text/ground pair that carries a label a learner has to read.
  const PAIRS = [
    ['--av2-ink', '--av2-paper', 4.5, 'body text on the screen ground'],
    ['--av2-ink', '--av2-card', 4.5, 'body text on a card'],
    ['--av2-ink-2', '--av2-card', 4.5, 'secondary body on a card'],
    ['--av2-muted', '--av2-card', 4.5, 'labels and meta on a card'],
    ['--av2-muted', '--av2-paper', 4.5, 'labels and meta on the ground'],
    ['--av2-on-red', '--av2-red', 4.5, 'the primary action label'],
    ['--av2-on-blue', '--av2-blue', 4.5, 'a story surface label'],
    ['--av2-on-green', '--av2-green', 4.5, 'a correct option label'],
    ['--av2-on-yellow', '--av2-yellow', 4.5, 'a reward label'],
    ['--av2-on-ink', '--av2-ink', 4.5, 'a done-tone action label'],
  ];

  for (const [theme, tokens] of [['light', lightBlock], ['dark', darkBlock]]) {
    for (const [fg, bg, min, what] of PAIRS) {
      const a = tokens.get(fg);
      const b = tokens.get(bg);
      assert.ok(a && b, `${theme}: ${fg} / ${bg} are both defined`);
      const ratio = contrast(a, b);
      assert.ok(
        ratio >= min,
        `${theme}: ${what} (${fg} ${a} on ${bg} ${b}) is ${ratio.toFixed(2)}:1, needs ${min}:1`,
      );
    }

    // The feedback tints are grounds for ink text, so they must clear AA too.
    for (const tint of ['--av2-tint-correct', '--av2-tint-wrong']) {
      const ratio = contrast(tokens.get('--av2-ink'), tokens.get(tint));
      assert.ok(ratio >= 4.5, `${theme}: ink on ${tint} is ${ratio.toFixed(2)}:1`);
    }

    // A focus ring has to be visible against both grounds it can sit on.
    for (const ground of ['--av2-paper', '--av2-card']) {
      const ratio = contrast(tokens.get('--av2-ink'), tokens.get(ground));
      assert.ok(ratio >= 3, `${theme}: the focus ring on ${ground} is ${ratio.toFixed(2)}:1`);
    }
  }
}

// ===========================================================================
// 3. Fonts are vendored, licensed and non-blocking
// ===========================================================================

{
  const faces = [...css.matchAll(/@font-face \{([\s\S]*?)\}/g)].map((m) => m[1]);
  assert.equal(faces.length, 4, 'two families × two subsets');

  for (const face of faces) {
    assert.ok(/font-display: swap;/.test(face), 'every face is font-display: swap');
    const src = face.match(/url\('([^']+)'\)/);
    assert.ok(src, 'every face has a local url');
    assert.ok(src[1].startsWith('/fonts/'), 'self-hosted, never a CDN link');
    const file = path.join(WEB_ROOT, 'public', src[1].replace(/^\//, ''));
    assert.ok(fs.existsSync(file), `${src[1]} exists on disk`);
    assert.ok(fs.statSync(file).size > 5000, `${src[1]} is a real font file`);
    assert.ok(/unicode-range:/.test(face), 'every face declares its subset');
  }

  // No remote font is requested anywhere in the stylesheet.
  assert.ok(!/fonts\.googleapis|fonts\.gstatic/.test(css), 'no Google Fonts request');

  const licence = fs.readFileSync(path.join(WEB_ROOT, 'public/fonts/LICENSE.md'), 'utf8');
  assert.ok(/SIL Open Font License/.test(licence), 'the licence text is shipped');
  assert.ok(/EB Garamond/.test(licence) && /Instrument Sans/.test(licence));
  assert.ok(/PERMISSION & CONDITIONS/.test(licence), 'the full OFL body, not just a link');

  // Both stacks carry a real fallback, so a font failure degrades rather than
  // falling back to the browser default.
  const serif = css.match(/--av2-serif:([^;]+);/)[1];
  const sans = css.match(/--av2-sans:([^;]+);/)[1];
  assert.ok(/serif/.test(serif) && serif.split(',').length >= 3, 'serif stack has fallbacks');
  assert.ok(/sans-serif/.test(sans) && sans.split(',').length >= 3, 'sans stack has fallbacks');
}

// ===========================================================================
// 4. Type scales with the learner's text-size setting
// ===========================================================================

{
  const light = css.match(/\n\.av2 \{([\s\S]*?)\n\}/)[1];
  const typeTokens = [...light.matchAll(/--av2-t-[\w-]+:\s*([^;]+);/g)].map((m) => m[1].trim());
  assert.ok(typeTokens.length >= 9, 'the whole type scale is tokenised');
  for (const value of typeTokens) {
    assert.ok(/rem$/.test(value), `type must be rem so the text-size setting moves it: ${value}`);
  }

  // The form field never drops under 16px, which is what makes iOS zoom the
  // viewport on focus.
  assert.equal(light.match(/--av2-t-body-lg:\s*([^;]+);/)[1].trim(), '1rem');
  assert.ok(/font-size: var\(--av2-t-body-lg\)/.test(css), 'the field uses it');
}

// ===========================================================================
// 5. Touch targets, overflow and motion
// ===========================================================================

{
  assert.ok(/--av2-tap: 44px;/.test(css), 'the 44px floor is a token');
  // Every interactive primitive is at least the tap floor.
  for (const rule of ['.av2-btn {', '.av2-choice {', '.av2-tile {', '.av2-icon-btn {', '.av2-tab {']) {
    const start = css.indexOf(rule);
    assert.ok(start > 0, `${rule} exists`);
    const body = css.slice(start, css.indexOf('}', start));
    assert.ok(
      /min-height: (max\(var\(--av2-tap\)|var\(--av2-tap\))/.test(body) ||
        /height: var\(--av2-tap\)/.test(body),
      `${rule} reaches the 44px floor`,
    );
  }

  // D-6: the grid/flex `min-width: auto` default is zeroed once, globally
  // within the scope. This is the defect that clipped the primary action at
  // 320px with 200% text.
  assert.ok(
    /\.av2 :where\(div, section, header, footer, main, li, p, label, button, a, span\) \{\s*min-width: 0;/.test(
      css,
    ),
    'min-width:auto is zeroed for every flex/grid child in scope',
  );
  assert.ok(/white-space: normal;/.test(css), 'action labels wrap rather than widen the row');

  assert.ok(
    /@media \(prefers-reduced-motion: reduce\)/.test(css),
    'reduced motion is respected',
  );
  assert.ok(/:focus-visible \{\s*outline: 3px solid/.test(css), 'focus is visible');
}

// ===========================================================================
// 6. Status is never colour alone
// ===========================================================================

{
  const statusLabels = { selected: 'Selected', correct: 'Correct', wrong: 'Not yet' };
  const options = [
    { id: 'a', textFr: 'elle réussira', state: 'correct' },
    { id: 'b', textFr: 'elle a réussi', state: 'wrong' },
    { id: 'c', textFr: 'elle réussit' },
  ];

  const html = render(
    h(ui.ChoiceList, {
      options,
      selectedId: 'b',
      label: 'Choose one',
      disabled: true,
      onSelect: () => {},
      statusLabels,
    }),
  );

  // The verdict survives greyscale and a screen reader.
  assert.ok(html.includes('Correct'), 'the correct option says so in words');
  assert.ok(html.includes('Not yet'), 'the wrong option says so in words');
  assert.ok(html.includes('av2-sr'), 'the words are available to assistive tech');
  assert.ok(html.includes('data-state="correct"') && html.includes('data-state="wrong"'));

  // A graded option is locked but still fully readable.
  assert.ok(html.includes('disabled=""'), 'graded options lock');
  for (const option of options) {
    assert.ok(html.includes(option.textFr.replace(/é/g, 'é')), 'a locked option stays legible');
  }
  const choiceRule = css.slice(css.indexOf('.av2-choice:disabled'), css.indexOf('.av2-choice__dot'));
  assert.ok(/opacity: 1;/.test(choiceRule), 'a disabled option is never dimmed');

  // A disabled button dims its FACE, never its label.
  const btnDisabled = css.slice(
    css.indexOf('.av2-btn:disabled'),
    css.indexOf('.av2-btn--quiet:disabled'),
  );
  assert.ok(!/opacity/.test(btnDisabled), 'a disabled action is not made unreadable with opacity');

  // Feedback tones each carry a glyph as well as a colour.
  for (const tone of ['correct', 'supported', 'wrong', 'neutral']) {
    const band = render(h(ui.FeedbackBand, { tone, title: `title-${tone}` }));
    assert.ok(band.includes(`data-tone="${tone}"`));
    assert.ok(band.includes('<svg'), `${tone} carries a glyph, not only a colour`);
    assert.ok(band.includes(`title-${tone}`), `${tone} states its verdict in words`);
  }
}

// ===========================================================================
// 7. Pending and busy states
// ===========================================================================

{
  const pending = render(
    h(ui.Action, { tone: 'primary', pending: true, pendingLabel: 'Working' }, 'Send'),
  );
  assert.ok(pending.includes('aria-busy="true"'), 'a pending action is announced as busy');
  assert.ok(pending.includes('disabled=""'), 'and cannot queue a second mutation');
  assert.ok(pending.includes('Working') && !pending.includes('>Send<'), 'and says what it is doing');

  const idle = render(h(ui.Action, { tone: 'primary' }, 'Send'));
  assert.ok(!idle.includes('aria-busy'), 'an idle action is not busy');
  assert.ok(!idle.includes('disabled'), 'and is pressable');

  const icon = render(h(ui.IconAction, { label: 'Record' }, null));
  assert.ok(icon.includes('aria-label="Record"'), 'an icon-only control has a name');
}

// ===========================================================================
// 8. Progress never invents a number
// ===========================================================================

{
  const known = render(h(ui.ProgressRule, { value: 2, max: 5, label: 'Progress' }));
  assert.ok(known.includes('aria-valuenow="2"') && known.includes('aria-valuemax="5"'));
  assert.ok(known.includes('width:40%'), 'the fill is the real fraction');

  // No plan yet is NOT "you have done none of it".
  const unknown = render(h(ui.ProgressRule, { value: 0, max: 0, label: 'Progress' }));
  assert.ok(!unknown.includes('aria-valuenow'), 'an unknown plan reports no value at all');
  assert.ok(unknown.includes('role="progressbar"'));

  // Segments only ever exist for real planned steps.
  assert.equal(render(h(ui.StepProgress, { steps: [], label: 'Progress' })), '');
  const segments = render(
    h(ui.StepProgress, {
      label: 'Progress',
      steps: [
        { id: '1', state: 'done' },
        { id: '2', state: 'active' },
        { id: '3', state: 'pending' },
      ],
    }),
  );
  // The closing quote matters: `av2-progress__segments` (the container) also
  // contains `av2-progress__segment` as a substring.
  assert.equal((segments.match(/av2-progress__segment"/g) || []).length, 3);
  assert.ok(segments.includes('aria-valuenow="1"') && segments.includes('aria-valuemax="3"'));
}

// ===========================================================================
// 9. Artwork fails gracefully
// ===========================================================================

{
  const missing = render(h(ui.Artwork, { url: null, alt: '', fallbackLabel: 'No illustration' }));
  assert.ok(!missing.includes('<img'), 'no image element without a source');
  assert.ok(missing.includes('role="img"') && missing.includes('No illustration'));

  const present = render(
    h(ui.Artwork, { url: '/media/x.png', alt: 'A café terrace', fallbackLabel: 'No illustration' }),
  );
  assert.ok(present.includes('<img') && present.includes('alt="A café terrace"'));
  assert.ok(present.includes('loading="lazy"'));
  // 16:9 is reserved either way, so resolving the image does not reflow the step.
  assert.ok(/\.av2-art \{[^}]*aspect-ratio: 16 \/ 9/.test(css));
  assert.ok(/\.av2-art__fallback \{[^}]*aspect-ratio: 16 \/ 9/.test(css));
}

// ===========================================================================
// 10. Character portraits reuse the world-bible tokens
// ===========================================================================

{
  assert.equal(ui.characterAccent('Marin'), 'var(--char-marin, #2c6a5d)');
  assert.equal(ui.characterAccent('Monsieur Marchand'), 'var(--char-marchand, #5b5346)');
  assert.equal(ui.characterAccent('Romy'), 'var(--char-romy, #1d3a8a)');
  // An unknown character does not get a colour picked for it.
  assert.equal(ui.characterAccent('Quelqu’un'), undefined);
  assert.equal(ui.characterAccent(null), undefined);
  assert.equal(ui.characterAccent(''), undefined);

  const portrait = render(h(ui.Portrait, { name: 'Marin' }));
  assert.ok(portrait.includes('--av2-char'), 'the accent is applied as a token, not a hex');
  assert.ok(portrait.includes('>M<'), 'the initial is drawn');
  assert.ok(portrait.includes('aria-hidden="true"'), 'the avatar is decorative; the name is text');
}

// ===========================================================================
// 11. Overlays are real dialogs
// ===========================================================================

{
  const sheet = render(
    h(ui.BottomSheet, { open: true, title: 'The rule', onClose: () => {} }, 'body'),
  );
  assert.ok(sheet.includes('role="dialog"') && sheet.includes('aria-modal="true"'));
  assert.ok(sheet.includes('aria-labelledby'), 'the sheet is named by its own title');
  assert.ok(sheet.includes('av2-sheet__handle'), 'one handle, shared by every sheet');
  assert.ok(sheet.includes('tabindex="-1"'), 'focus has somewhere to land');
  assert.equal(
    render(h(ui.BottomSheet, { open: false, title: 'x', onClose: () => {} }, 'b')),
    '',
    'a closed sheet renders nothing',
  );

  const dialog = render(
    h(ui.Dialog, { open: true, title: 'Stop here?', body: 'Body', onClose: () => {}, actions: null }),
  );
  assert.ok(dialog.includes('aria-describedby'), 'the dialog body is associated with it');
  assert.ok(dialog.includes('role="dialog"'));

  // Safe area and the design's own sheet geometry.
  assert.ok(/--av2-safe-bottom: max\(20px, env\(safe-area-inset-bottom\)\);/.test(css));
  assert.ok(/\.av2-sheet \{[\s\S]*?border-radius: var\(--av2-r-sheet\) var\(--av2-r-sheet\) 0 0;/.test(css));
  assert.ok(/rgba\(20, 17, 13, 0\.35\)/.test(css), "the design's own scrim");
}

// ===========================================================================
// 12. Navigation
// ===========================================================================

{
  const tabs = ['atelier', 'missions', 'serial', 'notebook'].map((key) => ({
    key,
    label: key,
    onSelect: () => {},
  }));
  const nav = render(h(ui.TabBar, { tabs, active: 'missions', label: 'Sections' }));
  assert.equal((nav.match(/class="av2-tab"/g) || []).length, 4, 'four tabs');
  assert.equal(
    (nav.match(/aria-current="page"/g) || []).length,
    1,
    'the active tab is exposed semantically, not only as a colour',
  );
  assert.ok(nav.includes('aria-label="Sections"'), 'the nav is named');
}

// ===========================================================================
// 13. Copy — complete, localized, and falling back rather than showing keys
// ===========================================================================

{
  const keys = Object.keys(atelierChrome('en'));
  assert.ok(keys.length > 40, `${keys.length} chrome keys`);

  for (const language of CONTROL_LANGUAGES) {
    const table = atelierChrome(language);
    assert.deepEqual(Object.keys(table).sort(), keys.slice().sort(), `${language} has every key`);
    for (const key of keys) {
      assert.equal(typeof table[key], 'string', `${language}.${key} is a string`);
      // `artwork_decorative` is intentionally empty: it marks an image decorative.
      if (key !== 'artwork_decorative') {
        assert.ok(table[key].trim().length > 0, `${language}.${key} is not empty`);
      }
    }
  }

  // Action names are really localized, not English under a translated heading.
  const actionKeys = keys.filter((key) => key.startsWith('action_') || key.startsWith('record_'));
  assert.ok(actionKeys.length >= 6, 'there are action names to check');
  for (const key of actionKeys) {
    assert.notEqual(
      atelierChrome('de')[key],
      atelierChrome('en')[key],
      `de.${key} must be German, not the English label`,
    );
    assert.notEqual(
      atelierChrome('fr')[key],
      atelierChrome('en')[key],
      `fr.${key} must be French, not the English label`,
    );
  }

  // Normalization: regional tags, casing, whitespace, separators, junk.
  assert.equal(normalizeControlLanguage('de'), 'de');
  assert.equal(normalizeControlLanguage('de-DE'), 'de');
  assert.equal(normalizeControlLanguage('de_AT'), 'de');
  assert.equal(normalizeControlLanguage('  FR-ca '), 'fr');
  assert.equal(normalizeControlLanguage('EN'), 'en');
  assert.equal(normalizeControlLanguage('pt'), 'en', 'an unsupported language falls back');
  assert.equal(normalizeControlLanguage(null), 'en');
  assert.equal(normalizeControlLanguage(undefined), 'en');
  assert.equal(normalizeControlLanguage(42), 'en');
  assert.equal(normalizeControlLanguage(''), 'en');

  // The merged table carries the journey contract keys too, so a renderer
  // needs exactly one copy object.
  const merged = atelierCopy('fr');
  assert.equal(typeof merged.start, 'string', 'journey keys are present');
  assert.equal(typeof merged.action_check, 'string', 'chrome keys are present');
  assert.equal(merged.action_check, 'Vérifier');
  assert.equal(atelierCopy('pt').action_check, atelierCopy('en').action_check);

  // Interpolation happens in the learner's language.
  assert.equal(stepOfLabel(atelierCopy('en'), 2, 5), 'Step 2 of 5');
  assert.equal(stepOfLabel(atelierCopy('de'), 2, 5), 'Schritt 2 von 5');
  assert.equal(stepOfLabel(atelierCopy('fr'), 2, 5), 'Étape 2 sur 5');
}

// ===========================================================================
// 14. The root is the only scope boundary
// ===========================================================================

{
  const html = render(h(ui.AtelierV2Root, { language: 'de' }, 'x'));
  assert.ok(html.includes('class="av2"'), 'the root applies the scope class');
  assert.ok(!html.includes('av2--dark'), 'and does not force a theme');

  const forced = render(h(ui.AtelierV2Root, { language: 'de', forceTheme: 'dark' }, 'x'));
  assert.ok(forced.includes('av2--dark'), 'the gallery can force dark');

  // Theme comes from the attribute the app already writes, so there is no
  // client-only branch to mismatch on hydration.
  assert.ok(/:root\[data-theme='dark'\] \.av2:not\(\.av2--light\)/.test(css));
  assert.ok(/:root\[data-theme='system'\] \.av2:not\(\.av2--light\)/.test(css));

  const light = render(h(ui.AtelierV2Root, { language: 'de', forceTheme: 'light' }, 'x'));
  assert.ok(light.includes('av2--light'), 'the gallery can force light on a dark OS');
  assert.ok(!light.includes('av2--dark'));
}

console.log('atelier v2 design system tests passed');

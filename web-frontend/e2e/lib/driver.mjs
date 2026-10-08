// A screen-reading driver for the daily journey: it looks at what is on the phone-sized
// page, decides what a learner would do next, does it, and records every distinct screen.

export const SNAPSHOT_FN = () => {
  const vis = (el) => {
    const r = el.getBoundingClientRect();
    const s = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none';
  };
  const q = (sel) => [...document.querySelectorAll(sel)].filter(vis);
  const buttons = q('button, a[role=button], [role=button]').map((el) => ({
    text: (el.innerText || el.getAttribute('aria-label') || '').trim().replace(/\s+/g, ' '),
    cls: el.className && el.className.toString ? el.className.toString() : '',
    disabled: !!el.disabled || el.getAttribute('aria-disabled') === 'true',
    y: Math.round(el.getBoundingClientRect().top),
    h: Math.round(el.getBoundingClientRect().height),
  }));
  const frOnly = (root) => {
    const clone = root.cloneNode(true);
    clone.querySelectorAll('[lang=fr], script, style').forEach((n) => n.remove());
    return (clone.innerText || '').replace(/\s+/g, ' ').trim();
  };
  const main = document.querySelector('main') || document.body;
  return {
    url: location.pathname + location.search,
    text: (main.innerText || '').replace(/\s+/g, ' ').trim(),
    nonFrText: frOnly(main),
    buttons,
    choices: q('.av2-choice').length,
    whoSaid: q('.av2-who-said__card').length,
    tiles: q('.av2-tiles__bank button.av2-tile, .av2-tiles__bank .av2-tile:not(.av2-tile--mould)').length,
    tilesBox: q('.av2-tiles').length,
    textarea: q('textarea, input[type=text], input:not([type])').length,
    dictation: q('.av2-dictation, [data-step=dictation]').length,
    match: q('.av2-match__card').length,
    goal: q('[data-goal]').map((n) => n.innerText.trim()),
    bodyLg: q('.av2-body--lg').map((n) => n.innerText.trim()),
    headline: q('.av2-headline').map((n) => n.innerText.trim()),
    stepLabel: (q('.av2-label')[0] || {}).innerText || '',
    dataStep: q('[data-step]').map((n) => n.getAttribute('data-step')),
    graded: q('.av2-graded').map((n) => ({ state: n.getAttribute('data-state'), text: n.innerText.trim() })),
    connection: q('.journey-connection').map((n) => n.getAttribute('data-state')),
    dataStates: q('[data-state]').map((n) => n.getAttribute('data-state')),
    reader: q('.fr-next').map((n) => {
      const r = n.getBoundingClientRect();
      return { x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height), disabled: !!n.disabled, text: n.innerText.trim() };
    }),
    thread: q('.av2-step--thread').length,
    recap: document.querySelectorAll('.journey-recap, .av2-reward').length,
    castIntro: q('.cast-intro__member').length,
    // Home once the day is done («Done for today» / «Fini pour aujourd'hui» / «Für heute»).
    homeDone: location.pathname.startsWith('/atelier') && /Done for today|Fini pour aujourd|Journée bouclée|Für heute (fertig|geschafft|erledigt)/i.test((document.querySelector('main') || document.body).innerText || ''),
    forgeStep: q('[data-step=forge]').length,
    // A request the screen says is in flight (Action's `pending`: disabled,
    // aria-busy, «La scène se prépare…»): waiting, not stuck.
    pending: document.querySelector('[data-pending="true"], [aria-busy="true"]') !== null,
    epFeedback: q('.ep-feedback').map((n) => ({ verdict: n.getAttribute('data-verdict'), text: n.innerText.trim() })),
    frTexts: q('[lang=fr]').map((n) => n.innerText.trim()).filter(Boolean),
    threadCue: (q('.av2-thread__cue')[0] || {}).innerText || '',
    fieldEnabled: q('textarea, input[type=text]').some((n) => !n.disabled && !n.readOnly),
    theme: document.documentElement.getAttribute('data-theme'),
    scrollW: document.documentElement.scrollWidth,
    innerW: window.innerWidth,
  };
};

export async function snapshot(page) {
  return page.evaluate(SNAPSHOT_FN);
}

export const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

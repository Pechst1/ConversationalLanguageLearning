/**
 * Le mur du Mistral · the café's wall, where every object the season has handed the learner
 * hangs in its frame, in the story's order (lib/season-wall.ts).
 *
 * The hooks still to come show their part number and nothing else. Tap an object and its person
 * hands it over again, in their own «montre», with the line they said; the object shows the
 * choice the learner made about it (the Polaroid pinned to the wall or under the till tray, Gus's
 * note on the petition), and the page it came from is one tap away.
 */
import Link from 'next/link';
import React from 'react';

import { AtelierV2Root } from '@/components/atelier-v2/ui';
import { readCameoItems } from '@/lib/cameo';
import type { CameoLang } from '@/lib/cameo';
import { useLearnerLanguage } from '@/lib/learner-language';
import {
  EMPTY_WALL,
  markLine,
  marksFor,
  rereadHref,
  toCameoLang,
  WALL_COPY,
  wallHooks,
  wallText,
} from '@/lib/season-wall';
import type { SeasonWall, WallHook } from '@/lib/season-wall';
import apiService from '@/services/api';

import { VivantFigure } from '../vivant/VivantFigure';
import { figureFor } from '../vivant/registry';
import { faceFor, handoverAt, itemOffer } from './offer';
import { PLOT_ITEM_CSS, PlotItem } from './PlotItem';
import type { ItemMarks } from './PlotItem';

/** The wall as the server reads it, with what this device was handed itself. */
export function useSeasonWall(): { wall: SeasonWall; hooks: WallHook[]; loaded: boolean } {
  const [wall, setWall] = React.useState<SeasonWall>(EMPTY_WALL);
  const [device, setDevice] = React.useState<string[]>([]);
  const [loaded, setLoaded] = React.useState(false);
  React.useEffect(() => {
    let alive = true;
    setDevice(readCameoItems());
    apiService
      .get<SeasonWall>('/serial/season/wall', { suppressGlobalError: true } as Record<string, unknown>)
      .then((body) => {
        if (alive && body && typeof body === 'object') setWall({ ...EMPTY_WALL, ...body, marks: body.marks ?? {} });
      })
      .catch(() => undefined)
      .finally(() => {
        if (alive) setLoaded(true);
      });
    return () => {
      alive = false;
    };
  }, []);
  const hooks = React.useMemo(() => wallHooks(wall, device), [wall, device]);
  return { wall, hooks, loaded };
}

function Gloss({ text, lang }: { text: string; lang: CameoLang }) {
  if (lang === 'fr') return null;
  return <span className="mur-gloss">{text}</span>;
}

function Frame({ hook, marks, lang, onOpen }: { hook: WallHook; marks: ItemMarks; lang: CameoLang; onOpen: () => void }) {
  if (!hook.owned) {
    return (
      <div className="mur-hook mur-hook--empty" aria-label={wallText(WALL_COPY.to_come, lang, { n: hook.number })}>
        <span className="mur-nail" aria-hidden="true" />
        <span className="mur-blank" aria-hidden="true">
          T{hook.number}
        </span>
      </div>
    );
  }
  return (
    <button type="button" className="mur-hook" data-item={hook.item.id} onClick={onOpen} aria-label={hook.item.name.fr}>
      <span className="mur-nail" aria-hidden="true" />
      <span className="mur-frame">
        <PlotItem id={hook.item.id} size={84} still css="none" marks={marksFor(hook.item, marks)} />
      </span>
      <span className="mur-name" lang="fr">
        {hook.item.name.fr}
      </span>
    </button>
  );
}

function HandOver({ hook, marks, lang, onClose }: { hook: WallHook; marks: ItemMarks; lang: CameoLang; onClose: () => void }) {
  const [take, setTake] = React.useState(0);
  const close = React.useRef<HTMLButtonElement>(null);
  React.useEffect(() => {
    close.current?.focus();
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);
  const { item } = hook;
  const own = marksFor(item, marks);
  const fig = figureFor(item.carrier);
  const offer = fig ? itemOffer(fig.key, item.id, item.mood, own) : null;
  const at = handoverAt(fig, item.id) ?? 0;
  const mark = markLine(item, marks);
  const headingId = `mur-sheet-${item.id}`;
  return (
    <div className="mur-sheet-wrap" role="presentation" onClick={onClose}>
      <div className="mur-sheet" role="dialog" aria-modal="true" aria-labelledby={headingId} onClick={(event) => event.stopPropagation()}>
        <div className="mur-sheet__top">
          <span className="mur-kicker">T{hook.number}</span>
          <button ref={close} type="button" className="mur-close" onClick={onClose} aria-label={wallText(WALL_COPY.close, lang)}>
            ×
          </button>
        </div>
        <div className="mur-stage" key={take}>
          {fig ? (
            <VivantFigure
              id={item.carrier}
              gesture="montre"
              expression={offer?.face ?? faceFor(item.mood)}
              offer={offer ?? undefined}
              crop="full"
              size={150}
              label=""
              className="mur-figure"
            />
          ) : null}
          <span className="mur-landed" style={{ animationDelay: `${at}ms` }}>
            <PlotItem id={item.id} size={104} css="none" marks={own} />
          </span>
        </div>
        <h2 id={headingId} className="mur-sheet__name" lang="fr">
          {item.name.fr}
        </h2>
        <Gloss text={wallText(item.name, lang)} lang={lang} />
        <p className="mur-line" lang="fr">
          «{item.line.fr}»
        </p>
        <Gloss text={wallText(item.line, lang)} lang={lang} />
        {fig ? <p className="mur-who">{fig.name}</p> : null}
        {mark ? (
          <p className="mur-mark">
            <span lang="fr">{mark.fr}</span>
            <Gloss text={wallText(mark, lang)} lang={lang} />
          </p>
        ) : null}
        <div className="mur-actions">
          <button type="button" className="mur-btn mur-btn--ink" onClick={() => setTake((n) => n + 1)}>
            {wallText(WALL_COPY.replay, lang)}
          </button>
          {hook.page ? (
            <Link className="mur-btn" href={rereadHref(hook.page)}>
              {wallText(WALL_COPY.reread, lang)}
            </Link>
          ) : null}
        </div>
      </div>
    </div>
  );
}

export function MurDuMistral() {
  const lang = toCameoLang(useLearnerLanguage());
  const { wall, hooks, loaded } = useSeasonWall();
  const [open, setOpen] = React.useState<string | null>(null);
  const owned = hooks.filter((hook) => hook.owned).length;
  const current = hooks.find((hook) => hook.item.id === open && hook.owned) ?? null;
  return (
    <AtelierV2Root as="main" language={lang} className="mur" aria-label={WALL_COPY.title}>
      <style dangerouslySetInnerHTML={{ __html: PLOT_ITEM_CSS + MUR_CSS }} />
      <header className="mur-head">
        <Link className="mur-back" href="/atelier">
          ← {wallText(WALL_COPY.back, lang)}
        </Link>
        <h1 className="mur-title">{WALL_COPY.title}</h1>
        <p className="mur-deck">{wallText(WALL_COPY.deck, lang)}</p>
        {hooks.length ? <p className="mur-count">{wallText(WALL_COPY.count, lang, { n: owned, total: hooks.length })}</p> : null}
      </header>
      <section className="mur-wall" aria-label={WALL_COPY.title} data-loaded={loaded || undefined}>
        <div className="mur-molding" aria-hidden="true" />
        {hooks.length ? (
          <div className="mur-grid">
            {hooks.map((hook) => (
              <Frame key={hook.item.id} hook={hook} marks={wall.marks} lang={lang} onOpen={() => setOpen(hook.item.id)} />
            ))}
          </div>
        ) : loaded ? (
          <p className="mur-empty">{wallText(WALL_COPY.empty, lang)}</p>
        ) : null}
        <div className="mur-banquette" aria-hidden="true" />
      </section>
      {current ? <HandOver hook={current} marks={wall.marks} lang={lang} onClose={() => setOpen(null)} /> : null}
    </AtelierV2Root>
  );
}

/* The wall itself is an illustration (plaster, wood, the teal banquette) and keeps its colours
 * in the dark; the page around it follows the theme. */
export const MUR_CSS = `
.mur { display: block; max-width: 560px; margin: 0 auto; padding: 16px 16px 40px; box-sizing: border-box; }
.mur-head { display: grid; gap: 4px; margin-bottom: 16px; }
.mur-back { font-size: 14px; color: inherit; opacity: .7; text-decoration: none; min-height: 44px; display: inline-flex; align-items: center; width: max-content; }
.mur-title { font-family: var(--app-serif, Georgia, serif); font-size: 34px; line-height: 1.05; margin: 0; font-weight: 600; }
.mur-deck { margin: 0; font-size: 16px; line-height: 1.45; opacity: .8; }
.mur-count { margin: 4px 0 0; font-size: 12px; font-weight: 600; letter-spacing: .08em; text-transform: uppercase; opacity: .6; }
.mur-wall { position: relative; background: #efe4cc; border-radius: 18px; overflow: hidden; padding: 30px 0 0; color: #14110d; }
.mur-molding { position: absolute; left: 0; right: 0; top: 0; height: 12px; background: #c9b48c; }
.mur-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 20px 12px; padding: 0 14px 24px; }
@media (min-width: 480px) { .mur-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); } }
.mur-hook { display: flex; flex-direction: column; align-items: center; gap: 6px; background: none; border: 0; padding: 0; font: inherit; color: inherit; cursor: pointer; min-height: 44px; }
.mur-hook:focus-visible .mur-frame { outline: 3px solid #b0260f; outline-offset: 3px; }
.mur-nail { width: 7px; height: 7px; border-radius: 50%; background: #3d3832; }
.mur-hook--empty .mur-nail { background: #a59e8f; }
.mur-frame { display: flex; align-items: center; justify-content: center; width: 112px; height: 112px; box-sizing: border-box; padding: 7px; background: #2a231c; border-radius: 4px; box-shadow: 0 6px 14px rgba(20, 17, 13, .18); }
.mur-frame .plot-item { background: #f8f3e8; width: 100%; height: 100%; padding: 4px; box-sizing: border-box; }
.mur-hook:active .mur-frame { transform: rotate(-2deg); }
.mur-name { font-family: var(--app-serif, Georgia, serif); font-style: italic; font-size: 15px; line-height: 1.2; text-align: center; }
.mur-blank { display: flex; align-items: center; justify-content: center; width: 112px; height: 86px; border-radius: 4px; background: #e3d6b9; color: #8a8270; font-size: 13px; font-weight: 600; letter-spacing: .06em; }
.mur-empty { margin: 8px 20px 28px; font-size: 16px; line-height: 1.45; }
.mur-banquette { height: 46px; background: #2c6a5d; border-top: 6px solid #1f4f45; }
.mur-sheet-wrap { position: fixed; inset: 0; z-index: 60; background: rgba(20, 17, 13, .55); display: flex; align-items: flex-end; justify-content: center; }
.mur-sheet { width: 100%; max-width: 480px; max-height: 92vh; overflow-y: auto; box-sizing: border-box; background: #f8f3e8; color: #14110d; border-radius: 24px 24px 0 0; padding: 14px 20px 26px; display: grid; gap: 6px; animation: mur-up 320ms cubic-bezier(.2, 1.1, .4, 1) both; }
.mur-sheet__top { display: flex; align-items: center; justify-content: space-between; }
.mur-kicker { font-size: 12px; font-weight: 600; letter-spacing: .1em; color: #8a8270; }
.mur-close { width: 44px; height: 44px; border: 0; border-radius: 22px; background: #ebe2cf; color: #14110d; font-size: 24px; line-height: 1; cursor: pointer; }
.mur-stage { display: flex; align-items: flex-end; justify-content: center; gap: 4px; min-height: 230px; }
.mur-figure { flex: none; }
.mur-landed { display: block; margin-bottom: 18px; animation: mur-landed 560ms cubic-bezier(.2, 1.35, .4, 1) both; }
.mur-sheet__name { margin: 4px 0 0; font-family: var(--app-serif, Georgia, serif); font-size: 26px; font-weight: 600; }
.mur-line { margin: 4px 0 0; font-family: var(--app-serif, Georgia, serif); font-style: italic; font-size: 19px; line-height: 1.3; }
.mur-gloss { display: block; font-size: 14px; color: #6f6857; }
.mur-who { margin: 0; font-size: 13px; color: #6f6857; }
.mur-mark { margin: 8px 0 0; padding: 10px 12px; background: #efe4cc; border-radius: 12px; font-size: 15px; line-height: 1.4; display: grid; gap: 2px; }
.mur-actions { display: flex; gap: 8px; margin-top: 10px; }
.mur-btn { flex: 1 1 0; min-height: 44px; display: inline-flex; align-items: center; justify-content: center; text-align: center; padding: 0 14px; border-radius: 22px; border: 0; background: #ebe2cf; color: #14110d; font: inherit; font-weight: 600; font-size: 15px; text-decoration: none; cursor: pointer; }
.mur-btn--ink { background: #14110d; color: #f8f3e8; }
@keyframes mur-up { from { transform: translateY(40px); opacity: 0; } to { transform: none; opacity: 1; } }
@keyframes mur-landed { from { opacity: 0; transform: translate(-48px, 14px) scale(.45) rotate(-14deg); } to { opacity: 1; transform: none; } }
@media (prefers-reduced-motion: reduce) {
  .mur-sheet, .mur-landed { animation: none; }
}
`;

export default MurDuMistral;

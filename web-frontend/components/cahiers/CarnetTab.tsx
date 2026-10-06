/**
 * WP-95 «Le Carnet» — what you can do in French, one page per sub-band.
 *
 * A Cahier tab beside «Relevé» (`/notebook?mode=carnet`): the Relevé is the
 * ledger of what went wrong, the Carnet the ledger of what you can do, and
 * both are records the learner reads rather than work to do. Home's next-step
 * line and the Dossier link here.
 *
 * Each can-do of the band is a row. Unstamped: a quiet dotted disc and «Pas
 * encore». Stamped the first time the story showed it: a small pressed Seal,
 * «Un café au Mistral — Margaux, 28 sept.» with the character's xs face, and
 * the learner's own words in Garamond italic. «Essayez-le pour de vrai» opens
 * Répétition (WP-31) with the can-do as the situation. Other sub-bands are one
 * tap away; future ones are shown calmly, locked, with what waits there.
 *
 * No gauge: the count is a line of text, and the seals are the only marks.
 * Every decision is in `lib/can-dos.ts` (`carnetModel`), which the node suite pins.
 */

import React from 'react';
import Link from 'next/link';

import { Action, Skeleton } from '@/components/atelier-v2/ui';
import { useControlLanguage } from '@/components/atelier-v2/ui/AtelierV2Root';
import { CastPortrait } from '@/components/atelier-v2/ui/CastPortrait';
import { SealMini, sealForEdition } from '@/components/ui/Seal';
import { canDoCopy } from '@/lib/can-do-copy';
import { carnetModel, readCanDos, type CanDosPayload, type CarnetModel } from '@/lib/can-dos';
import { frenchQuote, frenchSpacing } from '@/lib/french-typography';
import api from '@/services/api';
import type { ControlLanguage } from '@/types/daily-journey';

export function CarnetView({
  model,
  language,
  onSelectBand,
}: {
  model: CarnetModel;
  language: ControlLanguage;
  onSelectBand?: (band: string) => void;
}) {
  const copy = canDoCopy(language);
  const selected = model.selected;
  if (!selected) {
    return (
      <section className="av2-carnet" aria-label={copy.carnet_name} data-carnet="empty">
        <p className="av2-body av2-body--lg">{copy.carnet_empty}</p>
      </section>
    );
  }
  return (
    <section className="av2-carnet" aria-labelledby="av2-carnet-title" data-carnet={selected.band}>
      <div className="av2-stack">
        <p className="av2-label">
          <span id="av2-carnet-title" lang="fr">
            {copy.carnet_name}
          </span>{' '}
          · {selected.band} · <span data-carnet-count="">{selected.count}</span>
        </p>
        <p className="av2-body av2-carnet__lead">{copy.carnet_lead}</p>
      </div>

      {model.bands.length > 1 && (
        <ul className="av2-carnet__bands" aria-label={copy.carnet_bands_label}>
          {model.bands.map((band) => (
            <li key={band.band}>
              <button
                type="button"
                className="av2-carnet__band"
                aria-pressed={band.band === selected.band}
                data-locked={band.locked ? '' : undefined}
                data-state={band.state}
                onClick={() => onSelectBand?.(band.band)}
              >
                {band.band}
                {band.state === 'current' && <span className="av2-carnet__band-note">· {copy.carnet_band_current}</span>}
                {band.locked && <span className="av2-carnet__band-note">· {copy.carnet_band_locked}</span>}
              </button>
            </li>
          ))}
        </ul>
      )}

      {selected.lockedNote && <p className="av2-body">{selected.lockedNote}</p>}

      <ol className="av2-carnet__list">
        {selected.items.map((item, index) => (
          <li
            key={item.id}
            className="av2-carnet__item"
            data-stamped={item.stamped ? 'true' : 'false'}
            data-locked={selected.locked ? '' : undefined}
          >
            <span className="av2-carnet__mark">
              <SealMini
                state={item.stamped ? 'earned' : 'future'}
                variant={sealForEdition(index).variant}
                caption={item.stamped ? item.date : null}
                label={item.ariaState}
              />
            </span>
            <div className="av2-carnet__body">
              <p className="av2-carnet__title">{item.title}</p>
              {language !== 'fr' && item.titleFr && item.titleFr !== item.title && (
                <p className="av2-fr av2-label av2-carnet__title-fr" lang="fr">
                  {item.titleFr}
                </p>
              )}
              {item.stamped ? (
                <>
                  {item.line && (
                    <p className="av2-carnet__stamp" data-carnet-stamp="">
                      {item.characterId && (
                        <CastPortrait characterId={item.characterId} name={item.characterName ?? undefined} mood="happy" size="xs" />
                      )}
                      <span lang={language === 'fr' ? 'fr' : undefined}>
                        {language === 'fr' ? frenchSpacing(item.line) : item.line}
                      </span>
                    </p>
                  )}
                  {item.quoteFr && (
                    <p className="av2-carnet__quote" lang="fr">
                      {frenchQuote(item.quoteFr)}
                    </p>
                  )}
                </>
              ) : (
                !selected.locked && <p className="av2-label">{copy.carnet_unstamped}</p>
              )}
              {item.rehearsalHref && (
                <Link
                  className="av2-btn av2-btn--quiet av2-btn--inline av2-carnet__try"
                  href={item.rehearsalHref}
                  aria-label={copy.carnet_try_aria.replace('{can_do}', item.title)}
                >
                  {copy.carnet_try}
                </Link>
              )}
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}

/** The Cahier tab: loads `GET /can-dos` and renders the band in force. */
export default function CarnetTab() {
  const language = useControlLanguage();
  const copy = canDoCopy(language);
  const [payload, setPayload] = React.useState<CanDosPayload | null>(null);
  const [state, setState] = React.useState<'loading' | 'ready' | 'failed'>('loading');
  const [band, setBand] = React.useState<string | null>(null);

  const load = React.useCallback(() => {
    let cancelled = false;
    setState('loading');
    api
      .getCanDos()
      .then((raw) => {
        if (cancelled) return;
        setPayload(readCanDos(raw));
        setState('ready');
      })
      .catch(() => {
        if (!cancelled) setState('failed');
      });
    return () => {
      cancelled = true;
    };
  }, []);

  React.useEffect(() => load(), [load]);

  if (state === 'loading') {
    return (
      <div className="av2-carnet" aria-busy="true">
        <Skeleton height={18} radius={9} />
        <Skeleton height={88} radius={16} />
        <Skeleton height={88} radius={16} />
      </div>
    );
  }
  if (state === 'failed') {
    return (
      <div className="av2-carnet" role="status">
        <p className="av2-body">{copy.carnet_load_failed}</p>
        <Action tone="secondary" inline onClick={() => load()}>
          {copy.carnet_retry}
        </Action>
      </div>
    );
  }
  return <CarnetView model={carnetModel(payload, band, language)} language={language} onSelectBand={setBand} />;
}

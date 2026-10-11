/**
 * WP-121 B · La Relecture: the learner answers their own Papier's question again.
 *
 * The plate as a band, the dossier's title, the question as Romy proposed it; then a
 * field for the answer *to the question* (one or two sentences, French), without the
 * old answer on screen. After sending, the two answers side by side — «Semaine 34»
 * and «Aujourd'hui» — with the words the rubric flagged underlined (a dotted line for
 * register, a solid one for grammar, each with its word for screen readers: never
 * colour alone), and Romy's one line. No score, no verdict word.
 */

import React, { useId, useState } from 'react';

import { Action, CastPortrait } from '@/components/atelier-v2/ui';
import { resolveMediaUrl } from '@/lib/media-url';
import type { RelectureOffer, RelecturePair, RelectureSide } from '@/lib/carte-types';

import type { CarteCopy } from './carte-copy';
import { relectureSegments } from './palais-model';

export type CarteRelectureProps = {
  offer: RelectureOffer;
  copy: CarteCopy;
  /** The stored pair, when the Papier was already re-read. */
  pair?: RelecturePair | null;
  onAnswer: (answerFr: string) => Promise<RelecturePair>;
  onBack: () => void;
};

function Side({ side, copy, mine }: { side: RelectureSide; copy: CarteCopy; mine?: boolean }) {
  return (
    <figure className="carte-relecture__side" data-side={mine ? 'now' : 'then'}>
      <figcaption className="av2-label">{side.labelFr}</figcaption>
      <blockquote className="carte-relecture__text" lang="fr">
        {relectureSegments(side.textFr, side.spans).map((segment, index) =>
          segment.flag ? (
            <span key={index} className="carte-flag" data-flag={segment.flag}>
              {segment.text}
              <span className="av2-sr"> ({copy.relecture_flag[segment.flag]})</span>
            </span>
          ) : (
            <React.Fragment key={index}>{segment.text}</React.Fragment>
          ),
        )}
      </blockquote>
    </figure>
  );
}

export function CarteRelecture({ offer, copy, pair: initialPair = null, onAnswer, onBack }: CarteRelectureProps) {
  const [pair, setPair] = useState<RelecturePair | null>(initialPair);
  const [text, setText] = useState('');
  const [pending, setPending] = useState(false);
  const [failed, setFailed] = useState(false);
  const fieldId = `carte-relecture-${useId().replace(/:/g, '')}`;
  const plate = offer.plateUrl ? resolveMediaUrl(offer.plateUrl) ?? offer.plateUrl : null;

  const send = async () => {
    setPending(true);
    setFailed(false);
    try {
      setPair(await onAnswer(text.trim()));
    } catch {
      setFailed(true);
    } finally {
      setPending(false);
    }
  };

  return (
    <section className="carte-relecture" aria-label={copy.relecture_title}>
      <div className="carte-relecture__band" aria-hidden="true">
        {plate && (
          // eslint-disable-next-line @next/next/no-img-element -- a static plate, already sized
          <img src={plate} alt="" decoding="async" />
        )}
      </div>
      <header className="carte-relecture__head">
        <p className="av2-label" lang="fr">
          {[copy.relecture_title, offer.placeLabelFr].filter(Boolean).join(' · ')}
        </p>
        <h2 className="carte-relecture__title" lang="fr">
          {offer.dossierTitleFr}
        </h2>
      </header>

      {offer.kind === 'question' && (
        <figure className="carte-relecture__question">
          <span aria-hidden="true">
            <CastPortrait characterId="romy_tremblay" name="Romy" size="xs" ring />
          </span>
          <blockquote lang="fr">{offer.promptFr}</blockquote>
        </figure>
      )}

      {pair ? (
        <>
          <div className="carte-relecture__pair">
            <Side side={pair.then} copy={copy} />
            <Side side={pair.now} copy={copy} mine />
          </div>
          <figure className="carte-relecture__romy" data-char="romy_tremblay">
            <span aria-hidden="true">
              <CastPortrait characterId="romy_tremblay" name="Romy" size="sm" ring />
            </span>
            <blockquote lang="fr">{pair.romyLineFr}</blockquote>
          </figure>
          <Action tone="secondary" onClick={onBack}>
            {copy.review_back}
          </Action>
        </>
      ) : (
        <>
          <p className="av2-body av2-body--lg">{offer.kind === 'question' ? copy.relecture_lead_question : copy.relecture_lead_headline}</p>
          <div className="av2-field">
            <label className="av2-field__label" htmlFor={fieldId}>
              {copy.relecture_field}
            </label>
            <textarea
              id={fieldId}
              className="av2-field__control"
              lang="fr"
              rows={3}
              maxLength={600}
              value={text}
              placeholder={copy.relecture_placeholder}
              disabled={pending}
              onChange={(event) => setText(event.target.value)}
            />
          </div>
          {failed && <p className="av2-label carte-review__failed">{copy.review_error}</p>}
          <Action tone="primary" pending={pending} pendingLabel={copy.relecture_sending} disabled={!text.trim()} onClick={() => void send()}>
            {copy.relecture_send}
          </Action>
        </>
      )}
    </section>
  );
}

export default CarteRelecture;

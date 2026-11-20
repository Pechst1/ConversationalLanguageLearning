/**
 * «Le titre» and «L'intox express» · what both players share: their props, «Lire» (the
 * story's picture, the dateline, the lead at the learner's band — every word tappable,
 * «Traduire», ▶ — and the source), a tappable French line with its translation chip, and the
 * outlet's verbatim quote with the words that settle the point lit and its name.
 */

import React from 'react';

import { Action, ArrowRightIcon } from '@/components/atelier-v2/ui';
import type { LineVoice } from '@/components/atelier-v2/journey/useLineVoice';
import type { RvIntoxView, RvRubriqueBody, RvRubriqueQuote, RvRubriqueRead, RvTitreView } from '@/lib/revue-rubriques-types';
import type { RvComptoirText, RvGloss, RvLanguage, RvSessionView } from '@/lib/revue-types';

import type { ComptoirCopy } from '../comptoir/comptoir-copy';
import { ComptoirPicture, ListenChip } from '../comptoir/RvComptoirParts';
import type { RevueCopy } from '../revue-copy';
import { RvGallery } from '../RvGallery';
import { RvGlossText, RvSourceLine, RvTranslate, type RvWordEvent } from '../RvThread';
import type { RubriqueCopy } from './rubriques-copy';
import { settledSegments } from './rubriques-model';

/** What each screen is given by `RvRubrique`. */
export type RubriqueStepProps = {
  session: RvSessionView;
  chrome: RvLanguage;
  copy: RevueCopy;
  ccopy: ComptoirCopy;
  rcopy: RubriqueCopy;
  /** The reasons: the mother tongue (the gloss language), while the chrome is French from B1. */
  xcopy: RubriqueCopy;
  glossLanguage: RvLanguage;
  glosses: RvGloss[];
  voice: LineVoice;
  pending: string | null;
  readOnly: boolean;
  onAct: (body: RvRubriqueBody, key: string) => Promise<boolean>;
  onContinue: () => void;
  wordFor: (speakerId: string | null, speakerName?: string) => (event: RvWordEvent) => void;
  notice: React.ReactNode;
  footRef: React.Ref<HTMLDivElement>;
};
export type TitreStepProps = RubriqueStepProps & { view: RvTitreView };
export type IntoxStepProps = RubriqueStepProps & { view: RvIntoxView };

/** A French line, every word tappable, with «Traduire». */
export function FrLine({ text, props, className = 'rb-line__fr' }: { text: RvComptoirText; props: RubriqueStepProps; className?: string }) {
  const { glosses, glossLanguage, copy, wordFor } = props;
  return (
    <div className="rb-line">
      <p className={className} lang="fr">
        <RvGlossText text={text.fr} glosses={glosses} mode="tap" glossLanguage={glossLanguage} onWord={wordFor(null)} />
      </p>
      <RvTranslate textFr={text.fr} translation={text.tr} glossLanguage={glossLanguage} copy={copy} />
    </div>
  );
}

/** The outlet's own words, verbatim, the settling ones lit, and who wrote them. */
export function SourceQuote({ quote }: { quote: RvRubriqueQuote }) {
  return (
    <figure className="rb-quote">
      <blockquote className="rb-quote__fr" lang="fr">
        «&nbsp;
        {settledSegments(quote.quoteFr, quote.settlesFr).map((segment, index) =>
          segment.wrong ? (
            <mark key={index} className="rb-quote__lit">
              {segment.text}
            </mark>
          ) : (
            <React.Fragment key={index}>{segment.text}</React.Fragment>
          ),
        )}
        &nbsp;»
      </blockquote>
      {quote.sourceName && (
        <figcaption className="rb-quote__by" lang="fr">
          {quote.sourceName}
        </figcaption>
      )}
    </figure>
  );
}

/** The lead at the learner's band, with its tools and its source. */
export function LeadBlock({ read, props, voiceKey }: { read: RvRubriqueRead; props: RubriqueStepProps; voiceKey: string }) {
  const { session, copy, ccopy, glossLanguage, glosses, voice, wordFor } = props;
  const source = read.sources[0] ?? null;
  return (
    <section className="rv-lead ct-lead" aria-label={copy.lead_kicker}>
      <p className="rv-lead__k">
        {copy.lead_kicker}
        {read.datelineFr && (
          <>
            {' · '}
            <span lang="fr">{read.datelineFr}</span>
          </>
        )}
      </p>
      <p className="rv-lead__fr" lang="fr">
        <RvGlossText text={read.lead.fr} glosses={glosses} mode={session.plan.support.glosses} glossLanguage={glossLanguage} onWord={wordFor(null)} />
      </p>
      <RvTranslate
        textFr={read.lead.fr}
        translation={read.lead.tr}
        glossLanguage={glossLanguage}
        copy={copy}
        before={<ListenChip voice={voice} voiceKey={voiceKey} textFr={read.lead.fr} castId="romy_tremblay" copy={copy} ccopy={ccopy} />}
      />
      {source && <RvSourceLine source={source} copy={copy} />}
    </section>
  );
}

/** «Lire»: the picture, the lead, the story's other pictures (RvGallery), one press to the assignment. */
export function RvRubriqueRead({ read, press, props }: { read: RvRubriqueRead; press: string; props: RubriqueStepProps }) {
  const { session, pending, readOnly, onContinue, notice, footRef } = props;
  return (
    <>
      <div className="rv-body ct-body" data-step="read">
        <ComptoirPicture url={session.stage.plateUrl} credit={session.stage.plateKind === 'story'} />
        <LeadBlock read={read} props={props} voiceKey={`rb-lead-${session.id}`} />
        {/* The story's other pictures after the lead: the text first on a phone's first screen. */}
        <RvGallery pictures={session.stage.pictures} mainUrl={session.stage.plateUrl} copy={props.copy} />
        {notice}
      </div>
      {!readOnly && (
        <div className="rv-foot ct-foot" ref={footRef}>
          <Action tone="primary" lang="fr" pending={pending === 'open'} pendingLabel={press} disabled={pending !== null} iconAfter={<ArrowRightIcon size={18} />} onClick={onContinue}>
            {press}
          </Action>
        </div>
      )}
    </>
  );
}

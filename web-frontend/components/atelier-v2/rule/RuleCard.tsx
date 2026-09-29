/**
 * WP-L10 — the rule card v2 (canvas «La règle, v2», boards 18–19).
 *
 * One Garamond line, and it is French: an example said by a character, with
 * the part that carries the rule in red. The rule is one sentence in the
 * learner's language; the pattern is drawn (rows with the gender shapes of
 * WP-D6, or a small table where silent endings are grey); one wrong/right
 * pair; «Why?» opens the longer note. `intro` is the card as its own screen
 * before a rule's first exercise; `inline` sits above an exercise, whose prompt
 * is then the screen's one headline, so the example is set in the body face.
 */

import React, { useEffect, useRef, useState } from 'react';
import Link from 'next/link';

import { CastPortrait } from '@/components/atelier-v2/ui/CastPortrait';
import { SpeakingPortrait } from '@/components/atelier-v2/journey/SpeakingPortrait';
import type { LineVoice } from '@/components/atelier-v2/journey/useLineVoice';
import apiService from '@/services/api';
import {
  RULE_CARD_COPY,
  parseMarked,
  pick,
  plainText,
  type RuleCardData,
  type RuleCardShape,
  type RuleSceneAnchor,
} from '@/lib/rule-card';
import type { ControlLanguage } from '@/types/daily-journey';
import type { PortraitMood } from '@/lib/onboarding-portraits';

export const RULE_CARD_SPEAKERS: Record<string, string> = {
  margaux_barman: 'Margaux',
  marin_leveque: 'Marin',
  romy_tremblay: 'Romy',
  lila_bonnet: 'Lila',
  augustin_de_roncourt: 'Gus',
  landlord_marchand: 'M. Marchand',
};

export function Marked({ value }: { value: string }) {
  return (
    <>
      {parseMarked(value).map((segment, index) =>
        segment.tone === 'plain' ? (
          <React.Fragment key={index}>{segment.text}</React.Fragment>
        ) : (
          <span key={index} className={`rc-${segment.tone}`}>
            {segment.text}
          </span>
        ),
      )}
    </>
  );
}

function ShapeGlyph({ shape }: { shape: RuleCardShape }) {
  if (shape === 'none') return <span className="rc-glyph" aria-hidden="true" />;
  return (
    <svg className="rc-glyph" data-shape={shape} width="30" height="22" viewBox="0 0 30 22" aria-hidden="true">
      {shape === 'square' && <rect x="7" y="3" width="16" height="16" rx="3.5" />}
      {shape === 'circle' && <circle cx="15" cy="11" r="8.5" />}
      {shape === 'circles' && (
        <>
          <circle cx="9" cy="11" r="7.5" />
          <circle cx="21" cy="11" r="7.5" className="rc-glyph__back" />
        </>
      )}
      {shape === 'triangle' && <path d="M15 2.5 L24 19.5 H6 Z" />}
    </svg>
  );
}

function useSpeech(text: string) {
  const [busy, setBusy] = useState(false);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  useEffect(() => () => audioRef.current?.pause(), []);
  const play = async () => {
    if (busy || !text) return;
    setBusy(true);
    try {
      const bytes = await apiService.synthesizeSpeech(text);
      const url = URL.createObjectURL(new Blob([bytes], { type: 'audio/mpeg' }));
      audioRef.current?.pause();
      const audio = new Audio(url);
      audioRef.current = audio;
      audio.onended = () => URL.revokeObjectURL(url);
      await audio.play();
    } catch {
      // Audio is a help, never a gate: a failed synthesis leaves the text.
    } finally {
      setBusy(false);
    }
  };
  return { busy, play };
}

export type RuleCardProps = {
  card: RuleCardData;
  language: ControlLanguage;
  variant?: 'intro' | 'inline';
  conceptId?: number | string | null;
  /** intro only: the one primary action, «Essayer». */
  onDone?: () => void;
  /**
   * WP-S5: the rule's coach. A card without a speaker is said by its coach, so
   * the face on the card is the face on the feedback; `coachMood` is theirs.
   */
  coach?: { id: string; name: string } | null;
  coachMood?: PortraitMood;
  /**
   * WP-92: the day's own line using the rule — the FIRST anchor, with its
   * speaker's face and «in today's scene». The card's generic example follows
   * it (in the body face: the scene line is the screen's one Garamond line).
   * Absent: the card is unchanged.
   */
  sceneAnchor?: RuleSceneAnchor | null;
  /** WP-91: the face speaks the scene line when a voice is at hand. */
  sceneVoice?: LineVoice | null;
  /** «Écouter Margaux», in the learner's language. */
  sceneListenLabel?: string;
};

function SceneAnchor({
  anchor,
  variant,
  label,
  voice,
  listenLabel,
}: {
  anchor: RuleSceneAnchor;
  variant: 'intro' | 'inline';
  label: string;
  voice?: LineVoice | null;
  listenLabel?: string;
}) {
  const text = plainText(anchor.fr);
  return (
    <div className="rc-scene" data-anchor="scene">
      <div className="rc-source">
        {anchor.castId && (
          <SpeakingPortrait
            characterId={anchor.castId}
            name={anchor.name}
            size="xs"
            ring
            line={{ key: 'rule-scene-anchor', text_fr: text, character_id: anchor.castId }}
            voice={voice}
            label={listenLabel || anchor.name}
          />
        )}
        <span className="rc-source__name">
          {anchor.name && <span className="rc-scene__who">{anchor.name}</span>}
          <span className="rc-scene__label">{label}</span>
        </span>
      </div>
      {variant === 'intro' ? (
        <h2 className="av2-headline rc-example" lang="fr">
          <Marked value={anchor.fr} />
        </h2>
      ) : (
        <p className="rc-example rc-example--inline" lang="fr">
          <Marked value={anchor.fr} />
        </p>
      )}
    </div>
  );
}

export function RuleCard({
  card,
  language,
  variant = 'intro',
  conceptId,
  onDone,
  coach,
  coachMood = 'neutral',
  sceneAnchor = null,
  sceneVoice = null,
  sceneListenLabel,
}: RuleCardProps) {
  const copy = RULE_CARD_COPY[language] ?? RULE_CARD_COPY.en;
  const [showTranslation, setShowTranslation] = useState(false);
  const [showWhy, setShowWhy] = useState(false);
  const exampleText = plainText(card.example.fr);
  const speech = useSpeech(exampleText);
  const translation = pick(card.example.tr, language);
  const rule = pick(card.rule, language);
  const more = pick(card.more, language);
  const speakerId = card.speaker || coach?.id || null;
  const speakerName = card.speaker
    ? RULE_CARD_SPEAKERS[card.speaker] ?? null
    : coach
      ? RULE_CARD_SPEAKERS[coach.id] ?? coach.name
      : null;
  const speakerMood: PortraitMood = coach && speakerId === coach.id ? coachMood : 'neutral';
  const pattern = card.pattern;

  return (
    <section className="rc" data-variant={variant} aria-label={copy.eyebrow}>
      {variant === 'intro' && <p className="av2-label av2-label--story rc-eyebrow">{copy.eyebrow}</p>}

      {sceneAnchor && (
        <SceneAnchor
          anchor={sceneAnchor}
          variant={variant}
          label={copy.fromScene}
          voice={sceneVoice}
          listenLabel={sceneListenLabel}
        />
      )}

      <div className="rc-source">
        {speakerId && speakerName && (
          <CastPortrait characterId={speakerId} name={speakerName} mood={speakerMood} size="sm" ring />
        )}
        {speakerName && <span className="rc-source__name">{speakerName}</span>}
        <button
          type="button"
          className="rc-listen"
          aria-label={copy.listen}
          aria-busy={speech.busy || undefined}
          onClick={() => void speech.play()}
        >
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M3 8v4h3l4 3V5L6 8H3z" />
            <path d="M13.5 7.5a3.5 3.5 0 0 1 0 5M15.5 5a7 7 0 0 1 0 10" />
          </svg>
        </button>
      </div>

      {variant === 'intro' && !sceneAnchor ? (
        <h2 className="av2-headline rc-example" lang="fr">
          <Marked value={card.example.fr} />
        </h2>
      ) : (
        <p className="rc-example rc-example--inline" lang="fr">
          <Marked value={card.example.fr} />
        </p>
      )}

      {translation && (
        <div className="rc-translate">
          <button
            type="button"
            className="rc-link"
            aria-expanded={showTranslation}
            onClick={() => setShowTranslation((value) => !value)}
          >
            {showTranslation ? copy.hideTranslation : copy.translate}
          </button>
          {showTranslation && <p className="rc-translation">{translation}</p>}
        </div>
      )}

      {rule && <p className="rc-rule">{rule}</p>}

      {pattern?.kind === 'rows' && pattern.rows.length > 0 && (
        <div className="rc-pattern" role="group" aria-label={copy.pattern} lang="fr">
          {pattern.rows.map((row, index) => (
            <div className="rc-row" key={index}>
              <ShapeGlyph shape={row.shape} />
              <span className="rc-row__label">{row.label}</span>
              <span className="rc-row__fr">
                <Marked value={row.fr} />
              </span>
            </div>
          ))}
        </div>
      )}

      {pattern?.kind === 'table' && pattern.rows.length > 0 && (
        <div className="rc-pattern rc-pattern--table" role="group" aria-label={`${copy.pattern} · ${pattern.verb}`}>
          <div className="rc-table" lang="fr">
            {pattern.rows.map((row, index) => (
              <div className="rc-table__cell" key={index}>
                <span className="rc-table__p">{row.p}</span>
                <span className="rc-table__form">
                  <Marked value={row.fr} />
                </span>
              </div>
            ))}
          </div>
          {pick(pattern.note, language) && <p className="rc-note">{pick(pattern.note, language)}</p>}
        </div>
      )}

      {card.contrast && (
        <div className="rc-contrast" lang="fr">
          <p className="rc-contrast__line" data-tone="wrong">
            <span className="rc-contrast__badge" aria-hidden="true">
              <svg width="10" height="10" viewBox="0 0 10 10" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M2 2l6 6M8 2L2 8" />
              </svg>
            </span>
            <span className="av2-sr">{copy.wrong}</span>
            <s>{plainText(card.contrast.wrong)}</s>
          </p>
          <p className="rc-contrast__line" data-tone="right">
            <span className="rc-contrast__badge" aria-hidden="true">
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M2 6.5l2.6 2.5L10 3.5" />
              </svg>
            </span>
            <span className="av2-sr">{copy.right}</span>
            <span>
              <Marked value={card.contrast.right} />
            </span>
          </p>
        </div>
      )}

      {(more || conceptId != null) && (
        <div className="rc-why">
          <button
            type="button"
            className="rc-why__toggle"
            aria-expanded={showWhy}
            onClick={() => setShowWhy((value) => !value)}
          >
            {copy.why}
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
              <path d={showWhy ? 'M2.5 7.5 6 4l3.5 3.5' : 'M2.5 4.5 6 8l3.5-3.5'} />
            </svg>
          </button>
          {showWhy && (
            <p className="rc-more">
              {more}{' '}
              {conceptId != null && (
                <Link className="rc-cahier" href={`/grammar?concept=${conceptId}`}>
                  {copy.cahier}
                </Link>
              )}
            </p>
          )}
        </div>
      )}

      {variant === 'intro' && onDone && (
        <button type="button" className="av2-btn av2-btn--primary rc-done" onClick={onDone}>
          {copy.tryIt}
        </button>
      )}
    </section>
  );
}

export default RuleCard;

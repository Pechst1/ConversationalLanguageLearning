/**
 * «Les habitués se souviennent» (2026-11-21, `REVUE_MEMORY_ENABLED`): ONE line a regular says
 * to the learner about an earlier Papier, on the first screen of the session — in French at the
 * learner's band, with its translation behind «Traduire» like every line of the counter.
 *
 * `RvSouvenirSlot` asks the server once and draws NOTHING when the switch is off, the read
 * fails, or there is no memory to speak of.
 */

import React, { useEffect, useState } from 'react';

import type { RvLanguage } from '@/lib/revue-types';
import type { RvSouvenir } from '@/lib/revue-rdv';

import { ComptoirBubble, type ComptoirStepProps } from '../comptoir/RvComptoirParts';
import { fillRdv, rdvCopy } from './rdv-copy';
import { souvenirTranslation } from './rdv-model';
import { useRdv } from './RdvContext';

type BubbleProps = Pick<ComptoirStepProps, 'copy' | 'ccopy' | 'glossLanguage' | 'glosses' | 'voice' | 'wordFor'>;

/**
 * «La belle édition»: the regular's aside — said from the bar, not part of the task: a small
 * label («Gus se souvient», chrome), their face, the line in the counter's
 * voice set lighter, off the column's edge, under a dotted rule.
 */
export function RvSouvenirLine({ line, props, language, chrome }: { line: RvSouvenir; props: BubbleProps; language: RvLanguage; chrome?: RvLanguage }) {
  const copy = rdvCopy(chrome ?? language);
  const label = line.speakerFr ? fillRdv(copy.souvenir_by, { name: line.speakerFr }) : copy.souvenir_label;
  return (
    <aside className="rv-souvenir pp-aside" data-souvenir={line.templateId} aria-label={label}>
      <p className="pp-aside__k" aria-hidden="true">
        {label}
      </p>
      <ComptoirBubble
        castId={line.speakerId}
        name={line.speakerFr}
        textFr={line.fr}
        translation={souvenirTranslation(line, language)}
        glosses={props.glosses}
        glossLanguage={props.glossLanguage}
        voice={props.voice}
        voiceKey={`rdv-souvenir-${line.templateId}`}
        copy={props.copy}
        ccopy={props.ccopy}
        onWord={props.wordFor(line.speakerId, line.speakerFr)}
      />
    </aside>
  );
}

/** The slot the players' first screen calls. */
export function RvSouvenirSlot({ sessionId, props, chrome }: { sessionId: string; props: BubbleProps; chrome?: RvLanguage }) {
  const rdv = useRdv();
  const [line, setLine] = useState<RvSouvenir | null>(null);
  useEffect(() => {
    if (!rdv) return undefined;
    let alive = true;
    rdv
      .souvenir(sessionId)
      .then((next) => {
        if (alive) setLine(next);
      })
      .catch(() => {
        // A memory is an extra: nothing is said.
      });
    return () => {
      alive = false;
    };
  }, [rdv, sessionId]);
  if (!line) return null;
  return <RvSouvenirLine line={line} props={props} language={props.glossLanguage} chrome={chrome} />;
}

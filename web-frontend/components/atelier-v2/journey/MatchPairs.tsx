/**
 * WP-78 — «Paires» : four French cards, four meanings, tap one of each.
 *
 * With the step's hashed key (WP-76) each pair is checked on the device the
 * moment it is made: a right pair settles green and leaves play, a wrong one
 * flashes and lets go. Every pairing is recorded, wrong ones included, and
 * posted once the last pair lands — the server grades the day's target on the
 * first pairing that touched it (`journey_learning.match_pairs_target_correct`),
 * so eliminating the others is fine and guessing the target is not.
 *
 * Without a usable key (an older server, an insecure origin) nothing is
 * coloured: the learner pairs all four, may undo a pair by tapping it, and the
 * server's verdict is the first word on it.
 */

import React, { useEffect, useRef, useState } from 'react';

import { checkAnswerLocally, promptHasAnswerKey } from '@/lib/answer-key';
import type { RecallOption, RecallPrompt } from '@/types/daily-journey';

import { matchCards, pairsComplete } from './practice-formats';

export type MatchPairsProps = {
  prompt: Pick<RecallPrompt, 'task_type' | 'answer_key' | 'options'>;
  disabled?: boolean;
  /** `pairs` is every pairing made, as `[fr, native, fr, native, …]`. */
  onComplete: (pairs: string[], clean: boolean) => void;
  /** How long a wrong pair stays red before it lets go. */
  flashMs?: number;
};

type CardState = 'idle' | 'selected' | 'matched' | 'paired' | 'wrong';

export function MatchPairs({ prompt, disabled = false, onComplete, flashMs = 450 }: MatchPairsProps) {
  const { fr, native } = matchCards(prompt.options);
  const keyed = promptHasAnswerKey(prompt);
  const [pickFr, setPickFr] = useState<string | null>(null);
  const [pickNative, setPickNative] = useState<string | null>(null);
  const [attempts, setAttempts] = useState<string[]>([]);
  const [settled, setSettled] = useState<string[]>([]);
  const [wrong, setWrong] = useState<string[]>([]);
  const [mistakes, setMistakes] = useState(0);
  const done = useRef(false);

  useEffect(() => {
    if (done.current || !pairsComplete(settled, fr.length)) return;
    done.current = true;
    // Unkeyed, the settled pairs are the answer; keyed, every attempt is.
    onComplete(keyed ? attempts : settled, keyed && mistakes === 0);
  }, [attempts, fr.length, keyed, mistakes, onComplete, settled]);

  const pair = (frId: string, nativeId: string) => {
    setPickFr(null);
    setPickNative(null);
    if (!keyed) {
      setSettled((current) => [...current, frId, nativeId]);
      return;
    }
    setAttempts((current) => [...current, frId, nativeId]);
    void checkAnswerLocally(prompt, { tileIds: [frId, nativeId] }).then((verdict) => {
      if (verdict === 'correct') {
        setSettled((current) => [...current, frId, nativeId]);
      } else {
        setMistakes((count) => count + 1);
        setWrong([frId, nativeId]);
        window.setTimeout(() => setWrong([]), flashMs);
      }
    });
  };

  const tap = (card: RecallOption) => {
    if (disabled || done.current) return;
    if (settled.includes(card.id)) {
      if (keyed) return;
      // Unkeyed: tapping a made pair undoes it.
      setSettled((current) => {
        const at = current.indexOf(card.id);
        const start = at - (at % 2);
        return [...current.slice(0, start), ...current.slice(start + 2)];
      });
      return;
    }
    if (card.side === 'native') {
      if (pickFr) pair(pickFr, card.id);
      else setPickNative((current) => (current === card.id ? null : card.id));
    } else if (pickNative) {
      pair(card.id, pickNative);
    } else {
      setPickFr((current) => (current === card.id ? null : card.id));
    }
  };

  const stateOf = (card: RecallOption): CardState => {
    if (wrong.includes(card.id)) return 'wrong';
    if (settled.includes(card.id)) return keyed ? 'matched' : 'paired';
    if (card.id === pickFr || card.id === pickNative) return 'selected';
    return 'idle';
  };

  const column = (cards: RecallOption[], side: 'fr' | 'native') => (
    <div className="av2-match__col" role="group" aria-label={side === 'fr' ? 'Français' : 'Sens'}>
      {cards.map((card) => {
        const state = stateOf(card);
        return (
          <button
            key={card.id}
            type="button"
            className="av2-match__card"
            data-state={state}
            lang={side === 'fr' ? 'fr' : undefined}
            aria-pressed={state === 'selected'}
            disabled={disabled || (keyed && state === 'matched')}
            onClick={() => tap(card)}
          >
            {card.text_fr}
          </button>
        );
      })}
    </div>
  );

  return (
    <div className="av2-match" data-keyed={keyed ? 'true' : 'false'}>
      {column(fr, 'fr')}
      {column(native, 'native')}
    </div>
  );
}

export default MatchPairs;

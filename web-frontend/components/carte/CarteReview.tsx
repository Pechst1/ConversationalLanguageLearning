/**
 * WP-121 A.3 · reviewing «ici»: the due words of one place, on its plate.
 *
 * The plate is the full-bleed stage behind; Romy (or the guest) is drawn small with the
 * line that carried the word — the cue the method of loci needs. The words are posed
 * with the journey's own recall formats (`MatchPairs`, the word bank's `WordTiles`,
 * `Dictation`), in the server's order (`palais-model.ts` says how it chooses). Every
 * answer is graded on the server and scheduled through the existing SRS; when the
 * place's words are done, «Retour à la carte» (the dot is gone there).
 */

import React, { useCallback, useState } from 'react';

import { Dictation } from '@/components/atelier-v2/journey/Dictation';
import { journeyCopy } from '@/components/atelier-v2/journey/journey-copy';
import { MatchPairs } from '@/components/atelier-v2/journey/MatchPairs';
import { Action, CastPortrait, WordTiles, type ChoiceOption } from '@/components/atelier-v2/ui';
import { resolveMediaUrl } from '@/lib/media-url';
import type { CarteLanguage, CarteReview as CarteReviewData, CarteReviewAnswer, CarteReviewGrade, CarteReviewItem } from '@/lib/carte-types';

import type { CarteCopy } from './carte-copy';
import { weekNo } from './carte-model';
import { itemSpeaker, itemVerdict, reviewGraded, reviewNext, reviewStart, type ReviewProgress } from './palais-model';

export type CarteReviewProps = {
  review: CarteReviewData;
  copy: CarteCopy;
  language?: CarteLanguage;
  onGrade: (answer: CarteReviewAnswer) => Promise<CarteReviewGrade>;
  onBack: () => void;
  /** Tests: where the review stands on first render. */
  initialProgress?: ReviewProgress;
};

export function CarteReview({ review, copy, language = 'fr', onGrade, onBack, initialProgress }: CarteReviewProps) {
  const [progress, setProgress] = useState<ReviewProgress>(() => initialProgress ?? reviewStart(review));
  const [tiles, setTiles] = useState<string[]>([]);
  const [text, setText] = useState('');
  const [pending, setPending] = useState(false);
  const [failed, setFailed] = useState(false);
  const item: CarteReviewItem | null = progress.done ? null : review.items[progress.index] ?? null;
  const speaker = itemSpeaker(review, item);
  const verdict = item ? itemVerdict(progress, item) : null;
  const plate = review.plateUrl ? resolveMediaUrl(review.plateUrl) ?? review.plateUrl : null;
  const week = weekNo(review.week);

  const send = useCallback(
    async (answer: CarteReviewAnswer) => {
      setPending(true);
      setFailed(false);
      try {
        const grade = await onGrade(answer);
        setProgress((current) => reviewGraded(current, grade));
      } catch {
        setFailed(true);
      } finally {
        setPending(false);
      }
    },
    [onGrade],
  );

  const next = () => {
    setTiles([]);
    setText('');
    setProgress((current) => reviewNext(current, review));
  };

  const options: ChoiceOption[] = (item?.options ?? []).map((option) => ({ id: option.id, textFr: option.text_fr }));
  const graded = verdict !== null;

  return (
    <section className="carte-review" aria-label={copy.review_title} data-format={item?.taskType ?? 'done'}>
      <div className="carte-review__plate" aria-hidden="true">
        {plate ? (
          // eslint-disable-next-line @next/next/no-img-element -- a static plate, already sized
          <img src={plate} alt="" decoding="async" />
        ) : (
          <span className="carte-review__plate-fallback" />
        )}
      </div>

      <header className="carte-review__head">
        <p className="av2-label" lang="fr">
          {[review.placeLabelFr, copy.week_fr(week)].filter(Boolean).join(' · ')}
        </p>
        <h2 className="carte-review__title" lang="fr">
          {copy.review_title}
        </h2>
        {item && review.items.length > 1 && (
          <p className="carte-review__count" aria-live="polite">
            {copy.review_progress(progress.index + 1, review.items.length)}
          </p>
        )}
      </header>

      {speaker && !progress.done && (
        <figure className="carte-review__voice" data-char={speaker.speakerId}>
          <span className="carte-review__face" aria-hidden="true">
            <CastPortrait characterId={speaker.speakerId} name={speaker.speakerName} size="sm" ring />
          </span>
          <div className="carte-review__said">
            <figcaption className="av2-label">{speaker.speakerName}</figcaption>
            <blockquote lang="fr">{speaker.lineFr}</blockquote>
          </div>
        </figure>
      )}

      <div className="carte-review__card">
        {review.items.length === 0 && !initialProgress ? (
          <p className="av2-body">{copy.review_empty}</p>
        ) : progress.done ? (
          <div className="carte-review__done" role="status">
            <h3 className="carte-review__done-title" lang="fr">
              {copy.review_done_title}
            </h3>
            <p className="av2-body">{copy.review_done_body}</p>
            <ul className="carte-review__words" lang="fr">
              {review.words.map((word) => (
                <li key={word.progressId} data-right={progress.results[word.progressId] ? 'true' : progress.results[word.progressId] === false ? 'false' : undefined}>
                  <b>{word.word}</b> <span>{word.gloss}</span>
                </li>
              ))}
            </ul>
            <Action tone="primary" onClick={onBack}>
              {copy.review_back}
            </Action>
          </div>
        ) : item ? (
          <>
            <p className="av2-body carte-review__ask">{copy.review_instruction[item.taskType]}</p>
            {item.taskType === 'match_pairs' && (
              <MatchPairs
                key={item.id}
                prompt={{ task_type: 'match_pairs', answer_key: item.answerKey, options: item.options }}
                disabled={pending || graded}
                onComplete={(pairs) => void send({ itemId: item.id, tileIds: pairs })}
              />
            )}
            {(item.taskType === 'word_bank' || item.taskType === 'unscramble') && (
              <WordTiles
                options={options}
                placed={tiles}
                label={copy.review_instruction[item.taskType]}
                emptyHint={copy.review_tiles_empty}
                removeLabel={copy.review_remove_last}
                disabled={pending || graded}
                onPlace={(id) => setTiles((current) => [...current, id])}
                onRemoveLast={() => setTiles((current) => current.slice(0, -1))}
                verdict={verdict}
                verdictLabel={verdict === 'correct' ? copy.review_correct : copy.review_wrong}
              />
            )}
            {item.taskType === 'dictation' && (
              <Dictation
                prompt={{ audio_url: item.audioUrl, instruction_native: copy.review_instruction.dictation }}
                copy={journeyCopy(language)}
                value={text}
                disabled={pending || graded}
                onChange={setText}
              />
            )}
            {graded && (
              <p className="carte-review__verdict" data-verdict={verdict} role="status">
                {verdict === 'correct' ? copy.review_correct : copy.review_wrong}
                {verdict === 'wrong' && speaker && (
                  <>
                    {' · '}
                    <span lang="fr">{speaker.sentenceFr}</span>
                  </>
                )}
              </p>
            )}
            {failed && <p className="av2-label carte-review__failed">{copy.review_error}</p>}
            {graded ? (
              <Action tone="primary" onClick={next}>
                {copy.review_next}
              </Action>
            ) : item.taskType !== 'match_pairs' ? (
              <Action
                tone="primary"
                pending={pending}
                pendingLabel={copy.review_sending}
                disabled={item.taskType === 'dictation' ? !text.trim() : tiles.length === 0}
                onClick={() =>
                  void send(item.taskType === 'dictation' ? { itemId: item.id, text } : { itemId: item.id, tileIds: tiles })
                }
              >
                {copy.review_check}
              </Action>
            ) : null}
          </>
        ) : null}
      </div>
    </section>
  );
}

export default CarteReview;

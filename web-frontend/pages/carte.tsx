/* WP-120 phase C · /carte — La Carte: where each Papier happened.

   An own-shell av2 page (no tab: the map is an archive, not a daily surface), the
   settings cog in its corner. Reached from the close screen of a Papier, the
   Relevé's «Le Papier» section and Settings' Bibliothèque row.

   Query:
     ?mock=1         DEV ONLY (never in a production build): six Papiers and three
                     «Mon quartier» places from components/carte/carte-mock.ts.
                     ?lang=de|en|fr shapes the chrome; ?level=idf|paris opens there.
                     WP-121: &due=1 puts two due words on the Aligre pin (and a Relecture
                     mark on two pins); &review=marche_aligre reviews them; &relecture=1
                     opens La Relecture (the side-by-side pair once sent).
     ?review=<place_id>       WP-121 A.3: review the due words met at that place.
     ?relecture=<session_id>  WP-121 B: La Relecture of that Papier (the pair if re-read).
     ?focus=<id>     WP-120 phase D: the Papier with that session id opens its card on
                     load, on its own level (the close screen's «Voir sur la carte»).

   States: loading · the map (with the empty state above it when nothing is filed
   yet) · the Revue switched off · the API failing (retry). */

import React, { useCallback, useEffect, useState } from 'react';
import Head from 'next/head';
import { useRouter } from 'next/router';

import { AtelierV2Root, IconAction, Skeleton, StateBlock } from '@/components/atelier-v2/ui';
import { ArrowLeftIcon } from '@/components/atelier-v2/ui/Shapes';
import { Carte, CarteEmpty, CarteRelecture, CarteReview, carteCopy } from '@/components/carte';
import { ShellCorner } from '@/components/layout/ShellCorner';
import { carteClient } from '@/lib/carte-api';
import type {
  CarteLanguage,
  CarteLevel,
  CartePin,
  CarteReview as CarteReviewData,
  CarteReviewAnswer,
  CarteReviewGrade,
  CarteView,
  RelectureOffer,
  RelecturePair,
} from '@/lib/carte-types';
import { useChromeLanguage } from '@/lib/learner-language';

type PageState =
  | { kind: 'loading' }
  | { kind: 'disabled' }
  | { kind: 'error' }
  | { kind: 'ready'; view: CarteView }
  | { kind: 'review'; review: CarteReviewData; grade: (answer: CarteReviewAnswer) => Promise<CarteReviewGrade> }
  | {
      kind: 'relecture';
      offer: RelectureOffer;
      pair: RelecturePair | null;
      answer: (answerFr: string) => Promise<RelecturePair>;
    }
  | { kind: 'unavailable'; message: string };

const BACK = '/notebook?mode=releve';

function queryString(value: string | string[] | undefined): string | null {
  const one = Array.isArray(value) ? value[0] : value;
  return one && one.trim() ? one.trim() : null;
}

export default function CartePage() {
  const router = useRouter();
  const learnerLanguage = useChromeLanguage();
  const mock = process.env.NODE_ENV !== 'production' && router.query.mock === '1';
  const langParam = queryString(router.query.lang);
  const language: CarteLanguage =
    mock && (langParam === 'de' || langParam === 'en' || langParam === 'fr') ? langParam : (learnerLanguage as CarteLanguage);
  const levelParam = queryString(router.query.level);
  const initialLevel: CarteLevel = mock && (levelParam === 'idf' || levelParam === 'paris') ? levelParam : 'france';
  const focus = queryString(router.query.focus);
  const copy = carteCopy(language);
  const [state, setState] = useState<PageState>({ kind: 'loading' });

  const reviewPlace = queryString(router.query.review);
  const relectureParam = queryString(router.query.relecture);
  const mockDue = mock && router.query.due === '1';

  const load = useCallback(async () => {
    if (!router.isReady) return;
    setState({ kind: 'loading' });
    // The literal NODE_ENV test lets the production build drop the mock chunk entirely.
    if (process.env.NODE_ENV !== 'production' && mock) {
      const m = await import('@/components/carte/carte-mock');
      if (reviewPlace) {
        setState({ kind: 'review', review: m.CARTE_MOCK_REVIEW, grade: m.mockGradeFor() });
      } else if (relectureParam) {
        const sent = router.query.sent === '1';
        setState({
          kind: 'relecture',
          offer: m.CARTE_MOCK_RELECTURE_OFFER,
          pair: sent ? m.CARTE_MOCK_RELECTURE_PAIR : null,
          answer: async () => m.CARTE_MOCK_RELECTURE_PAIR,
        });
      } else {
        setState({ kind: 'ready', view: mockDue ? m.CARTE_MOCK_DUE_VIEW : m.CARTE_MOCK_VIEW });
      }
      return;
    }
    const client = carteClient();
    try {
      if (reviewPlace) {
        const review = await client.review(reviewPlace);
        setState({ kind: 'review', review, grade: (answer) => client.grade(reviewPlace, answer) });
        return;
      }
      if (relectureParam) {
        const pair = await client.relecturePair(relectureParam);
        const offer = pair?.offer ?? (await client.relectureOffer());
        if (!offer || offer.sessionId !== relectureParam) {
          setState({ kind: 'unavailable', message: copy.relecture_unavailable });
          return;
        }
        setState({ kind: 'relecture', offer, pair, answer: (answerFr) => client.relectureAnswer(relectureParam, answerFr) });
        return;
      }
      const result = await client.carte();
      setState(result.enabled ? { kind: 'ready', view: result.view } : { kind: 'disabled' });
    } catch (error) {
      setState((error as { status?: number })?.status === 404 ? { kind: 'disabled' } : { kind: 'error' });
    }
  }, [router.isReady, router.query.sent, mock, mockDue, reviewPlace, relectureParam, copy.relecture_unavailable]);

  useEffect(() => {
    void load();
  }, [load]);

  const relire = (pin: CartePin) => void router.push(`/revue?session=${encodeURIComponent(pin.sessionId)}&readonly=1`);
  const releve = (pin: CartePin) => void router.push(`${BACK}#revue-${pin.week}`);
  const back = () => void router.push(BACK);
  // WP-121: the review and the Relecture keep the mock flags, so the demo walks through.
  const keep = mock ? `mock=1${langParam ? `&lang=${langParam}` : ''}` : '';
  const toMap = () => void router.push(`/carte${keep ? `?${keep}` : ''}`);
  const review = (pin: CartePin) =>
    pin.placeId && void router.push(`/carte?${keep ? `${keep}&` : ''}review=${encodeURIComponent(pin.placeId)}`);
  const reread = (pin: CartePin) =>
    void router.push(`/carte?${keep ? `${keep}&` : ''}relecture=${mock ? '1' : encodeURIComponent(pin.sessionId)}`);
  const inside = state.kind === 'review' || state.kind === 'relecture' || state.kind === 'unavailable';

  let body: React.ReactNode;
  if (state.kind === 'ready') {
    const { view } = state;
    body = (
      <>
        {view.pins.length === 0 && <CarteEmpty copy={copy} onOpenPapier={() => void router.push('/revue')} />}
        <Carte
          key={`${initialLevel}:${focus ?? ''}`}
          pins={view.pins}
          quartier={view.quartier}
          copy={copy}
          language={language}
          initialLevel={initialLevel}
          focusSessionId={focus}
          onRelire={relire}
          onReleve={releve}
          onReview={review}
          onRelecture={reread}
        />
      </>
    );
  } else if (state.kind === 'review') {
    body = <CarteReview review={state.review} copy={copy} language={language} onGrade={state.grade} onBack={toMap} />;
  } else if (state.kind === 'relecture') {
    body = <CarteRelecture offer={state.offer} pair={state.pair} copy={copy} onAnswer={state.answer} onBack={toMap} />;
  } else if (state.kind === 'unavailable') {
    body = <StateBlock tone="empty" title={state.message} action={{ label: copy.review_back, onSelect: toMap }} />;
  } else if (state.kind === 'disabled') {
    body = <StateBlock tone="empty" title={copy.disabled_title} body={copy.disabled_body} action={{ label: copy.back, onSelect: back }} />;
  } else if (state.kind === 'error') {
    body = <StateBlock tone="error" title={copy.error_title} body={copy.error_body} action={{ label: copy.retry, onSelect: () => void load() }} />;
  } else {
    body = (
      <div className="carte-loading" role="status" aria-busy="true" aria-label={copy.loading}>
        <Skeleton height={20} />
        <Skeleton height={320} radius={16} />
      </div>
    );
  }

  return (
    <>
      <Head>
        <title>La Carte · L’Atelier</title>
      </Head>
      <AtelierV2Root
        as="main"
        language={language}
        className={`carte-page${state.kind === 'review' ? ' carte-page--review' : ''}`}
        aria-label="La Carte"
        data-carte-mock={mock ? '' : undefined}
      >
        <ShellCorner />
        <header className="carte-page__head">
          <IconAction label={inside ? copy.review_back : copy.back} onClick={inside ? toMap : back}>
            <ArrowLeftIcon size={18} />
          </IconAction>
          <h1 className="carte-page__title" lang="fr">
            {copy.page_title}
          </h1>
        </header>
        <div className="carte-page__body">{body}</div>
        {mock && <p className="carte-page__mock">{copy.mock_badge}</p>}
      </AtelierV2Root>
    </>
  );
}

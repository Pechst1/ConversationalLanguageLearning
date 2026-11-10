/**
 * S4 stage 4 — «Aide», the Help place in Réglages.
 *
 * Three things, in the learner's own language (lib/help-copy.ts): a short FAQ,
 * the same feedback sheet the rest of the app opens (now asking whether the
 * learner wants an answer), and the contact address the legal pages print.
 * Nothing here sends a reply; the report only records the wish.
 */
import React from 'react';
import Head from 'next/head';
import { useRouter } from 'next/router';

import { Action, ArrowLeftIcon, AtelierV2Root, IconAction } from '@/components/atelier-v2/ui';
import { FEEDBACK_OPEN_EVENT } from '@/components/feedback/FeedbackWidget';
import { helpCopy } from '@/lib/help-copy';
import { LEGAL_CONTACT } from '@/lib/legal';
import { useLearnerLanguage } from '@/lib/learner-language';

const SETTINGS = '/settings';

export default function HelpPage() {
  const router = useRouter();
  const language = useLearnerLanguage();
  const copy = helpCopy(language);

  return (
    <>
      <Head>
        <title>{copy.page_title}</title>
      </Head>
      <AtelierV2Root as="main" language={language} className="av2-screen hp-screen" aria-labelledby="hp-headline">
        <header className="hp-head">
          <IconAction label={copy.back} onClick={() => void router.push(SETTINGS)}>
            <ArrowLeftIcon size={16} />
          </IconAction>
          <div>
            <p className="av2-label">{copy.eyebrow}</p>
            <h1 id="hp-headline" className="hp-headline">{copy.headline}</h1>
          </div>
        </header>
        <p className="hp-lead">{copy.lead}</p>

        <section className="hp-card" aria-label={copy.faq_label}>
          {copy.faq.map((item) => (
            <details key={item.id} className="hp-question" data-help-question={item.id}>
              <summary>{item.q}</summary>
              <p>{item.a}</p>
            </details>
          ))}
        </section>

        <section className="hp-card hp-row">
          <div className="hp-row__text">
            <span className="hp-row__label">{copy.feedback_label}</span>
            <span className="hp-row__hint">{copy.feedback_hint}</span>
          </div>
          <Action tone="secondary" inline onClick={() => window.dispatchEvent(new Event(FEEDBACK_OPEN_EVENT))}>
            {copy.feedback_action}
          </Action>
        </section>

        <section className="hp-card hp-row">
          <div className="hp-row__text">
            <span className="hp-row__label">{copy.contact_label}</span>
            <span className="hp-row__hint">{copy.contact_hint}</span>
            <a className="hp-contact" href={`mailto:${LEGAL_CONTACT}`}>{LEGAL_CONTACT}</a>
          </div>
        </section>
      </AtelierV2Root>
      <HelpStyles />
    </>
  );
}

/* Page-scoped `.av2 .hp-*`, tokens only, so both themes come from the tokens. */
function HelpStyles() {
  return (
    <style jsx global>{`
      .av2.hp-screen {
        display: flex;
        flex-direction: column;
        gap: 14px;
        width: 100%;
        max-width: 640px;
        margin: 0 auto;
        padding: 16px 16px 32px;
      }
      .av2 .hp-head {
        display: flex;
        align-items: center;
        gap: 12px;
      }
      .av2 .hp-headline {
        margin: 2px 0 0;
        font-family: var(--av2-serif);
        font-size: var(--av2-t-screen);
        line-height: 1.1;
      }
      .av2 .hp-lead {
        margin: 0;
        color: var(--av2-ink-2);
        font-size: var(--av2-t-body);
      }
      .av2 .hp-card {
        border-radius: var(--av2-r-card);
        background: var(--av2-paper);
        box-shadow: inset 0 0 0 1px var(--av2-line);
        padding: 4px 16px;
      }
      .av2 .hp-question + .hp-question {
        border-top: 1px solid var(--av2-line);
      }
      .av2 .hp-question summary {
        min-height: 44px;
        display: flex;
        align-items: center;
        cursor: pointer;
        font-weight: 600;
        font-size: var(--av2-t-body);
      }
      .av2 .hp-question p {
        margin: 0 0 14px;
        color: var(--av2-ink-2);
        font-size: var(--av2-t-body);
        line-height: 1.5;
      }
      .av2 .hp-row {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 12px;
        padding: 12px 16px;
      }
      .av2 .hp-row__text {
        display: flex;
        flex-direction: column;
        gap: 2px;
        min-width: 0;
      }
      .av2 .hp-row__label {
        font-weight: 600;
        font-size: var(--av2-t-body);
      }
      .av2 .hp-row__hint {
        color: var(--av2-muted);
        font-size: var(--av2-t-label);
      }
      .av2 .hp-contact {
        margin-top: 6px;
        color: var(--av2-ink);
        font-size: var(--av2-t-body);
        overflow-wrap: anywhere;
        text-decoration: underline;
        text-underline-offset: 3px;
      }
    `}</style>
  );
}

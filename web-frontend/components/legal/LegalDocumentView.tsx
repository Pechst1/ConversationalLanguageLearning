/**
 * WP-72 — one legal document (privacy policy or terms) in the av2 system.
 *
 * Rendered by the public `/privacy` and `/terms` pages and inside the sign-up
 * sheet, so a learner reads the text without losing what they typed.
 */
import React from 'react';

import {
  LEGAL_VERSION,
  legalDocument,
  legalLabels,
  legalTextParts,
  type LegalDocumentKind,
  type LegalLanguage,
} from '@/lib/legal';

function Paragraph({ text }: { text: string }) {
  return (
    <p className="av2-body lg-doc__p">
      {legalTextParts(text).map((part, index) =>
        part.kind === 'contact' ? (
          part.value.includes('@') ? (
            <a key={index} href={`mailto:${part.value}`}>
              {part.value}
            </a>
          ) : (
            <span key={index}>{part.value}</span>
          )
        ) : (
          <React.Fragment key={index}>{part.value}</React.Fragment>
        ),
      )}
    </p>
  );
}

export function LegalDocumentView({
  kind,
  language,
  showTitle = true,
}: {
  kind: LegalDocumentKind;
  language: LegalLanguage;
  /** The sheet already prints the title in its head. */
  showTitle?: boolean;
}) {
  const doc = legalDocument(kind, language);
  const labels = legalLabels(language);
  return (
    <article className="lg-doc" lang={language} data-legal-document={kind}>
      {showTitle && <h1 className="av2-headline av2-headline--screen">{doc.title}</h1>}
      <p className="av2-label lg-doc__meta">
        {labels.updated} {LEGAL_VERSION}
      </p>
      <p className="av2-body av2-body--lg lg-doc__lead">{doc.lead}</p>
      {doc.sections.map((section) => (
        <section key={section.h} className="lg-doc__section">
          <h2 className="lg-doc__h">{section.h}</h2>
          {section.p.map((text) => (
            <Paragraph key={text} text={text} />
          ))}
        </section>
      ))}
      <style jsx global>{`
        .av2 .lg-doc {
          display: flex;
          flex-direction: column;
          gap: 4px;
          min-width: 0;
        }
        .av2 .lg-doc__meta {
          color: var(--av2-muted);
        }
        .av2 .lg-doc__lead {
          border-bottom: 1px solid var(--av2-line);
          padding-bottom: 14px;
          margin-bottom: 4px;
        }
        .av2 .lg-doc__section {
          display: flex;
          flex-direction: column;
          gap: 6px;
          padding-top: 14px;
        }
        .av2 .lg-doc__h {
          font-size: 1rem;
          font-weight: 700;
          margin: 0;
          color: var(--av2-ink);
        }
        .av2 .lg-doc__p {
          margin: 0;
          color: var(--av2-ink-2);
          overflow-wrap: anywhere;
        }
        .av2 .lg-doc a {
          color: var(--av2-blue);
        }
      `}</style>
    </article>
  );
}

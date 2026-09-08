/* The chapter's opening narration. Blue, because the design assigns blue to
 * story and information. */

import React from 'react';

interface NarrativeCardProps {
  narrative: string | null;
}

export default function NarrativeCard({ narrative }: NarrativeCardProps) {
  if (!narrative) return null;

  return (
    <section className="av2-surface av2-surface--blue bib-narrative" aria-label="Ouverture du chapitre">
      <p className="av2-label">Ouverture</p>
      <p className="av2-body av2-body--lg bib-narrative__text">{narrative}</p>
    </section>
  );
}

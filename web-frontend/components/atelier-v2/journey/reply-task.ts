/** A cast member is addressed by the name their friends use. */
export function shortCharacterName(name: string, id?: string | null): string {
  if (id === 'romy_tremblay' || /Romane|Romy/.test(name)) return 'Romy';
  if (id === 'augustin_de_roncourt') return 'Gus';
  return name.trim().split(/\s+/)[0] || name;
}

/** Grammar notation belongs in help, rather than the reply's task line. */
export function replyTaskLine(objective: string): string {
  return objective
    .replace(/Romane\s*[«"]\s*Romy\s*[»"]\s*Tremblay/g, 'Romy')
    .replace(/\([^)]*(?:\+|→|->)[^)]*\)/g, '')
    .replace(/si\s*\+\s*(?:présent|present)\s*(?:→|->)\s*(?:futur|future)/gi, 'si')
    .replace(/\s+/g, ' ').trim();
}

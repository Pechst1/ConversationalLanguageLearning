import { castDisplayName } from './journey-faces';

/** A cast member is addressed by the name their friends use: the cast's one display name. */
export function shortCharacterName(name: string, id?: string | null): string {
  return castDisplayName(id, name) ?? (name.trim().split(/\s+/)[0] || name);
}

/** Grammar notation belongs in help, rather than the reply's task line. */
export function replyTaskLine(objective: string): string {
  return objective
    .replace(/Romane\s*[«"]\s*Romy\s*[»"]\s*Tremblay/g, 'Romy')
    .replace(/\([^)]*(?:\+|→|->)[^)]*\)/g, '')
    .replace(/si\s*\+\s*(?:présent|present)\s*(?:→|->)\s*(?:futur|future)/gi, 'si')
    .replace(/\s+/g, ' ').trim();
}

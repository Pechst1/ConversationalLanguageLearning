/**
 * The letter's shape and the composer it asks for, kept outside the page so a
 * node test can hold it.
 *
 * The backend rotates five mission formats (serial_arc_planner.py) and ships a
 * per-format payload + writing scaffold. The shape is the server's: it already
 * reads who writes, so a friend's note in tu arrives as `chat_message`, never
 * as a formal e-mail (#953, `format_for_writer` in app/services/missions.py).
 */

import type { RealWorldMission } from '@/services/api';
import type { CourrierCopy } from './courrier-copy';

export type MissionFormat = 'chat_message' | 'email_formal' | 'admin_form' | 'voicemail_reply' | 'phone_call';

const KNOWN: MissionFormat[] = ['chat_message', 'email_formal', 'admin_form', 'voicemail_reply', 'phone_call'];

export function missionFormat(mission: RealWorldMission | null): MissionFormat {
  const raw = String(mission?.mission_format || mission?.prompt_payload?.mission_format || 'chat_message');
  return (KNOWN as string[]).includes(raw) ? (raw as MissionFormat) : 'chat_message';
}

export function missionWriting(mission: RealWorldMission | null): { title: string; instruction: string; placeholder: string } {
  const prompt = mission?.prompt_payload || {};
  return {
    title: String(prompt.writing_title || ''),
    instruction: String(prompt.writing_instruction || ''),
    placeholder: String(prompt.writing_placeholder || ''),
  };
}

// WP-82: the labels and instructions are chrome (`t`); the email and form
// placeholders are French templates of the letter itself, so they stay French.
export function formatComposerCopy(
  format: MissionFormat,
  writing: { title: string; instruction: string; placeholder: string },
  t: CourrierCopy,
) {
  // The server writes `writing_title` / `writing_instruction` in French: they
  // are chrome, so they are only used when the chrome is French (B1+).
  const serverChrome = t.lang === 'fr';
  const title = serverChrome ? writing.title : '';
  const instruction = serverChrome ? writing.instruction : '';
  switch (format) {
    case 'email_formal':
      return {
        label: title || t.composer_label_email,
        instruction: instruction || t.composer_instruction_email,
        placeholder: writing.placeholder || 'Objet : ...\n\nMadame, Monsieur,\n...',
      };
    case 'admin_form':
      return {
        label: title || t.composer_label_form,
        instruction: instruction || t.composer_instruction_form,
        placeholder: writing.placeholder || 'Nom :\nAdresse :\nDemande :',
      };
    case 'voicemail_reply':
      return { label: t.composer_label_voicemail, instruction: t.composer_instruction_voicemail, placeholder: t.composer_placeholder_voice };
    case 'phone_call':
      return { label: t.composer_label_call, instruction: t.composer_instruction_call, placeholder: t.composer_placeholder_voice };
    default:
      return { label: t.composer_label_chat, instruction: '', placeholder: t.composer_placeholder_chat };
  }
}

// The composer verb per artefact, in the chrome language.
export function submitLabel(format: MissionFormat, t: CourrierCopy) {
  if (format === 'email_formal') return t.send_email;
  if (format === 'admin_form') return t.send_form;
  return t.send;
}

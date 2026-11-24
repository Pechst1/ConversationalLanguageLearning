// The shape a Courrier letter is answered in, and the composer that shape opens.
//
// The backend rotates five mission formats (missions.py `_choose_format`,
// serial_arc_planner.py) and ships a per-format payload + writing scaffold. These
// readers surface it so the composer can adapt.
//
// #953: a friend's note in «tu» (Marin, Gus, Lila) opened «Deine E-Mail · Ein Betreff,
// eine Anrede…» with «E-Mail senden»: the format had been drawn apart from who writes.
// The server now holds every format to the writer's register (`format_for_writer`);
// letters stored before that still carry `email_formal`, so the page reads the same rule.
import type { CourrierCopy } from './courrier-copy';

export type MissionFormat = 'chat_message' | 'email_formal' | 'admin_form' | 'voicemail_reply' | 'phone_call';

type MissionLike = {
  mission_format?: unknown;
  prompt_payload?: Record<string, any> | null;
} | null | undefined;

const KNOWN: MissionFormat[] = ['chat_message', 'email_formal', 'admin_form', 'voicemail_reply', 'phone_call'];

// The shapes only a formal writer sends (missions.py FORMAL_FORMATS).
const FORMAL: MissionFormat[] = ['email_formal', 'admin_form'];

// «tu / registre familier», «tu / warm informal»: the writer tutoie the learner
// (missions.py `register_kind`, informal wins).
const INFORMAL_WORDS = ['tu', 'tutoiement', 'informal', 'informel', 'informelle', 'casual'];

export function writerSaysTu(register: unknown): boolean {
  const words = String(register || '').toLowerCase().split(/[^a-z0-9_à-ÿœæ]+/);
  return words.some((word) => INFORMAL_WORDS.includes(word));
}

export function missionFormat(mission: MissionLike): MissionFormat {
  const prompt = mission?.prompt_payload || {};
  const raw = String(mission?.mission_format || prompt.mission_format || 'chat_message');
  const format = (KNOWN as string[]).includes(raw) ? (raw as MissionFormat) : 'chat_message';
  const register = prompt.messenger?.target_register || prompt.target_register;
  if (FORMAL.includes(format) && writerSaysTu(register)) return 'chat_message';
  return format;
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
